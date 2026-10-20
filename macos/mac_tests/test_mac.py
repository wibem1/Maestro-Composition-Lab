import copy,json,os,pathlib,subprocess,sys,tempfile,time,types,unittest,urllib.error,urllib.request
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'mac_host'),str(ROOT.parent/'engine')]
import backend,native_core as n,preferences as p,mac_keys,maestro_analyse as a
from test_workspace import fragment

class Tests(unittest.TestCase):
 def test_data_folder_and_exact_navigation_origin(self):
  self.assertEqual(n.data_folder('/Users/Wilhelm'),pathlib.Path('/Users/Wilhelm/Library/Application Support/Maestro-Composition-Lab'))
  base='http://127.0.0.1:45678/'
  self.assertTrue(n.own_page(base,base));self.assertTrue(n.own_page(base+'index.html',base))
  for url in ('http://127.0.0.1:123/','http://localhost:45678/','https://127.0.0.1:45678/','http://127.0.0.1:45678.attacker.test/','http://user@127.0.0.1:45678/','file:///etc/passwd','https://example.com',None):self.assertFalse(n.own_page(url,base))
 def test_json_and_clipboard_bridge_is_bounded_and_preserves_unicode(self):
  value=n.bridge_message({'type':'save-json','name':'../../Gänseliesel.json','text':'{"title":"Gänseliesel"}'})
  self.assertEqual(value['name'],'Gänseliesel.json');self.assertEqual(json.loads(value['text'])['title'],'Gänseliesel')
  self.assertEqual(n.bridge_message({'type':'copy','text':'♯ → ♭'})['text'],'♯ → ♭')
  for bad in ({'type':'exec','text':'x'},{'type':'save-json','text':'invalid'},{'type':'copy','text':123}):
   with self.assertRaises(ValueError):n.bridge_message(bad)
 def test_open_bom_json_with_native_filename(self):
  with tempfile.TemporaryDirectory() as folder:
   path=pathlib.Path(folder)/'Arbeitsstand.json';path.write_text(json.dumps({'composition':fragment()}),encoding='utf-8-sig')
   value=n.open_json(path);self.assertEqual(value['type'],'open-composition');self.assertIn('composition',json.loads(value['text']))
 def test_native_host_starts_real_engine_with_spaces_and_saves_outside_app(self):
  with tempfile.TemporaryDirectory(prefix='Maestro Mac ä ') as folder:
   data=pathlib.Path(folder)/'Benutzerdaten';b=backend.Backend(sys.executable,ROOT.parent/'engine/maestro_analyse.py',data)
   b.start();proc=b.process
   try:
    self.assertEqual(b.request('desktop/info',{})['version'],'3.0.0')
    result=b.request('workspace/load',{'text':json.dumps({'composition':fragment()})})
    self.assertTrue(pathlib.Path(result['saved_path']).is_relative_to(data))
    self.assertEqual(b.request('workspace/history',{})['total'],1)
    with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(b.url+'desktop/info',data=b'{}')
    b.request('preferences/save',{'provider':'Google','key':'secret-not-saved','remember':False,'workspace':{'transitionEnabled':True,'transitionBars':4}})
    self.assertNotIn('secret-not-saved',(data/'settings.json').read_text())
    self.assertEqual(b.request('preferences/load',{})['workspace']['transitionBars'],4)
   finally:b.stop()
   self.assertIsNotNone(proc.poll());self.assertIsNone(b.process)
 def test_service_exits_when_native_parent_disappears(self):
  import socket
  with tempfile.TemporaryDirectory() as folder:
   script=pathlib.Path(folder)/'parent.py'
   script.write_text('import sys,time,json\nsys.path.insert(0,'+repr(str(ROOT/'mac_host'))+')\nfrom backend import Backend\nb=Backend(sys.executable,'+repr(str(ROOT.parent/'engine/maestro_analyse.py'))+','+repr(str(pathlib.Path(folder)/'data'))+')\nb.start()\nprint(json.dumps({"pid":b.process.pid,"url":b.url}),flush=True)\ntime.sleep(30)')
   parent=subprocess.Popen([sys.executable,str(script)],stdout=subprocess.PIPE,text=True)
   try:
    info=json.loads(parent.stdout.readline());port=urllib.parse.urlsplit(info['url']).port
    parent.terminate();parent.wait(timeout=3)
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
     try:
      connection=socket.create_connection(('127.0.0.1',port),timeout=0.2);connection.close();time.sleep(0.1)
     except OSError:break
    else:self.fail('Local service survived its native parent')
   finally:
    if parent.poll() is None:parent.kill();parent.wait()
    parent.stdout.close()
 def test_malformed_start_handshake_stops_process(self):
  with tempfile.TemporaryDirectory() as folder:
   script=pathlib.Path(folder)/'bad.py';script.write_text('print(\'MAESTRO_DESKTOP {"url":"https://example.com/","token":"abcdefghijklmnop"}\',flush=True)\nimport time;time.sleep(30)')
   b=backend.Backend(sys.executable,script,pathlib.Path(folder)/'data')
   with self.assertRaises(RuntimeError):b.start()
   self.assertIsNone(b.process)
 def test_missing_engine_has_clear_error(self):
  b=backend.Backend(sys.executable,'/no-such-engine.py','/unused')
  with self.assertRaisesRegex(RuntimeError,'unvollständig'):b.start()
 def test_mac_keychain_preferences_keep_secrets_off_disk(self):
  keys={}
  with tempfile.TemporaryDirectory() as folder,patch.object(p,'settings_path',return_value=pathlib.Path(folder)/'settings.json'),patch.object(p.sys,'platform','darwin'),patch.object(mac_keys,'store',side_effect=lambda provider,key:(keys.update({provider:key}) or provider)),patch.object(mac_keys,'load',side_effect=lambda provider:keys.get(provider,'')),patch.object(mac_keys,'delete',side_effect=lambda provider:keys.pop(provider,None)):
   p.save({'provider':'Google','key':'private-api-key','remember':True})
   self.assertNotIn('private-api-key',p.settings_path().read_text());self.assertEqual(p.load()['profiles']['Google']['key'],'private-api-key');self.assertTrue(p.load()['can_protect'])
   p.save({'provider':'Google','key':'private-api-key','remember':False})
   self.assertFalse(keys);self.assertEqual(p.load()['profiles']['Google']['key'],'')
 def test_mac_keychain_failure_never_falls_back_to_plaintext(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(p,'settings_path',return_value=pathlib.Path(folder)/'settings.json'),patch.object(p.sys,'platform','darwin'),patch.object(mac_keys,'store',side_effect=ValueError('Keychain unavailable')):
   with self.assertRaises(ValueError):p.save({'provider':'Google','key':'secret','remember':True})
   self.assertFalse(p.settings_path().exists())
 def test_native_security_api_add_update_lookup_delete(self):
  values={};s=types.SimpleNamespace(**{k:k for k in ('kSecClass','kSecClassGenericPassword','kSecAttrService','kSecAttrAccount','kSecValueData','kSecReturnData','kSecMatchLimit','kSecMatchLimitOne')},errSecSuccess=0,errSecDuplicateItem=-25299,errSecItemNotFound=-25300)
  def add(q,_):
   key=q[s.kSecAttrAccount]
   if key in values:return -25299,None
   values[key]=q[s.kSecValueData];return 0,None
  s.SecItemAdd=add
  def update(q,v):values[q[s.kSecAttrAccount]]=v[s.kSecValueData];return 0
  s.SecItemUpdate=update;s.SecItemCopyMatching=lambda q,_:(0,values[q[s.kSecAttrAccount]]) if q[s.kSecAttrAccount] in values else (-25300,None)
  s.SecItemDelete=lambda q:(values.pop(q[s.kSecAttrAccount],None) is not None and 0 or 0)
  data=types.SimpleNamespace(dataWithBytes_length_=lambda data,length:data[:length])
  with patch.object(mac_keys,'frameworks',return_value=(s,data)):
   mac_keys.store('Google','secret');self.assertEqual(mac_keys.load('Google'),'secret')
   mac_keys.store('Google','new-secret');self.assertEqual(mac_keys.load('Google'),'new-secret')
   mac_keys.delete('Google');self.assertEqual(mac_keys.load('Google'),'')
 def test_discover_maestro_in_user_applications(self):
  with tempfile.TemporaryDirectory() as folder,patch('pathlib.Path.home',return_value=pathlib.Path(folder)),patch.object(a.shutil,'which',return_value=None):
   exe=pathlib.Path(folder)/'Applications/Maestro.app/Contents/MacOS/maestro-script';exe.parent.mkdir(parents=True);exe.touch()
   found,checked=a.discover_maestro(windows=False);self.assertEqual(found,str(exe))

if __name__=='__main__':unittest.main()
