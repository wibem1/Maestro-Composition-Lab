"""Expression routing in real Lua against an independent score/editor model.

This verifies our data path, not Maestro's synthesizer or its implementation.
"""
import copy,json,tempfile,pathlib,unittest
from unittest.mock import patch
import composition as c
import expression as x
import workspace as w
import replacement as r
import workflows as f
import maestro_analyse as api
from test_workspace import MODEL,execute,fragment

EXPRESS_MODEL=MODEL.replace("if key=='slurs' or key=='glissandos'","if key=='slurs' or key=='glissandos' or key=='systemTexts'").replace("return duration(data.duration)end", "return duration(data.duration)*(data.factor or 1)end").replace(
    "tick=tick+duration(e.duration)","tick=tick+duration(e.duration)*(e.factor or 1)").replace(
    "if key=='hairpins' or key=='texts' or key=='chords' or key=='octaves' or key=='pedals' or key=='textLines' then return {}end",
    "if key=='hairpins' or key=='texts' or key=='chords' or key=='octaves' or key=='pedals' or key=='textLines' then return collection(data[key] or {})end")+r'''
music.systemTexts={};local calls={}
editor.perform=function(command,region,options)
 calls[#calls+1]={command=command,options=options}
 local ends=region.id and {region} or region
 local a,b=ends[1],ends[#ends]
 if command=='tuplet' then
  local actual,normal=options.ratio:match('^(%d+):(%d+)$')
  for _,e in ipairs(ends)do e:raw().factor=tonumber(normal)/tonumber(actual)end
 elseif command=='slur' then music.slurs[#music.slurs+1]={first=a.id,last=b.id}
 elseif command=='glissando' or command=='wavyGlissando' then music.glissandos[#music.glissandos+1]={first=a.id,last=b.id}
 elseif command=='tempoMark' then
  music.systemTexts[#music.systemTexts+1]={text=options.text,tick=a.tick}
 else
  local collections={pedal='pedals',crescendo='hairpins',diminuendo='hairpins',textLine='textLines',text='texts',glissando='glissandos',octaveUp='octaves'}
  local key=collections[command] or 'texts'
  local bar=a.measure:raw();bar[key]=bar[key] or {}
  bar[key][#bar[key]+1]={kind=command,first=a.id,last=b.id,tick=a.tick,text=options and options.text,category=options and options.kind}
 end
 return true,'ok'
end
'''

def snapshot(scope='selection',extra=''):
    return execute(EXPRESS_MODEL+extra+w.read_lua(scope)+'\nreturn output[2]')|{'id':'snapshot','score_id':'bound-score'}

def expressive_score():
    score=fragment(2,2)
    score['staves'][0]['bars'][0]={'voices':[[['8',['C4']],['8',['D4']],['8',['E4']],['q',['G4'],['tenuto']]]],
        'tuplets':[{'voice':1,'start':1,'count':3,'ratio':[3,2]}],'dynamics':[[0,'pp'],[960,'mf']]}
    score['staves'][0]['bars'][1]={'voices':[[['q',['F4']],['q',['E4'],['fermata']]]]}
    score['staves'][0]['directions']=[
        {'kind':'crescendo','from':[1,1,1],'to':[1,1,4]},
        {'kind':'textLine','from':[1,1,4],'to':[2,1,2],'text':'rit.'},
        {'kind':'tempo','from':[2,1,1],'bpm':80,'text':'Meno mosso'},
        {'kind':'text','from':[1,1,1],'text':'dolce cantabile','category':'expression'},
        {'kind':'text','from':[2,1,1],'text':'pizz.','category':'technique'},
        {'kind':'arpeggio','from':[1,1,4]}]
    score['staves'][1]['directions']=[{'kind':'pedal','from':[1,1,1],'to':[2,1,1]}]
    return score

class Tests(unittest.TestCase):
    def test_expressive_composition_reaches_editor_with_exact_timing(self):
        score=expressive_score()
        code=w.score_lua(score,'compose')
        result=execute(EXPRESS_MODEL+'for _,st in ipairs(music.staves)do for _,m in ipairs(st.measures)do m.entries={}end end\n'+code+'\nreturn json({music=music,calls=calls})')
        events=result['music']['staves'][0]['measures'][0]['entries']
        for actual,expected in zip([e.get('factor',1) for e in events],[2/3,2/3,2/3,1]):self.assertAlmostEqual(actual,expected)
        commands=[d['command'] for d in result['calls']]
        self.assertEqual(commands,['tuplet','crescendo','textLine','tempoMark','text','text','arpeggio','pedal'])
        self.assertEqual(result['music']['systemTexts'][0]['text'],'Meno mosso ♩ = 80')
        self.assertEqual(result['music']['staves'][0]['measures'][0]['texts'][0]['text'],'dolce cantabile')
        self.assertEqual(result['music']['staves'][1]['measures'][0]['pedals'][0]['kind'],'pedal')

    def test_expression_roundtrip_and_legacy_data(self):
        value=c.validate(expressive_score())
        self.assertEqual(c.validate(value),value)
        self.assertEqual(c.parse_composition(json.dumps(value)),value)
        legacy=c.validate(fragment())
        self.assertNotIn('directions',legacy['staves'][0])
        with patch.object(api,'save_composition',return_value='saved'):
            record=f.load(api,json.dumps({'composition':value,'provider':'Test'}))
        self.assertEqual(record['composition'],value)

    def test_malformed_expression_and_injection_rejected_or_quoted(self):
        for change in [
            {'kind':'pedal','from':[0,1,1],'to':[2,1,1]},
            {'kind':'crescendo','from':[2,1,2],'to':[1,1,1]},
            {'kind':'tempo','from':[1,1,1],'bpm':float('nan')},
            {'kind':'text','from':[1,1,1],'text':'x','category':'execute'},
            {'kind':'os.execute','from':[1,1,1]},
            {'kind':'text','from':[1,1,1],'text':'x','code':'attack'}]:
            s=expressive_score();s['staves'][0]['directions']=[change]
            with self.assertRaises(c.ScoreError):c.validate(s)
        s=fragment(1,1);text='dolce "); os.execute("attack") --\n'
        s['staves'][0]['directions']=[{'kind':'text','from':[1,1,1],'text':text}]
        result=execute(EXPRESS_MODEL+'for _,st in ipairs(music.staves)do for _,m in ipairs(st.measures)do m.entries={}end end\n'+w.score_lua(s,'compose')+'\nreturn json(music)')
        self.assertEqual(result['staves'][0]['measures'][0]['texts'][0]['text'],text)

    def test_tuplet_overlaps_wrong_lengths_and_fractional_grid_rejected(self):
        for edit in ['overlap','count','ratio','length','fractional']:
            s=expressive_score();bar=s['staves'][0]['bars'][0];g=bar['tuplets'][0]
            if edit=='overlap':bar['tuplets'].append(copy.deepcopy(g))
            if edit=='count':g['count']=9
            if edit=='ratio':g['ratio']=[1,1]
            if edit=='length':g['ratio']=[3,1]
            if edit=='fractional':g['ratio']=[7,4]
            with self.assertRaises(c.ScoreError):c.validate(s)

    def test_failure_to_apply_tuplets_is_detected_before_commit(self):
        code=w.score_lua(expressive_score(),'compose')
        model=EXPRESS_MODEL+"local perform=editor.perform;editor.perform=function(cmd,r,o)if cmd=='tuplet'then return true end;return perform(cmd,r,o)end\n"
        with self.assertRaisesRegex(RuntimeError,'N-tolen'):
            execute(model+'for _,st in ipairs(music.staves)do for _,m in ipairs(st.measures)do m.entries={}end end\n'+code+'\nreturn "null"')

    def test_existing_score_expression_patch_and_selection_bounds(self):
        src=snapshot()
        value={'changes':[],'directions':[{'kind':'crescendo','from':'a','to':'b'},
                {'kind':'text','from':'a','text':'espressivo'},{'kind':'tempo','from':'a','bpm':104},{'kind':'glissando','from':'a','to':'b'}]}
        result=execute(EXPRESS_MODEL+w.patch_lua(value,src)+'\nreturn json(music)')
        self.assertEqual(result['staves'][0]['measures'][0]['hairpins'][0]['first'],'a')
        self.assertEqual(result['systemTexts'][0]['text'],'♩ = 104')
        self.assertEqual(result['glissandos'][0]['last'],'b')
        value['directions'][0]['to']='c'
        with self.assertRaisesRegex(c.ScoreError,'Auswahl'):w.patches(value,src)

    def test_replacement_supports_new_tuplets_and_expression(self):
        src=snapshot()
        data={'cells':[{'staff':1,'bar':1,'layer':1,
            'events':[['8',['C4']],['8',['D4']],['8',['E4']],['q',['G4']]],
            'tuplets':[{'voice':1,'start':1,'count':3,'ratio':[3,2]}]}],
            'directions':[{'kind':'pedal','from':[1,1,1,1],'to':[1,1,1,4]},
                {'kind':'text','from':[1,1,1,1],'text':'dolce'}]}
        result=execute(EXPRESS_MODEL+r.writer(data,src)+'\nreturn json(music)')
        self.assertEqual(len(result['staves'][0]['measures'][0]['entries']),4)
        self.assertEqual(result['staves'][0]['measures'][0]['pedals'][0]['kind'],'pedal')
        self.assertEqual(result['staves'][1]['measures'][0]['entries'],[e['raw'] for e in src['staves'][1]['measures'][0]['entries']])

    def test_snapshot_and_ai_context_include_global_tempo_and_expression(self):
        extra='music.systemTexts={{text="♩ = 80",measure=2,tick=0}};music.staves[1].measures[1].pedals={{tick=0,endTick=960}}\n'
        src=snapshot(extra=extra);context=w.ai_context(src)
        self.assertEqual(context['system_texts'][0]['text'],'♩ = 80')
        self.assertEqual(context['staves'][0]['measures'][0]['pedals'][0]['endTick'],960)

    def test_continuation_and_new_instruments_keep_expressions(self):
        src=snapshot('all')
        for mode,data in [('continue',expressive_score()),('instruments',fragment(1,2))]:
            if mode=='instruments':data['staves'][0]['directions']=[{'kind':'text','from':[1,1,1],'text':'pizz.','category':'technique'}]
            result=execute(EXPRESS_MODEL+w.score_lua(data,mode,src)+'\nreturn json(music)')
            if mode=='continue':self.assertEqual(len(result['systemTexts']),1)
            else:self.assertEqual(result['staves'][-1]['measures'][0]['texts'][0]['text'],'pizz.')

    def test_real_lua_error_never_causes_commit(self):
        class Client:
            def __init__(self):self.calls=[]
            def connect(self):return {},[{'name':'run_script','inputSchema':{'properties':{k:{'type':v} for k,v in [('code','string'),('score_id','string'),('read_only','boolean')]}}}]
            def tool(self,name,args):
                if name=='run_script':
                    self.calls.append(args.copy())
                    raise api.UserError('Maestro lehnt tempoMark ab')
                return {}
            def close(self):pass
        client=Client();record={'mode':'compose','composition':expressive_score()}
        with patch.object(api,'mcp_for_app',return_value=client),patch.object(api,'save_composition',return_value='saved'):
            with self.assertRaises(api.UserError):f.apply(api,record,'blank','')
        self.assertEqual(len(client.calls),1);self.assertTrue(client.calls[0]['read_only'])
        self.assertNotIn('applied',record)

if __name__=='__main__':unittest.main()
