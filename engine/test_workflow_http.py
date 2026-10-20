import json,pathlib,tempfile,threading,types,unittest,urllib.request
from unittest.mock import patch
import maestro_analyse as a
from test_workspace import source,fragment

class Tests(unittest.TestCase):
 def test_real_http_workspace_roundtrip(self):
  snapshot=source();calls=[]
  class Client:
   def connect(self):return {},[{'name':'run_script','inputSchema':{'properties':{k:{'type':v} for k,v in [('score_id','string'),('code','string'),('read_only','boolean')]}}}]
   def tool(self,name,args):
    calls.append((name,dict(args)))
    if name=='list_open_scores':return {'scores':[{'score_id':'bound-score','title':'Original'}]}
    if name=='run_script':
     if 'BEGIN_MAESTRO_WORKSPACE' in args['code']:return {'content':[{'type':'text','text':json.dumps(snapshot)}]}
     return {'content':[{'type':'text','text':'WORKSPACE_APPLIED'}]}
    return {}
   def close(self):pass
  with tempfile.TemporaryDirectory() as folder,patch.object(a,'ROOT',pathlib.Path(folder)),patch.object(a,'mcp_for_app',side_effect=lambda path:Client()),patch.object(a,'query_model',return_value={'answer':json.dumps(fragment()),'provider':'Test','model':'m','usage':{}}):
   server=a.http.server.ThreadingHTTPServer(('127.0.0.1',0),a.Handler);server.authority='127.0.0.1:'+str(server.server_port);server.token='session-test';server.compositions={};thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   def post(route,data):
    req=urllib.request.Request('http://'+server.authority+route,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Session':server.token})
    with urllib.request.urlopen(req) as response:return json.load(response)
   try:
    self.assertEqual(len(post('/workspace/catalog',{})['sounds']),128)
    self.assertEqual(post('/workspace/scores',{})['scores'][0]['score_id'],'bound-score')
    read=post('/workspace/read',{'score_id':'bound-score','scope':'all'})
    r=post('/workspace/run',{'mode':'continue','source_id':read['id'],'provider':'Test','key':'secret','model':'m','task':'Fortsetzen','bars':1})
    self.assertIsNone(r['validation_error']);self.assertTrue(pathlib.Path(r['saved_path']).exists());self.assertNotIn('secret',pathlib.Path(r['saved_path']).read_text())
    applied=post('/workspace/apply',{'id':r['id'],'score_id':'wrong'})
    self.assertEqual(applied['score_id'],'bound-score')
    writes=[x[1] for x in calls if x[0]=='run_script' and 'WORKSPACE_APPLIED' in x[1]['code']]
    self.assertEqual(len(writes),2);self.assertTrue(writes[0]['read_only']);self.assertFalse(writes[1]['read_only'])
    # Ending rewrite option traverses the real HTTP service and preserves the source.
    with patch.object(a,'query_model',return_value={'answer':json.dumps(fragment(2,3)),'provider':'Test','model':'m'}):
     transition=post('/workspace/run',{'mode':'continue','source_id':read['id'],'provider':'Test','key':'secret','model':'m','task':'Mit Übergang','bars':1,'transition_bars':2})
    self.assertIsNone(transition['validation_error']);self.assertEqual(transition['transition_bars'],2)
    self.assertEqual(transition['source'],read);self.assertEqual(len(transition['composition']['staves'][0]['bars']),3)
    transition_saved=json.loads(pathlib.Path(transition['saved_path']).read_text())
    self.assertEqual(transition_saved['source']['guard'],read['guard'])
    post('/workspace/apply',{'id':transition['id'],'score_id':'wrong'})
    # The new real HTTP route accepts an analysis, creates a proposal and only
    # writes after a separate /apply request. Maestro itself is simulated here.
    with patch.object(a,'query_model',return_value={'answer':'Verbessere die Motivführung.','provider':'Kritiker','model':'A'}):
     analysed=post('/workspace/run',{'mode':'analysis','source_id':read['id'],'provider':'Test','key':'secret','model':'A','task':'Analysiere'})
    import workspace as w
    groups=sorted({(e['staff'],e['bar'],e['layer']) for e in w.entries(snapshot)})
    proposal={'cells':[{'staff':si,'bar':bi,'layer':li,'events':[['h',['C4']]]} for si,bi,li in groups]}
    before=sum(not args.get('read_only',True) for name,args in calls if name=='run_script')
    with patch.object(a,'query_model',return_value={'answer':json.dumps(proposal),'provider':'Bearbeiter','model':'B'}):
     reviewed=post('/workspace/review',{'id':analysed['id'],'provider':'Test','key':'secret','model':'B'})
    self.assertIsNone(reviewed['validation_error']);self.assertEqual(reviewed['review_origin']['model'],'A')
    self.assertEqual(sum(not args.get('read_only',True) for name,args in calls if name=='run_script'),before)
    post('/workspace/apply',{'id':reviewed['id'],'score_id':'wrong'})
    self.assertEqual(sum(not args.get('read_only',True) for name,args in calls if name=='run_script'),before+1)
    history=post('/workspace/history',{})
    self.assertGreaterEqual(history['total'],3)
    number_before=len(list((pathlib.Path(folder)/'Ergebnisse').glob('*.json')))
    reopened=post('/workspace/history/open',{'id':history['items'][0]['id']})
    self.assertIn('history_origin',reopened)
    self.assertEqual(len(list((pathlib.Path(folder)/'Ergebnisse').glob('*.json'))),number_before)
    with self.assertRaises(urllib.error.HTTPError):
     post('/workspace/run',{'mode':'continue','source_id':'fehlt','task':'Fortsetzen','provider':'Test','model':'Argon','key':'secret-value'})
    diagnostic=post('/desktop/info',{})
    self.assertEqual(diagnostic['last_error']['mode'],'continue')
    self.assertEqual(diagnostic['last_error']['model'],'Argon')
    self.assertNotIn('secret-value',json.dumps(diagnostic))
   finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
