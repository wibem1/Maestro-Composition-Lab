"""End-to-end bounded ending rewrite, including real Lua execution."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import composition as c
import history as h
import maestro_analyse as a
import transition as t
import workflows as f
import workspace as w
from test_workspace import execute,fragment
from test_expression import EXPRESS_MODEL

SETUP='''
music.measureMarks={}
score:appendMeasures(2)
for si,st in ipairs(music.staves) do
 for bi=3,4 do st.measures[bi].entries={event('tail'..si..bi,'h',{'C4'})};st.measures[bi].dynamics={{tick=0,marking='fff'}} end
end
music.slurs={{first='a',last='b'},{first='tail13',last='tail14'}}
'''

def fixture(extra=''):
    model=EXPRESS_MODEL.replace("or key=='systemTexts'", "or key=='systemTexts' or key=='measureMarks'")+SETUP+extra
    src=execute(model+w.read_lua('all')+'\nreturn output[2]')|{'id':'original','score_id':'bound-score'}
    return model,src

def proposal(tail=2,new=2):
    data=fragment(2,tail+new)
    data['staves'][0]['bars'][0]['voices']=[[['q',['D4']],['q',['E4']]]]
    data['staves'][0]['slurs']=[[tail,1,1,tail+1,1,1]]
    data['staves'][0]['directions']=[{'kind':'crescendo','from':[tail,1,1],'to':[tail+1,1,1]}]
    data['staves'][0]['bars'][0]['dynamics']=[[0,'p']]
    return data

class Tests(unittest.TestCase):
 def test_rewrite_tail_and_append_keep_prefix_instruments_and_curves(self):
    model,src=fixture();before=execute(model+w.LUA_JSON+'\nreturn json(score:raw())')
    data=t.validate(proposal(),src,2,2);result=execute(model+t.writer(data,src,2,2)+'\nreturn json(score:raw())')
    self.assertEqual(result['count'],6);self.assertEqual(result['title'],before['title'])
    for old,new in zip(before['staves'],result['staves']):
        for field in ('id','name','clef'):self.assertEqual(old[field],new[field])
        self.assertEqual(new['measures'][:2],old['measures'][:2])
        self.assertNotEqual(new['measures'][2]['entries'],old['measures'][2]['entries'])
        self.assertEqual(len(new['measures']),6)
    self.assertIn({'first':'a','last':'b'},result['slurs'])
    self.assertNotIn({'first':'tail13','last':'tail14'},result['slurs'])
    self.assertEqual(len(result['slurs']),2)
    self.assertEqual(result['staves'][0]['measures'][2]['dynamics'],[{'tick':0,'marking':'p'}])
    self.assertEqual(result['staves'][0]['measures'][3]['dynamics'],[])
    self.assertEqual(len(result['staves'][0]['measures'][3]['hairpins']),1)
 def test_two_three_and_four_tail_bars(self):
    model,src=fixture()
    for tail in (2,3,4):
        with self.subTest(tail=tail):
            result=execute(model+t.writer(proposal(tail,1),src,tail,1)+'\nreturn json(score:raw())')
            self.assertEqual(result['count'],5)
            self.assertEqual(t.plan(src,tail)['first'],5-tail)
 def test_cross_boundary_curve_rejected_before_paid_call(self):
    _,src=fixture("music.slurs={{first='c',last='tail13'}}\n")
    with patch.object(a,'query_model') as query:
        with self.assertRaisesRegex(c.ScoreError,'Auswahlgrenze'):f.run(a,self.body(),src)
        query.assert_not_called()
 def test_invalid_counts_and_short_score(self):
    _,src=fixture()
    for count in (-1,1,5,2.0,True,'2',None):
        with self.subTest(count=count),self.assertRaises(c.ScoreError):t.plan(src,count)
    short=copy.deepcopy(src);short['measure_count']=1
    with self.assertRaises(c.ScoreError):t.plan(short,2)
    with self.assertRaises(c.ScoreError):t.validate(proposal(),src,2,1023)
 def test_invalid_generated_count_meter_rhythm_and_tempo(self):
    _,src=fixture()
    for kind in ('count','meter','rhythm','tempo'):
        data=proposal()
        if kind=='count':
            for st in data['staves']:st['bars'].pop()
        if kind=='meter':
            data['time']=[1,2] # same duration, wrong notation of the existing meter
        if kind=='rhythm':data['staves'][0]['bars'][0]['voices']=[[['q',['C4']]]]
        if kind=='tempo':data['staves'][0]['directions']=[{'kind':'tempo','from':[1,1,1],'bpm':90}]
        with self.subTest(kind=kind),self.assertRaises(c.ScoreError):t.validate(data,src,2,2)
 def test_incoming_tie_requires_matching_first_note(self):
    _,src=fixture("music.staves[1].measures[2].entries[1].tied=true\n")
    with self.assertRaisesRegex(c.ScoreError,'eingehende'):t.validate(proposal(),src,2,2)
    data=proposal();data['staves'][0]['bars'][0]['voices'][0][0][1]=['E4']
    self.assertTrue(t.validate(data,src,2,2))
 def test_existing_tail_text_lines_and_system_text_are_removed(self):
    model,src=fixture('''music.staves[1].measures[3].texts={{text='fine',tick=0}}
music.staves[1].measures[3].hairpins={{first='tail13',last='tail14',tick=0}}
music.systemTexts={{measure=1,tick=0,text='Allegro'},{measure=4,tick=0,text='rit.'}}
''')
    result=execute(model+t.writer(proposal(),src,2,2)+'\nreturn json(score:raw())')
    self.assertEqual(result['systemTexts'],[{'measure':1,'tick':0,'text':'Allegro'}])
    self.assertEqual(result['staves'][0]['measures'][2]['texts'],[])
    self.assertEqual(result['staves'][0]['measures'][2]['hairpins'],[])
 def test_unsafe_line_and_structure_rejected(self):
    for extra in ("music.staves[1].measures[2].hairpins={{first='c',last='tail13',tick=0}}\n", "music.staves[1].measures[2].pedals={{tick=0,endTick=7000}}\n", "music.measureMarks={{measure=4,kind='repeatEnd'}}\n"):
        _,src=fixture(extra)
        with self.assertRaises(c.ScoreError):t.plan(src,2)
 def test_changed_source_or_corrupted_prefix_rolls_back(self):
    model,src=fixture();code=t.writer(proposal(),src,2,2)
    with self.assertRaisesRegex(RuntimeError,'seit dem Einlesen'):execute(model+'music.title="Changed"\n'+code+'\nreturn "null"')
    corrupt='local append=methods.appendMeasures;function methods:appendMeasures(n)append(self,n);music.staves[1].measures[1].entries[1].pitches={"G4"}end\n'
    with self.assertRaisesRegex(RuntimeError,'vor dem Uebergang'):execute(model+corrupt+code+'\nreturn "null"')
 def body(self):return {'mode':'continue','transition_bars':2,'bars':2,'provider':'Test','model':'m','key':'secret','task':'Fortsetzen'}
 def test_workflow_prompt_saves_original_and_only_explicit_apply_writes(self):
    model,src=fixture();calls=[]
    class Client:
        def connect(self):return {},[{'name':'run_script','inputSchema':{'properties':{k:{'type':v} for k,v in [('score_id','string'),('code','string'),('read_only','boolean')]}}}]
        def tool(self,name,args):
            calls.append((name,dict(args)))
            if name=='run_script':
                result=execute(model+args['code']+'\nreturn json(score:raw())')
                return {'content':[{'type':'text','text':'WORKSPACE_APPLIED' if not args['read_only'] else 'validated'}]}
            return {}
        def close(self):pass
    with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'MAESTRO_DATA_DIR':folder}),patch.object(a,'mcp_for_app',side_effect=lambda _:Client()),patch.object(a,'query_model',return_value={'answer':json.dumps(proposal()),'provider':'Test','model':'m'}) as query:
        before=copy.deepcopy(src);record=f.run(a,self.body(),src)
        self.assertIsNone(record['validation_error']);self.assertEqual(src,before)
        prompt=json.loads(query.call_args.args[4]);self.assertEqual(prompt['Taktzahl'],4)
        self.assertEqual(prompt['Uebergang']['erster_Bestandstakt'],3)
        self.assertEqual(prompt['Uebergang']['neue_Takte'],2)
        saved=json.loads(Path(record['saved_path']).read_text());self.assertEqual(saved['source'],src)
        self.assertFalse(any(not args.get('read_only',True) for name,args in calls))
        loaded=h.open_record(a,Path(record['saved_path']).name)
        self.assertEqual(loaded['transition_bars'],2);self.assertEqual(loaded['bars'],2)
        f.apply(a,loaded,'wrong-score','')
        writes=[args for name,args in calls if name=='run_script' and 'WORKSPACE_APPLIED' in args['code']]
        self.assertEqual(len(writes),2);self.assertTrue(writes[0]['read_only']);self.assertFalse(writes[1]['read_only'])
        self.assertEqual(writes[0]['code'],writes[1]['code']);self.assertEqual(writes[1]['score_id'],'bound-score')
        with self.assertRaisesRegex(c.ScoreError,'bereits angewendet'):f.apply(a,loaded,'wrong','')
        reloaded=f.load(a,json.dumps(loaded),save=False)
        with self.assertRaisesRegex(c.ScoreError,'bereits angewendet'):f.apply(a,reloaded,'wrong','')
 def test_invalid_answer_is_saved_and_unappliable(self):
    _,src=fixture()
    with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'MAESTRO_DATA_DIR':folder}),patch.object(f,'assert_current'),patch.object(a,'query_model',return_value={'answer':json.dumps(fragment(2,2)),'provider':'Test','model':'m'}):
        record=f.run(a,self.body(),src)
        self.assertTrue(record['validation_error']);self.assertEqual(record['source'],src)
        self.assertTrue(Path(record['saved_path']).exists())
        with self.assertRaises(c.ScoreError):f.apply(a,record,'wrong','')
 def test_loaded_transition_cannot_expand_authorized_tail(self):
    _,src=fixture();record={'mode':'continue','source':src,'composition':proposal(),'transition_bars':1,'bars':2}
    with self.assertRaises(c.ScoreError):f.load(a,json.dumps(record),save=False)
 def test_save_failure_prevents_any_maestro_write(self):
    _,src=fixture();record={'mode':'continue','source':src,'composition':proposal(),'transition_bars':2,'bars':2}
    with patch.object(a,'save_composition',return_value=None),patch.object(a,'mcp_for_app') as client:
        with self.assertRaisesRegex(c.ScoreError,'Sicherung'):f.apply(a,record,'wrong','')
        client.assert_not_called()
 def test_original_continuation_still_appends_without_tail_rewrite(self):
    model,src=fixture();data=f.prepare_score(fragment(2,2),'continue',src,[],2)
    result=execute(model+w.score_lua(data,'continue',src)+'\nreturn json(score:raw())')
    before=execute(model+w.LUA_JSON+'\nreturn json(score:raw())')
    for old,new in zip(before['staves'],result['staves']):self.assertEqual(old['measures'],new['measures'][:4])

if __name__=='__main__':unittest.main()
