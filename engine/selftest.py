"""Offline tests. No provider requests and no Maestro runtime are used."""
import ctypes, importlib.util, json, pathlib, subprocess, sys, threading, unittest, urllib.request, urllib.error, tempfile
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(P))
import maestro_analyse as a
EXPORT={'format':'maestro-review-1','title':'Prüfstück','selected_entries':[{'duration':'q','tick':0,'pitches':[{'name':'C4','midi':60}]}],'context_cells':[],'warnings':[]}

class Tests(unittest.TestCase):
 def test_console_history(self):
  def block(d):return a.BEGIN+'\n'+json.dumps(d)+'\n'+a.END
  newer={**EXPORT,'title':'Neu'}
  self.assertEqual(a.parse_export('Konsole\n'+block(EXPORT)+'\nFehler\n'+block(newer)+'\nEnde')['title'],'Neu')
  self.assertEqual(a.parse_export(block(EXPORT)+'\n'+a.BEGIN+'\nunfertig')['title'],'Prüfstück')
 def test_invalid_export(self):
  for text in ('{}',a.BEGIN+'\n{}','<script>','[]',json.dumps({**EXPORT,'selected_entries':[]})):
   with self.assertRaises(a.UserError):a.parse_export(text)
 def test_provider_responses(self):
  cases={
   'Google':{'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'intern','thought':True},{'text':'Analyse'}]}}],'usageMetadata':{'totalTokenCount':10}},
   'Anthropic':{'content':[{'type':'thinking','thinking':'intern'},{'type':'text','text':'Analyse'}],'stop_reason':'end_turn','usage':{'input_tokens':1}},
   'OpenAI':{'output':[{'type':'reasoning'},{'type':'message','content':[{'type':'output_text','text':'Analyse'}]}],'status':'completed','usage':{'input_tokens':1}},
   'OpenRouter':{'choices':[{'message':{'content':'Analyse'},'finish_reason':'stop'}],'usage':{'cost':.001}}
  }
  for provider,response in cases.items():
   with self.subTest(provider=provider),patch.object(a,'request_json',return_value=response) as req:
    result=a.analyse(provider,'secret','test-model','Prüfen',EXPORT,8192)
    self.assertEqual(result['answer'],'Analyse')
    self.assertNotIn('secret',json.dumps(result))
    self.assertEqual(req.call_count,1)
 def test_model_pagination(self):
  with patch.object(a,'request_json',side_effect=[{'models':[{'name':'models/a','supportedGenerationMethods':['generateContent']}],'nextPageToken':'x'},{'models':[{'name':'models/image','supportedGenerationMethods':['predict']}]}]):
   self.assertEqual([m['id'] for m in a.list_models('Google','secret')],['a'])
  with patch.object(a,'request_json',side_effect=[{'data':[{'id':'one'}],'has_more':True,'last_id':'one'},{'data':[{'id':'two'}],'has_more':False}]):
   self.assertEqual(len(a.list_models('Anthropic','secret')),2)
 def test_no_automatic_retry(self):
  with patch.object(a,'request_json',side_effect=a.UserError('Netzwerk')) as req:
   with self.assertRaises(a.UserError):a.analyse('OpenAI','secret','test','',EXPORT,8192)
   self.assertEqual(req.call_count,1)
 def test_http_session_and_export(self):
  server=a.http.server.ThreadingHTTPServer(('127.0.0.1',0),a.Handler);server.authority='127.0.0.1:'+str(server.server_port);server.token='test-token'
  th=threading.Thread(target=server.serve_forever,daemon=True);th.start()
  try:
   url='http://'+server.authority
   with urllib.request.urlopen(url) as r:
    html=r.read().decode();self.assertIn('test-token',html);self.assertNotIn('__TOKEN__',html)
   body=json.dumps({'text':json.dumps(EXPORT)}).encode()
   with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(urllib.request.Request(url+'/validate',data=body))
   self.assertEqual(err.exception.code,403)
   with urllib.request.urlopen(urllib.request.Request(url+'/validate',data=body,headers={'X-Session':'test-token'})) as r:self.assertEqual(json.load(r)['entries'],1)
  finally:server.shutdown();server.server_close();th.join()
 def test_command_in_path(self):
  with patch.object(a.shutil,'which',side_effect=lambda n:'C:/custom/maestro-script.exe' if n=='maestro-script.exe' else None):
   exe,checked=a.discover_maestro(windows=True,environ={})
   self.assertEqual(exe,'C:/custom/maestro-script.exe')
 def test_custom_running_install(self):
  with tempfile.TemporaryDirectory() as d:
   helper=pathlib.Path(d)/'maestro-script.exe';helper.touch()
   running=pathlib.Path(d)/'Maestro.exe'
   result=subprocess.CompletedProcess([],0,(str(running)+'\n').encode(),b'')
   with patch.object(a.shutil,'which',return_value=None),patch.object(a.subprocess,'run',return_value=result):
    exe,checked=a.discover_maestro(windows=True,environ={'LOCALAPPDATA':d+'/local'})
    self.assertEqual(exe,str(helper))
 def test_explicit_missing_path(self):
  with patch.object(a.shutil,'which',return_value=None):
   exe,checked=a.discover_maestro('/nonexistent/maestro-test.exe',windows=True,environ={})
   self.assertIsNone(exe);self.assertEqual(len(checked),1)
 def test_missing_command_diagnostic(self):
  with patch.object(a,'discover_maestro',return_value=(None,['checked'])):
   r=a.probe();self.assertEqual(r['status'],'error');self.assertEqual(r['checked_paths'],['checked'])
 def test_split_mcp_print_output(self):
  r={'content':[{'type':'text','text':a.BEGIN},{'type':'text','text':json.dumps(EXPORT)},{'type':'text','text':a.END}]}
  self.assertEqual(a.extract_tool_export(r)['title'],'Prüfstück')
  wrapped={'content':[{'type':'text','text':json.dumps({'output':[a.BEGIN,json.dumps(EXPORT),a.END]})}]}
  self.assertEqual(a.extract_tool_export(wrapped)['title'],'Prüfstück')
 def test_live_read_protocol(self):
  # New subprocess validates order and guarantees read_only true. No real Maestro.
  code="""import sys,json
stage=0
for line in sys.stdin:
 x=json.loads(line)
 if 'id' not in x:continue
 m=x['method'];p=x.get('params',{})
 if m=='initialize':r={'protocolVersion':'2024-11-05','capabilities':{}}
 elif m=='tools/list':r={'tools':[{'name':'describe_api'},{'name':'run_script','inputSchema':{'properties':{'code':{'type':'string'},'read_only':{'type':'boolean'}}}}]}
 elif m=='tools/call' and p['name']=='describe_api':
  stage=1;r={'content':[{'type':'text','text':'API documentation'}]}
 elif m=='tools/call' and p['name']=='run_script':
  assert stage==1 and p['arguments']['read_only'] is True
  assert 'eachentry(selection)' in p['arguments']['code']
  stage=2;r={'content':[{'type':'text','text':json.dumps({'output':['BEGIN_MAESTRO_REVIEW',json.dumps(PAYLOAD),'END_MAESTRO_REVIEW']})}]}
 else:raise AssertionError('Unexpected call')
 print(json.dumps({'jsonrpc':'2.0','id':x['id'],'result':r}),flush=True)
""".replace('PAYLOAD',repr(EXPORT))
  probe=a.MCPProbe([sys.executable,'-u','-c',code])
  result=probe.read_selection((P/'03_Auswahl_fuer_Analyse.lua').read_text())
  self.assertEqual(result['title'],'Prüfstück');self.assertIsNotNone(probe.proc.poll())
 def test_missing_readonly_rejected(self):
  with patch.object(a.MCPProbe,'connect',return_value=({},[{'name':'describe_api'},{'name':'run_script','inputSchema':{'properties':{'code':{'type':'string'}}}}])),patch.object(a.MCPProbe,'tool') as tool,patch.object(a.MCPProbe,'close'):
   probe=object.__new__(a.MCPProbe)
   with self.assertRaises(a.UserError):probe.read_selection('test')
   tool.assert_not_called()
 def test_mcp_real_subprocess(self):
  # Fixture responds like a stdio MCP server, including a paginated tools list.
  code='''import sys,json
for l in sys.stdin:
 x=json.loads(l)
 if 'id' not in x:continue
 m=x['method'];p=x.get('params',{})
 r={'protocolVersion':'2024-11-05','serverInfo':{'name':'fixture','version':'1'},'capabilities':{}} if m=='initialize' else ({'tools':[{'name':'second','inputSchema':{}}]} if p.get('cursor') else {'tools':[{'name':'first','inputSchema':{}}],'nextCursor':'two'})
 print(json.dumps({'jsonrpc':'2.0','id':x['id'],'result':r}),flush=True)
'''
  probe=a.MCPProbe([sys.executable,'-u','-c',code]);result=probe.run()
  self.assertEqual([x['name'] for x in result['tools']],['first','second']);self.assertIsNotNone(probe.proc.poll())

if __name__=='__main__':unittest.main(verbosity=2)
