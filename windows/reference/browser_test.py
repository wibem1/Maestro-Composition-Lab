"""Real Chromium UI test. APIs simulated; backend validation tested separately."""
import json,os,pathlib,sys,tempfile,threading
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parent
if not (ROOT/'engine').exists():ROOT=ROOT.parent
sys.path.insert(0,str(ROOT/'engine'))
import maestro_analyse as a
from test_workspace import source,fragment
writes=[];queries=[]
class Client:
 def connect(self):return {},[{'name':'run_script','inputSchema':{'properties':{k:{'type':v} for k,v in [('code','string'),('score_id','string'),('read_only','boolean')]}}}]
 def tool(self,name,args):
  if name=='list_open_scores':return {'scores':[{'score_id':'original','title':'Original'},{'score_id':'blank','title':'Leere Partitur'}]}
  if name=='run_script':
   code=args['code']
   if 'BEGIN_MAESTRO_WORKSPACE' in code:return {'content':[{'type':'text','text':json.dumps(source('selection' if 'local scope="selection"' in code else 'all'))}]}
   if 'MAESTRO_TARGET:' in code:return {'content':[{'type':'text','text':'MAESTRO_TARGET:2:'+('0' if args['score_id']=='blank' else '5')}]}
   if not args.get('read_only'):writes.append(args['score_id'])
   return {'content':[{'type':'text','text':'WORKSPACE_APPLIED'}]}
  return {}
 def close(self):pass
def query(provider,key,model,system,user,limit):
 data=json.loads(user);queries.append(data)
 if 'musikalischer Analytiker' in system:answer='Das Stück besitzt eine klare musikalische Idee. Die Analyse umfasst den eingelesenen Bereich: E5 $\\rightarrow$ D5.'
 elif 'Erlaubte_Taktstimmen' in data:answer=json.dumps({'explanation':'Das Motiv erhält eine neue Achtelbewegung.','cells':[{'staff':1,'bar':1,'layer':1,'events':[['8',['C4']],['8',None],['8',['D4']],['8',['E4']]]}],'slurs':[{'from':[1,1,1,1],'to':[1,1,1,4]}]})
 elif '"changes"' in system:answer=json.dumps({'explanation':'Die erste Note wird gezielt verändert.','changes':[{'id':'a','pitches':['C#4']}]})
 else:
  members=data.get('Neue_Besetzung') or data.get('Besetzung')
  score=fragment(len(members),data['Taktzahl'])
  score['staves'][0]['directions']=[{'kind':'text','from':[1,1,1],'text':'dolce','category':'expression'},{'kind':'pedal','from':[1,1,1],'to':[data['Taktzahl'],1,1]}]
  answer=json.dumps(score)
 return {'answer':answer,'provider':provider,'model':model,'usage':{'test':True},'version':'2.5.1','finish':'STOP'}
a.mcp_for_app=lambda path:Client();a.query_model=query
a.preferences.load=lambda:{'provider':'Google','profiles':{'Google':{'key':'test-only','model':'test-model'}},'can_protect':False}
a.preferences.save=lambda data:{'ok':True}
with tempfile.TemporaryDirectory() as folder:
 os.environ['MAESTRO_DATA_DIR']=folder
 server=a.http.server.ThreadingHTTPServer(('127.0.0.1',0),a.Handler);server.authority='127.0.0.1:'+str(server.server_port);server.token='browser-session';server.compositions={};thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=sys.argv[1],headless=True,args=['--no-sandbox'])
   page=browser.new_page(viewport={'width':1200,'height':850});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://'+server.authority);page.wait_for_function("document.querySelector('#run').disabled === false && document.querySelector('#model').value === 'test-model'")
   assert page.locator('#ensembleDetails').evaluate('(e)=>!e.open')
   page.locator('#task').fill('Ein heiteres Klavierstück');page.locator('#bars').fill('2');page.locator('#run').click();page.wait_for_function("document.querySelector('#status').textContent.includes('In Maestro angewendet')")
   assert len(writes)==1
   assert 'Pedal' in page.locator('#resultText').inner_text() and 'Spielanweisung' in page.locator('#resultText').inner_text()
   page.screenshot(path='/tmp/maestro-ui-220-compose.png',full_page=True)
   # Whole/selected analysis: no write operations.
   page.locator('#tab-analysis').click();page.locator('#sourceScore').select_option('original');page.locator('#run').click();page.wait_for_function("document.querySelector('#status').textContent==='Analyse erhalten.'")
   assert len(writes)==1
   assert 'E5 → D5' in page.locator('#resultText').inner_text()
   assert '$' not in page.locator('#resultText').inner_text()
   page.locator('#scope').select_option('selection');page.locator('#run').click();page.wait_for_function("document.querySelector('#status').textContent==='Analyse erhalten.'")
   # Analysis -> revision is a paid proposal step, never an automatic write.
   assert page.locator('#apply').is_hidden();assert page.locator('#review').is_enabled()
   before_review=len(writes);page.locator('#review').click();page.wait_for_function("document.querySelector('#status').textContent.startsWith('Überarbeitung aus Analyse erstellt')")
   assert len(writes)==before_review;assert page.locator('#apply').is_enabled()
   assert 'Vorhandene_Analyse' in queries[-1]
   page.locator('#apply').click();page.wait_for_function("document.querySelector('#status').textContent.startsWith('In Maestro angewendet')");assert len(writes)==before_review+1
   page.locator('#tab-analysis').click();assert 'E5 → D5' in page.locator('#resultText').inner_text()
   # Continue and add instruments: explicit apply, preserving original target binding.
   for mode in ['continue','instruments']:
    page.locator('#tab-'+mode).click();page.locator('#sourceScore').select_option('original');page.locator('#run').click();page.wait_for_function("document.querySelector('#status').textContent.startsWith('Vorschlag erstellt')")
    count=len(writes);assert not page.locator('#apply').is_disabled();page.locator('#apply').click();page.wait_for_function("document.querySelector('#status').textContent.startsWith('In Maestro angewendet')");assert len(writes)==count+1
   page.locator('#tab-revise').click();page.locator('#sourceScore').select_option('original');page.locator('#run').click();page.wait_for_function("document.querySelector('#status').textContent.startsWith('Vorschlag erstellt')")
   assert page.locator('#changes tr').count()==1;page.screenshot(path='/tmp/maestro-ui-220-revise.png',full_page=True)
   page.locator('#reviseKind').select_option('replace');page.locator('#read').click();page.wait_for_function("document.querySelector('#status').textContent.startsWith('Eingelesen:')");page.locator('#run').click();page.wait_for_function("document.querySelector('#status').textContent.startsWith('Vorschlag erstellt')")
   assert 'neu gestaltete' in page.locator('#resultSummary').inner_text();assert '4 Einträge' in page.locator('#changes').inner_text()
   assert queries[-1]['Vorhandene_Partitur']['context_scope']=='whole_score';assert len(queries[-1]['Vorhandene_Partitur']['staves'])==2
   before=len(writes);page.locator('#apply').click();page.wait_for_function("document.querySelector('#status').textContent.startsWith('In Maestro angewendet')");assert len(writes)==before+1
   # Native-sized and narrow windows: no document-wide horizontal overflow.
   for width,height in [(1200,850),(980,720),(760,620)]:
    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(100)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(width,height)
   page.screenshot(path='/tmp/maestro-ui-220-narrow.png',full_page=True)
   assert not errors,errors
   browser.close()
   print('Real Chromium: all five modes; whole/selection analysis; direct new-score write; explicit continuation/instrument apply; revision diff; 1200/980/760px layouts; no JS errors. Maestro/API simulated, no paid requests.')
 finally:server.shutdown();server.server_close();thread.join()
