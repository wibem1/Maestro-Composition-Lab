"""Regression: Maestro permits whitespace-only staff labels."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import composition as c
import history as h
import maestro_analyse as a
import workflows as f
import workspace as w
from test_workspace import MODEL,execute,fragment

class Tests(unittest.TestCase):
 def setup_record(self,name=' '):
  model=MODEL+'\nmusic.staves[1].name='+w.lua(name)+'\n'
  src=execute(model+w.read_lua('all')+'\nreturn output[2]')|{'id':'snapshot','score_id':'bound-score'}
  raw=fragment();raw['staves'][0]['name']=name
  return model,{'id':'old','mode':'continue','source':src,'bars':1,'composition':None,'raw_response':json.dumps(raw),'validation_error':'Name oder Schlüssel in System 1 ungültig.'}
 def test_unnamed_source_has_local_label_without_source_changes(self):
  for name in ('',' ','\t\n','\u00a0'):
   with self.subTest(name=name):
    _,rec=self.setup_record(name);before=copy.deepcopy(rec)
    score=f.prepare_score(json.loads(rec['raw_response']),'continue',rec['source'],[],1)
    self.assertEqual(score['staves'][0]['name'],'System 1')
    self.assertEqual(rec,before)
 def test_recovery_and_lua_append_preserve_original_names_and_measures(self):
  model,rec=self.setup_record();before=execute(model+w.LUA_JSON+'\nreturn json(score:raw())')
  with patch.object(a,'query_model') as query,patch.object(a,'save_composition') as save:
   loaded=f.load(a,json.dumps(rec),save=False)
   query.assert_not_called();save.assert_not_called()
  self.assertIsNone(loaded['validation_error']);self.assertEqual(loaded['source'],rec['source'])
  self.assertEqual(loaded['raw_response'],rec['raw_response'])
  after=execute(model+w.score_lua(loaded['composition'],'continue',loaded['source'])+'\nreturn json(score:raw())')
  self.assertEqual(after['count'],3)
  for old,new in zip(before['staves'],after['staves']):
   self.assertEqual(old['name'],new['name']);self.assertEqual(old['measures'],new['measures'][:2])
 def test_history_recovers_without_modifying_file_or_calling_ai(self):
  _,rec=self.setup_record()
  with tempfile.TemporaryDirectory() as folder,patch.dict('os.environ',{'MAESTRO_DATA_DIR':folder}):
   directory=Path(folder)/'Ergebnisse';directory.mkdir();path=directory/'Komposition-old.json'
   path.write_text(json.dumps(rec));before=path.read_bytes()
   with patch.object(a,'query_model') as query,patch.object(a,'save_composition') as save:
    loaded=h.open_record(a,path.name)
    query.assert_not_called();save.assert_not_called()
   self.assertIsNone(loaded['validation_error']);self.assertEqual(path.read_bytes(),before)
   self.assertEqual(loaded['history_origin']['id'],'old')
 def test_other_invalid_music_is_still_blocked_and_inspectable(self):
  _,rec=self.setup_record();raw=json.loads(rec['raw_response']);raw['staves'][0]['bars'][0]['voices']=[[['q',['C4']]]]
  rec['raw_response']=json.dumps(raw)
  with self.assertRaises(c.ScoreError):f.load(a,json.dumps(rec),save=False)
  with tempfile.TemporaryDirectory() as folder,patch.dict('os.environ',{'MAESTRO_DATA_DIR':folder}):
   directory=Path(folder)/'Ergebnisse';directory.mkdir();(directory/'bad.json').write_text(json.dumps(rec))
   loaded=h.open_record(a,'bad.json');self.assertTrue(loaded['validation_error'])
   with self.assertRaises(c.ScoreError):f.apply(a,loaded,'bound-score','')
 def test_real_names_and_applied_guard_remain(self):
  _,rec=self.setup_record('Klavier rechts');rec['applied']=True
  loaded=f.load(a,json.dumps(rec),save=False)
  self.assertEqual(loaded['composition']['staves'][0]['name'],'Klavier rechts')
  with self.assertRaisesRegex(c.ScoreError,'bereits angewendet'):f.apply(a,loaded,'bound-score','')

if __name__=='__main__':unittest.main()
