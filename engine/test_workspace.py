import copy,ctypes,json,pathlib,tempfile,unittest
from unittest.mock import patch
import composition as c
import workspace as w
import workflows as f
import maestro_analyse as a
from test_measures import Lua

MODEL=r'''
local nextid=200
local function uid() nextid=nextid+1;return 'n'..nextid end
local function event(id,d,p) return {id=id,duration=d,pitches=p,articulations={},tied=false,layer=1} end
local music={title='Original',composer='Test',tempo=116,time={2,4},key={2,'major'},count=2,slurs={},glissandos={},staves={
 {id='s1',name='Klavier rechts',clef='treble',program=0,measures={{entries={event('a','q',{'C4'}),event('b','q',{'D4'})},dynamics={}},{entries={event('c','h',{'E4'})},dynamics={}}}},
 {id='s2',name='Klavier links',clef='bass',program=0,measures={{entries={event('d','h',{'C3'})},dynamics={}},{entries={event('e','h',{'G2'})},dynamics={}}}}
}}
local function duration(d)
 local base={breve=8,w=4,h=2,q=1,['8']=0.5,['16']=0.25,['32']=0.125,['64']=0.0625}
 local core=d:gsub('%.','');local dots=#d-#core;local factor=0;for i=0,dots do factor=factor+0.5^i end;return base[core]*factor*960
end
local function list(values)
 local out={};for _,data in ipairs(values or {}) do out[#out+1]={raw=function()return data end} end;return out
end
local function collection(values)
 local out={}
 for i,data in ipairs(values) do
  local proxy=setmetatable({raw=function()return data end,delete=function()for j,x in ipairs(values) do if x==data then table.remove(values,j);return end end end},{__index=data})
  out[#out+1]=proxy
 end
 function out:add(data) values[#values+1]=data end
 return out
end
local measureProxy,staffProxy,entryProxy
local function iterator(values)
 local i=0;return function()i=i+1;return values[i]end
end
entryProxy=function(data,measure)
 local methods={}
 function methods:raw()return data end
 function methods:setNotes(notes)data.pitches=notes end
 function methods:delete()local es=measure:raw().entries;for i,e in ipairs(es)do if e==data then table.remove(es,i);return end end end
 function methods:add(art)data.articulations[#data.articulations+1]=art end
 local proxy={}
 return setmetatable(proxy,{__index=function(_,key)
  if methods[key] then return methods[key] end
  if key=='notes' then local ns={};for _,p in ipairs(data.pitches)do ns[#ns+1]={name=p}end;return ns end
  if key=='measure' then return measure end
  if key=='isNote' then return #data.pitches>0 end
  if key=='isRest' then return #data.pitches==0 end
  if key=='isGrace' then return false end
  if key=='ticks' then return duration(data.duration)end
  if key=='tick' then local tick=0;for _,e in ipairs(measure:raw().entries)do if e==data then break end;if e.layer==data.layer then tick=tick+duration(e.duration)end end;return tick end
  return data[key]
 end,__newindex=function(_,key,value)data[key]=value end})
end
measureProxy=function(data,bi)
 local methods,proxy={},nil
 function methods:raw()return data end
 function methods:entries()local es={};for _,e in ipairs(data.entries)do es[#es+1]=entryProxy(e,proxy)end;return iterator(es)end
 function methods:clear(layer)if not layer then data.entries={};data.dynamics={} else for i=#data.entries,1,-1 do if data.entries[i].layer==layer then table.remove(data.entries,i)end end end end
 function methods:append(d,notes,layer)local e=event(uid(),d,notes or {});e.layer=layer or 1;data.entries[#data.entries+1]=e;return entryProxy(e,proxy)end
 proxy=setmetatable({},{__index=function(_,key)
  if methods[key] then return methods[key]end
  if key=='number' then return bi end
  if key=='ticks' then return music.time[1]*4/music.time[2]*960 end
  if key=='dynamics' then return collection(data.dynamics)end
  if key=='hairpins' or key=='texts' or key=='chords' or key=='octaves' or key=='pedals' or key=='textLines' then return {}end
  return data[key]
 end})
 return proxy
end
staffProxy=function(data)
 local methods={}
 function methods:raw()return data end
 function methods:delete()for i,s in ipairs(music.staves)do if s==data then table.remove(music.staves,i);return end end end
 function methods:setClef(clef) data.clef=clef end
 return setmetatable({},{__index=function(_,key)
  if methods[key]then return methods[key]end
  if key=='measures'then local ms={};for i,m in ipairs(data.measures)do ms[#ms+1]=measureProxy(m,i)end;return ms end
  return data[key]
 end,__newindex=function(_,key,value)data[key]=value end})
end
score={}
local methods={}
function methods:raw()return music end
function methods:entries()local es={};for _,s in ipairs(music.staves)do for bi,m in ipairs(s.measures)do local mp=measureProxy(m,bi);for _,e in ipairs(m.entries)do es[#es+1]=entryProxy(e,mp)end end end;return iterator(es)end
function methods:appendMeasures(n)for _,st in ipairs(music.staves)do for i=1,n do st.measures[#st.measures+1]={entries={},dynamics={}}end end;music.count=music.count+n end
function methods:deleteMeasures(first,last)for _,st in ipairs(music.staves)do for i=last,first,-1 do table.remove(st.measures,i)end end;music.count=music.count-(last-first+1)end
function methods:setTime(b,d,from)music.time={b,d}end
function methods:setKey(f,from,mode)music.key={f,mode}end
function methods:addStaff(options)local st={id=uid(),name=options.name,clef=options.clef,program=options.program,measures={}};for i=1,music.count do st.measures[i]={entries={},dynamics={}}end;music.staves[#music.staves+1]=st;return staffProxy(st)end
setmetatable(score,{__index=function(_,key)
 if methods[key]then return methods[key]end
 if key=='measureCount'then return music.count end
 if key=='staves'then local ss={};for _,s in ipairs(music.staves)do ss[#ss+1]=staffProxy(s)end;return ss end
 if key=='measures'then local ms={};for i=1,music.count do ms[i]={time=music.time,key=music.key}end;return ms end
 if key=='slurs' or key=='glissandos'then return collection(music[key])end
 return music[key]
end,__newindex=function(_,key,value)music[key]=value end})
selection={a=true,b=true}
function eachentry(region)local es={};for e in score:entries()do if region==score or (region and region[e.id])then es[#es+1]=e end end;return iterator(es)end
editor={perform=function(command,ends)assert(command=='slur');music.slurs[#music.slurs+1]={id=uid(),first=ends[1].id,last=ends[2].id}end}
local output={};print=function(...)local s={};for _,x in ipairs({...})do s[#s+1]=tostring(x)end;output[#output+1]=table.concat(s,' ')end
'''

def execute(code):
    runner=Lua();lib=runner.lib;state=lib.luaL_newstate();lib.luaL_openlibs(state)
    try:
        result=lib.luaL_loadstring(state,code.encode())
        if not result:result=lib.lua_pcallk(state,0,1,0,0,None)
        value=lib.lua_tolstring(state,-1,None)
        if result:raise RuntimeError(value.decode())
        return json.loads(value.decode())
    finally:lib.lua_close(state)

def source(scope='all'):
    return execute(MODEL+w.read_lua(scope)+'\nreturn output[2]')|{'id':'snapshot','score_id':'bound-score'}

def fragment(staves=2,bars=1):
    return {'title':'Neu','composer':'','time':[2,4],'key':[2,'major'],'tempo':116,'staves':[{'name':'Instrument '+str(i),'clef':'treble','program':i%128,'bars':[{'voices':[[['h',['F4']]]]} for _ in range(bars)],'slurs':[]} for i in range(staves)]}

class Tests(unittest.TestCase):
 def test_real_lua_export_full_and_selection(self):
  full=source();selected=source('selection')
  self.assertEqual(len(full['selected_ids']),5);self.assertEqual(selected['selected_ids'],['a','b'])
  self.assertEqual(full['measure_count'],2);self.assertTrue(full['guard']);self.assertIn('time',full['header'])
  response={'content':[{'type':'text','text':'BEGIN_MAESTRO_WORKSPACE'},{'type':'text','text':json.dumps(full)},{'type':'text','text':'END_MAESTRO_WORKSPACE'}]}
  self.assertEqual(w.parse_tool_result(response)['title'],'Original')
 def test_more_than_sixteen_systems_and_programs(self):
  data=fragment(20)
  result=execute(MODEL+'for _,s in ipairs(music.staves)do for _,m in ipairs(s.measures)do m.entries={}end end\n'+w.score_lua(data,'compose')+'\nreturn json(score:raw())')
  self.assertEqual(len(result['staves']),20);self.assertEqual(result['count'],1)
  self.assertEqual([s['program'] for s in result['staves']],list(range(20)))
 def test_matching_piano_template_preserves_staff_ids(self):
  data=fragment();data['staves'][1]['program']=0;data['staves'][1]['clef']='bass'
  blank='for _,s in ipairs(music.staves)do for _,m in ipairs(s.measures)do m.entries={}end end\n'
  result=execute(MODEL+blank+w.score_lua(data,'compose')+'\nreturn json(score:raw())')
  self.assertEqual([s['id'] for s in result['staves']],['s1','s2'])
 def test_local_time_signatures_validate_consistently(self):
  data=fragment(2,2)
  for st in data['staves']:st['bars'][1]={'time':[3,4],'voices':[[['h.',['C4']]]]}
  self.assertEqual(c.validate(data)['staves'][0]['bars'][1]['time'],[3,4])
  data['staves'][1]['bars'][1]={'voices':[[['h',['C4']]]]}
  with self.assertRaises(c.ScoreError):c.validate(data)
 def test_continuation_appends_and_preserves_original(self):
  src=source();data=fragment()
  result=execute(MODEL+w.score_lua(data,'continue',src)+'\nreturn json(score:raw())')
  self.assertEqual(result['count'],3);self.assertEqual(result['title'],'Original')
  for i,st in enumerate(src['staves']):
   for j,bar in enumerate(st['measures']):self.assertEqual(result['staves'][i]['measures'][j]['entries'],[e['raw'] for e in bar['entries']])
 def test_new_instrument_only_adds_new_staff(self):
  src=source();result=execute(MODEL+w.score_lua(fragment(1,2),'instruments',src)+'\nreturn json(score:raw())')
  self.assertEqual(len(result['staves']),3);self.assertEqual(result['count'],2)
  self.assertEqual(result['staves'][0]['measures'][0]['entries'][0]['pitches'],['C4'])
 def test_selected_pitch_patch_and_balanced_rhythm(self):
  src=source('selection');changes={'changes':[{'id':'a','pitches':['C#4'],'duration':'8'},{'id':'b','duration':'q.','dynamic':'p'}]}
  result=execute(MODEL+w.patch_lua(changes,src)+'\nreturn json(score:raw())')
  notes=result['staves'][0]['measures'][0]['entries'];self.assertEqual(notes[0]['pitches'],['C#4']);self.assertEqual(notes[1]['duration'],'q.')
  self.assertEqual(result['staves'][1]['measures'][0]['entries'][0]['pitches'],['C3'])
  self.assertEqual(result['staves'][0]['measures'][0]['dynamics'],[{'tick':480,'marking':'p'}])
 def test_scope_rhythm_and_stale_snapshot_rejected(self):
  src=source('selection')
  with self.assertRaises(c.ScoreError):w.patches({'changes':[{'id':'d','pitches':['D3']}]},src)
  with self.assertRaises(c.ScoreError):w.patches({'changes':[{'id':'a','duration':'8'}]},src)
  partial=copy.deepcopy(src);partial['selected_ids']=['a']
  with self.assertRaises(c.ScoreError):w.patches({'changes':[{'id':'a','duration':'8'},{'id':'b','duration':'q.'}]},partial)
  with self.assertRaisesRegex(RuntimeError,'seit dem Einlesen'):execute(MODEL+'music.title="Changed"\n'+w.score_lua(fragment(),'continue',source())+'\nreturn "null"')
 def test_conflict_after_append_rejected(self):
  broken='local append=methods.appendMeasures;function methods:appendMeasures(n)append(self,n);music.staves[1].measures[1].entries[1].pitches={"G4"}end\n'
  with self.assertRaisesRegex(RuntimeError,'Vorhandene Musik'):execute(MODEL+broken+w.score_lua(fragment(),'continue',source())+'\nreturn "null"')
 def test_workflow_request_and_response_validation(self):
  src=source();body={'mode':'instruments','provider':'Test','key':'secret','model':'m','task':'Flöte ergänzen','ensemble':[{'name':'Flöte','clef':'treble','program':73}],'bars':16,'limit':32768}
  reply={'answer':json.dumps(fragment(1,2)),'provider':'Test','model':'m','usage':{}}
  with patch.object(f,'assert_current'),patch.object(a,'query_model',return_value=reply) as query,patch.object(a,'save_composition',return_value='saved'):
   record=f.run(a,body,src);self.assertIsNone(record['validation_error']);self.assertEqual(record['composition']['staves'][0]['program'],73)
   user=json.loads(query.call_args.args[4]);self.assertIn('Neue_Besetzung',user);self.assertEqual(user['Taktzahl'],2)
   self.assertNotIn('secret',json.dumps(record))
  reply['answer']=json.dumps(fragment(1,1))
  with patch.object(f,'assert_current'),patch.object(a,'query_model',return_value=reply),patch.object(a,'save_composition',return_value='saved'):
   record=f.run(a,body,src);self.assertIn('statt 2',record['validation_error']);self.assertTrue(record['raw_response'])
 def test_apply_bound_source_preflight_and_commit(self):
  class Client:
   def __init__(self,fail=False):self.calls=[];self.fail=fail
   def connect(self):return {},[{'name':'run_script','inputSchema':{'properties':{k:{'type':v} for k,v in [('score_id','string'),('code','string'),('read_only','boolean')]}}}]
   def tool(self,name,args):
    self.calls.append((name,dict(args)))
    if name=='run_script' and self.fail:raise a.UserError('Conflict')
    return {'content':[{'type':'text','text':'WORKSPACE_APPLIED'}]}
   def close(self):pass
  record={'id':'r','mode':'continue','composition':fragment(),'source':source()}
  client=Client()
  with patch.object(a,'mcp_for_app',return_value=client),patch.object(a,'save_composition',return_value='saved'):f.apply(a,record,'wrong-ui-target','')
  self.assertTrue(client.calls[1][1]['read_only']);self.assertFalse(client.calls[2][1]['read_only']);self.assertEqual(client.calls[2][1]['score_id'],'bound-score')
  self.assertTrue(record['applied'])
  with self.assertRaises(c.ScoreError):f.apply(a,record,'wrong','')
  record.pop('applied');client=Client(True)
  with patch.object(a,'mcp_for_app',return_value=client),patch.object(a,'save_composition',return_value='saved'):
   with self.assertRaises(a.UserError):f.apply(a,record,None,'')
  self.assertEqual(len(client.calls),2)
 def test_stale_source_blocks_paid_request(self):
  body={'mode':'continue','provider':'Google','key':'key','model':'m','task':'Weiter','bars':4}
  with patch.object(f,'assert_current',side_effect=a.UserError('Partitur verändert')),patch.object(a,'query_model') as query:
   with self.assertRaises(a.UserError):f.run(a,body,source())
   query.assert_not_called()
 def test_old_json_import_still_supported(self):
  with patch.object(a,'save_composition',return_value='saved'):
   record=f.load(a,json.dumps({'composition':fragment(),'provider':'Google','model':'m'}))
  self.assertEqual(record['mode'],'compose');self.assertEqual(len(record['composition']['staves']),2)

if __name__=='__main__':unittest.main()
