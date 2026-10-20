import copy,json,unittest
from unittest.mock import patch
import composition as c
import workspace as w
import replacement as r
import workflows as f
import maestro_analyse as a
from test_workspace import MODEL,source,execute

def proposal(events=None):
 return {'explanation':'Motiv rhythmisch entfaltet','cells':[{'staff':1,'bar':1,'layer':1,'events':events or [['8',['C4']],['8',None],['8',['D4']],['8',['E4']]]}],'slurs':[]}

def custom_source(extra):
 return execute(MODEL+extra+w.read_lua('selection')+'\nreturn output[2]')|{'id':'snapshot','score_id':'bound-score'}

class Tests(unittest.TestCase):
 def test_full_score_context_includes_remote_bars_and_other_instruments(self):
  src=source('selection');last=copy.deepcopy(src['staves'][0]['measures'][-1]);last['index']=12
  src['staves'][0]['measures'].append(last)
  context=w.ai_context(src)
  self.assertEqual(context['context_scope'],'whole_score');self.assertEqual(context['selected_ids'],['a','b'])
  self.assertEqual(context['staves'][0]['measures'][-1]['index'],12)
  self.assertEqual(len(context['staves']),2);self.assertNotIn('guard',context)
 def test_replacement_changes_count_preserves_other_music_and_marks(self):
  extra='music.staves[1].measures[1].dynamics={{tick=0,marking="p"}}\n'
  src=custom_source(extra);data=r.validate(proposal(),src)
  result=execute(MODEL+extra+r.writer(data,src)+'\nreturn json(score:raw())')
  es=result['staves'][0]['measures'][0]['entries'];self.assertEqual(len(es),4);self.assertEqual(es[1]['pitches'],[])
  self.assertEqual(result['staves'][0]['measures'][0]['dynamics'],[{'tick':0,'marking':'p'}])
  self.assertEqual(result['staves'][0]['measures'][1]['entries'],[e['raw'] for e in src['staves'][0]['measures'][1]['entries']])
  self.assertEqual(result['staves'][1]['measures'][0]['entries'],[e['raw'] for e in src['staves'][1]['measures'][0]['entries']])
 def test_preserves_unselected_voice_inside_same_bar(self):
  extra='local x=event("other","h",{"G4"});x.layer=2;table.insert(music.staves[1].measures[1].entries,x)\n'
  src=custom_source(extra);result=execute(MODEL+extra+r.writer(proposal(),src)+'\nreturn json(score:raw())')
  self.assertEqual(result['staves'][0]['measures'][0]['entries'][0]['id'],'other')
  self.assertEqual(len(result['staves'][0]['measures'][0]['entries']),5)
 def test_fewer_entries_supported(self):
  src=source('selection');result=execute(MODEL+r.writer(proposal([['h',['F4','A4']]]),src)+'\nreturn json(score:raw())')
  es=result['staves'][0]['measures'][0]['entries'];self.assertEqual(len(es),1);self.assertEqual(es[0]['pitches'],['F4','A4'])
 def test_partial_selection_rejected_before_paid_request(self):
  src=source('selection');src['selected_ids']=['a']
  body={'mode':'revise','revise_kind':'replace','task':'Neu','provider':'Test','key':'secret','model':'m'}
  with patch.object(a,'query_model') as query,patch.object(f,'assert_current') as guard:
   with self.assertRaisesRegex(c.ScoreError,'alle Noten'):f.run(a,body,src)
   query.assert_not_called();guard.assert_not_called()
 def test_missing_extra_wrong_length_and_invalid_notes_rejected(self):
  src=source('selection')
  for data in [{'cells':[]},proposal([['q',['C4']]]),proposal([['h',['H4']]])]:
   with self.assertRaises(c.ScoreError):r.validate(data,src)
  data=proposal();data['cells'][0]['bar']=2
  with self.assertRaises(c.ScoreError):r.validate(data,src)
  data=proposal();data['cells']*=2
  with self.assertRaises(c.ScoreError):r.validate(data,src)
 def test_boundary_ties_validated_against_untouched_music(self):
  src=source('selection')
  good=proposal([['h',['E4'],[],True]])
  self.assertTrue(r.validate(good,src)['cells'][0]['events'][0][3])
  with self.assertRaisesRegex(c.ScoreError,'Übergang'):r.validate(proposal([['h',['F4'],[],True]]),src)
  extra='music.staves[1].measures[1].entries[2].tied=true;selection={c=true}\n'
  src=custom_source(extra);data={'cells':[{'staff':1,'bar':2,'layer':1,'events':[['h',['F4']]]}]}
  with self.assertRaisesRegex(c.ScoreError,'Übergang'):r.validate(data,src)
 def test_internal_slur_replaced_with_generated_slur(self):
  extra='music.slurs={{id="curve",first="a",last="b"}}\n'
  src=custom_source(extra);data=proposal();data['slurs']=[{'from':[1,1,1,1],'to':[1,1,1,4]}]
  validated=r.validate(data,src);self.assertEqual(validated['removed_curves'],1)
  result=execute(MODEL+extra+r.writer(validated,src)+'\nreturn json(score:raw())')
  self.assertEqual(len(result['slurs']),1);self.assertNotEqual(result['slurs'][0]['id'],'curve')
  self.assertNotIn(result['slurs'][0]['first'],['a','b'])
 def test_cross_boundary_slur_blocks_before_query(self):
  src=custom_source('music.slurs={{id="curve",first="b",last="c"}}\n')
  with self.assertRaisesRegex(c.ScoreError,'Auswahlgrenze'):r.targets(src)
 def test_stale_snapshot_and_unexpected_mutation_rejected(self):
  src=source('selection')
  with self.assertRaisesRegex(RuntimeError,'seit dem Einlesen'):execute(MODEL+'music.tempo=120\n'+r.writer(proposal(),src)+'\nreturn "null"')
  broken='local original=entryProxy;entryProxy=function(data,m)local proxy=original(data,m);local del=proxy.delete;return setmetatable({delete=function(self)del(proxy);music.staves[2].measures[1].entries[1].pitches={"D3"}end},{__index=proxy,__newindex=proxy}) end\n'
  with self.assertRaisesRegex(RuntimeError,'Nicht markierte Musik'):execute(MODEL+broken+r.writer(proposal(),src)+'\nreturn "null"')
 def test_workflow_sends_context_and_loads_validated_proposal(self):
  src=source('selection');body={'mode':'revise','revise_kind':'replace','task':'Entfalte das Motiv','provider':'Test','key':'secret','model':'m'}
  reply={'answer':json.dumps(proposal()),'provider':'Test','model':'m','usage':{}}
  with patch.object(f,'assert_current'),patch.object(a,'query_model',return_value=reply) as query,patch.object(a,'save_composition',return_value='saved'):
   record=f.run(a,body,src);self.assertIsNone(record['validation_error']);self.assertIsNotNone(record['replacement'])
   request=json.loads(query.call_args.args[4]);self.assertEqual(len(request['Vorhandene_Partitur']['staves']),2)
   self.assertEqual(request['Erlaubte_Taktstimmen'][0]['ticks'],1920)
   loaded=f.load(a,json.dumps(record));self.assertEqual(loaded['replacement'],record['replacement'])
   self.assertNotIn('secret',json.dumps(loaded))
 def test_multi_cell_multivoice_and_rest_replacement(self):
  extra='selection={a=true,b=true,c=true,d=true,e=true}\n';src=custom_source(extra)
  data={'cells':[{'staff':e['staff'],'bar':e['bar'],'layer':e['layer'],'events':[['h',None]]} for e in r.targets(src)]}
  result=execute(MODEL+extra+r.writer(data,src)+'\nreturn json(score:raw())')
  self.assertTrue(all(not e['pitches'] for st in result['staves'] for m in st['measures'] for e in m['entries']))
 def test_slur_endpoints_must_be_generated_notes(self):
  data=proposal();data['slurs']=[{'from':[1,1,1,2],'to':[1,1,1,4]}]
  with self.assertRaises(c.ScoreError):r.validate(data,source('selection'))

 def test_unknown_curve_anchors_and_note_bound_marks_rejected(self):
  src=custom_source('music.slurs={{id="unknown",start=1,finish=2}}\n')
  with self.assertRaisesRegex(c.ScoreError,'Anker'):r.targets(src)
  src=source('selection');src['staves'][0]['measures'][0]['texts']=[{'entryId':'a','text':'dolce'}]
  with self.assertRaisesRegex(c.ScoreError,'Taktzeichen'):r.targets(src)
 def test_apply_replacement_executes_preflight_then_commit(self):
  class Client:
   def __init__(self):self.calls=[]
   def connect(self):return {},[{'name':'run_script','inputSchema':{'properties':{k:{'type':v} for k,v in [('score_id','string'),('code','string'),('read_only','boolean')]}}}]
   def tool(self,name,args):
    if name=='run_script':
     self.calls.append(dict(args));return {'content':[{'type':'text','text':json.dumps(execute(MODEL+args['code']+'\nreturn json(output)'))}]}
    return {}
   def close(self):pass
  client=Client();src=source('selection')
  record={'id':'revision','mode':'revise','revise_kind':'replace','replacement':r.validate(proposal(),src),'source':src}
  with patch.object(a,'mcp_for_app',return_value=client),patch.object(a,'save_composition',return_value='saved'):
   result=f.apply(a,record,'wrong-ui-document','')
  self.assertTrue(record['applied']);self.assertEqual(result['score_id'],'bound-score')
  self.assertEqual([x['read_only'] for x in client.calls],[True,False])
  self.assertEqual(client.calls[0]['code'],client.calls[1]['code'])

if __name__=='__main__':unittest.main()
