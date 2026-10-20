import base64,json,pathlib,tempfile,unittest
from unittest.mock import patch
import preferences as p
import maestro_analyse as a

class Tests(unittest.TestCase):
 def setUp(self):
  # DPAPI adapter unit tests; Keychain has its own host test suite.
  platform=patch.object(p.sys,'platform','win32');platform.start();self.addCleanup(platform.stop)
 def test_no_plaintext_key_and_provider_profiles(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(p,'settings_path',return_value=pathlib.Path(folder)/'settings.json'):
   with patch.object(p,'crypt',side_effect=lambda data,decrypt=False: b'sealed' if not decrypt else b'secret'):
    p.save({'provider':'Google','model':'one','key':'secret','remember':True})
    text=p.settings_path().read_text();self.assertNotIn('secret',text)
    self.assertEqual(p.load()['profiles']['Google']['key'],'secret')
    p.save({'provider':'OpenAI','model':'two','key':'session-only','remember':False})
    self.assertNotIn('session-only',p.settings_path().read_text())
    self.assertEqual(p.load()['profiles']['Google']['model'],'one')
    p.save({'provider':'Google','model':'one','key':'secret','remember':False})
    self.assertNotIn('protected_key',p.settings_path().read_text())
    self.assertEqual(p.load()['profiles']['Google']['key'],'')
 def test_protection_failure_never_falls_back_to_plaintext(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(p,'settings_path',return_value=pathlib.Path(folder)/'settings.json'),patch.object(p,'crypt',side_effect=ValueError('DPAPI unavailable')):
   with self.assertRaises(ValueError):p.save({'provider':'Google','key':'secret','remember':True})
   self.assertFalse(p.settings_path().exists())
 def test_transition_option_survives_restart_with_validated_count(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(p,'settings_path',return_value=pathlib.Path(folder)/'settings.json'):
   for tail in (2,3,4):
    p.save({'provider':'Google','workspace':{'transitionEnabled':True,'transitionBars':tail}})
    loaded=p.load()['workspace'];self.assertTrue(loaded['transitionEnabled']);self.assertEqual(loaded['transitionBars'],tail)
   p.save({'provider':'Google','workspace':{'transitionEnabled':False,'transitionBars':500}})
   self.assertFalse(p.load()['workspace']['transitionEnabled']);self.assertEqual(p.load()['workspace']['transitionBars'],2)
 def test_target_inspection_is_bound_and_readonly(self):
  class Client:
   def __init__(self):self.calls=[]
   def connect(self):pass
   def tool(self,name,args):
    self.calls.append((name,args))
    if name=='list_open_scores':return {'scores':[{'score_id':'blank','title':'Neu'},{'score_id':'full','title':'Original'},{'score_id':'unknown','title':'Unbekannt'}]}
    if name=='run_script':
     if args['score_id']=='unknown':raise a.UserError('Nicht verfügbar')
     return {'content':[{'type':'text','text':'MAESTRO_TARGET:2:'+('0' if args['score_id']=='blank' else '20')}]}
    return {}
   def close(self):pass
  client=Client()
  with patch.object(a,'mcp_for_app',return_value=client):scores=a.list_targets()
  self.assertTrue(scores[0]['empty']);self.assertFalse(scores[1]['empty']);self.assertNotIn('empty',scores[2])
  calls=[args for name,args in client.calls if name=='run_script']
  self.assertEqual([x['score_id'] for x in calls],['blank','full','unknown'])
  self.assertTrue(all(x['read_only'] for x in calls))

if __name__=='__main__':unittest.main()
