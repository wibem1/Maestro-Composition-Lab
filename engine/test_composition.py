import copy,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import composition as c
import maestro_analyse as a

SCORE={'title':'Prüfstück','composer':'','time':[3,4],'key':[-3,'minor'],'tempo':126,'staves':[
 {'name':'Pianoforte','clef':'treble','bars':[
  {'voices':[[['q',['C4','Eb4'],['accent']],['q',['D4']],['q',['E4'],[],True]]],'dynamics':[[0,'f']]},
  {'voices':[[['q',['E4']],['h',['F4']]]]}], 'slurs':[[1,1,1,2,1,2]]},
 {'name':'Pianoforte','clef':'bass','bars':[{'voices':[[['h.',['C3']]]]},{'voices':[[['h.',None]]]}]}
]}
class Tests(unittest.TestCase):
 def test_complete_score(self):
  data=c.validate(SCORE);self.assertEqual(len(data['staves'][0]['bars']),2)
  self.assertEqual(c.duration_ticks('h.'),2880)
  self.assertEqual(c.parse_composition('```json\n'+json.dumps(SCORE)+'\n```')['key'],[-3,'minor'])
 def test_reject_bad_bars_and_ties(self):
  variants=[]
  x=copy.deepcopy(SCORE);x['staves'][0]['bars'][0]['voices'][0][0][0]='h';variants.append(x)
  x=copy.deepcopy(SCORE);x['staves'][0]['bars'][1]['voices'][0][0][1]=['G4'];variants.append(x)
  x=copy.deepcopy(SCORE);x['staves'][0]['bars'][0]['voices'][0][0][1]=['C4);os.execute("bad")'];variants.append(x)
  x=copy.deepcopy(SCORE);x['staves'][1]['bars'].pop();variants.append(x)
  x=copy.deepcopy(SCORE);x['staves'][0]['slurs']=[[1,1,1,99,1,1]];variants.append(x)
  for x in variants:
   with self.assertRaises(c.ScoreError):c.validate(x)
 def test_writer_is_fixed_and_guarded(self):
  text=c.lua_writer(SCORE,'Test','model')
  self.assertLess(text.index('assert(not e.isNote'),text.index('score:setTime'))
  self.assertIn('score:setTime(3,4,1)',text);self.assertIn('score:setKey(-3,1,"minor")',text)
  self.assertIn('m:append(event[1],notes,layer)',text)
  self.assertIn("musicalCommand('slur'",text)
 def test_invalid_answer_retained(self):
  response={'answer':'{unvollständig','provider':'Google','model':'test','usage':{'x':10}}
  with patch.object(a,'query_model',return_value=response),patch.object(a,'save_composition',return_value='saved'):
   r=a.compose('Google','secret','test','Auftrag',8192)
   self.assertEqual(r['raw_response'],'{unvollständig');self.assertIsNone(r['composition']);self.assertTrue(r['validation_error']);self.assertEqual(r['usage']['x'],10)
   self.assertNotIn('secret',json.dumps(r))
 def test_roundtrip_saved_data(self):
  r={'composition':c.validate(SCORE),'raw_response':json.dumps(SCORE),'provider':'Test','model':'m','id':'test'}
  with tempfile.TemporaryDirectory() as d,patch.object(a,'ROOT',pathlib.Path(d)):
   path=a.save_composition(r);self.assertEqual(json.loads(pathlib.Path(path).read_text(encoding='utf8'))['composition']['title'],SCORE['title'])
 def test_targets_response(self):
  v={'content':[{'type':'text','text':json.dumps({'scores':[{'score_id':'one','title':'Leer'},{'score_id':'two','title':'Original'}]})}]}
  self.assertEqual(a.open_score_options(v)[1]['score_id'],'two')
 def test_commit_sequence_and_no_commit_after_failure(self):
  class Client:
   def __init__(self,fail=False):self.calls=[];self.fail=fail
   def connect(self):return {},[{'name':'run_script','inputSchema':{'properties':{'score_id':{'type':'string'},'code':{'type':'string'},'read_only':{'type':'boolean'}}}}]
   def tool(self,name,args):
    self.calls.append((name,dict(args)))
    if name=='run_script' and self.fail:raise a.UserError('Ziel enthält Musik')
    return {'content':[{'type':'text','text':'COMPOSITION_WRITTEN'}]}
   def close(self):pass
  client=Client()
  with patch.object(a,'mcp_for_app',return_value=client):a.write_composition(SCORE,'target','Test','model')
  self.assertEqual([x[0] for x in client.calls],['describe_api','run_script','run_script'])
  self.assertTrue(client.calls[1][1]['read_only']);self.assertFalse(client.calls[2][1]['read_only'])
  self.assertEqual(client.calls[2][1]['score_id'],'target')
  client=Client(True)
  with patch.object(a,'mcp_for_app',return_value=client):
   with self.assertRaises(a.UserError):a.write_composition(SCORE,'target','Test','model')
  self.assertEqual(len(client.calls),2)

if __name__=='__main__':unittest.main(verbosity=2)
