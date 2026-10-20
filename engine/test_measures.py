"""Regression tests against independent Lua score model (not a live Maestro)."""
import ctypes,ctypes.util,json,unittest
from unittest.mock import patch
import composition as c
import maestro_analyse as a

MODEL=r'''
local noteAt={{},{}}
score={measureCount=32,staves={{},{}},beats=4,denom=4}
local function sync(n)
 score.measureCount=n
 for si,staff in ipairs(score.staves) do
  staff.measures={}
  for i=1,n do
   local s,b=si,i
   local m={}
   function m:entries()
    local used=false
    return function() if not used and noteAt[s][b] then used=true;return {isNote=true} end end
   end
   staff.measures[i]=m
  end
 end
end
sync(32)
function score:entries() return function() return nil end end
function score:setTime(b,d)
 sync(math.ceil(self.measureCount*(self.beats/self.denom)/(b/d)))
 self.beats=b;self.denom=d
end
function score:setKey() end
function score:appendMeasures(n) sync(self.measureCount+n) end
function score:deleteMeasures(first,last)
 if ignoreDelete then return end
 assert(first>=1 and last<=self.measureCount and first<=last)
 for _,notes in ipairs(noteAt) do for i=first,last do assert(not notes[i],"deleting music") end end
 sync(self.measureCount-(last-first+1))
end
'''

class Lua:
 def __init__(self):
  name=ctypes.util.find_library('lua5.4')
  if not name:raise unittest.SkipTest('Lua 5.4 shared library not installed')
  self.lib=ctypes.CDLL(name);l=self.lib
  l.luaL_newstate.restype=ctypes.c_void_p
  l.luaL_openlibs.argtypes=[ctypes.c_void_p]
  l.luaL_loadstring.argtypes=[ctypes.c_void_p,ctypes.c_char_p];l.luaL_loadstring.restype=ctypes.c_int
  l.lua_pcallk.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ssize_t,ctypes.c_void_p];l.lua_pcallk.restype=ctypes.c_int
  l.lua_tolstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p];l.lua_tolstring.restype=ctypes.c_char_p
  l.lua_close.argtypes=[ctypes.c_void_p]
 def run(self,code):
  l=self.lib;state=l.luaL_newstate();l.luaL_openlibs(state)
  try:
   result=l.luaL_loadstring(state,code.encode())
   if result==0:result=l.lua_pcallk(state,0,0,0,0,None)
   if result:raise RuntimeError(l.lua_tolstring(state,-1,None).decode())
  finally:l.lua_close(state)

class Tests(unittest.TestCase):
 def prefix(self):
  bar={'voices':[[['h',['C4']]]]}
  score={'title':'Test','time':[2,4],'key':[2,'major'],'tempo':116,'staves':[
   {'name':'Piano','clef':clef,'bars':[bar]*16} for clef in ['treble','bass']]}
  text=c.lua_writer(score)
  return text[text.index('score:setTime(2,4,1)'):text.index('score.title=')]
 def test_meter_reflow_before_resize(self):
  Lua().run(MODEL+self.prefix()+'\nassert(score.measureCount==16);assert(#score.staves[2].measures==16)')
 def test_failed_resize_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'Taktzahl stimmt nicht'):
   Lua().run(MODEL+'ignoreDelete=true\n'+self.prefix())
 def test_tail_trim_preserves_last_note_in_either_staff(self):
  Lua().run(MODEL+'noteAt[1][16]=true;noteAt[2][20]=true\n'+c.trim_empty_tail_lua()+'\nassert(score.measureCount==20);assert(noteAt[2][20])')
 def test_empty_score_not_trimmed(self):
  with self.assertRaisesRegex(RuntimeError,'keine Noten'):Lua().run(MODEL+c.trim_empty_tail_lua())
 def test_trim_rejects_failed_deletion(self):
  with self.assertRaisesRegex(RuntimeError,'nicht wie erwartet'):Lua().run(MODEL+'noteAt[1][16]=true;ignoreDelete=true\n'+c.trim_empty_tail_lua())
 def test_trim_mcp_dry_run_then_commit(self):
  class Client:
   def __init__(self,fail=False):self.calls=[];self.fail=fail
   def connect(self):return {},[{'name':'run_script','inputSchema':{'properties':{k:{'type':v} for k,v in [('score_id','string'),('code','string'),('read_only','boolean')]}}}]
   def tool(self,name,args):
    self.calls.append((name,dict(args)))
    if name=='run_script' and self.fail:raise a.UserError('Failed preflight')
    return {'content':[{'type':'text','text':'MAESTRO_TRIM:32:16'}]}
   def close(self):pass
  client=Client()
  with patch.object(a,'mcp_for_app',return_value=client):self.assertEqual(a.trim_empty_tail('target')['removed'],16)
  self.assertTrue(client.calls[1][1]['read_only']);self.assertFalse(client.calls[2][1]['read_only'])
  self.assertEqual(client.calls[2][1]['score_id'],'target')
  client=Client(True)
  with patch.object(a,'mcp_for_app',return_value=client):
   with self.assertRaises(a.UserError):a.trim_empty_tail('target')
  self.assertEqual(len(client.calls),2)

if __name__=='__main__':unittest.main()
