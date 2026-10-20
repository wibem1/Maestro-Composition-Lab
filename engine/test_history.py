import copy,json,os,pathlib,tempfile,types,unittest
from unittest.mock import patch
import composition as c
import history as h
import workflows as f
import maestro_analyse as a
from test_workspace import source,fragment

class Tests(unittest.TestCase):
 def setUp(self):
    self.temp=tempfile.TemporaryDirectory();self.directory=pathlib.Path(self.temp.name)
    self.env=patch.dict(os.environ,{'MAESTRO_DATA_DIR':str(self.directory)});self.env.start()
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def save(self,id='one',mode='compose',**fields):
    value={'id':id,'mode':mode,'task':'Mein Auftrag','provider':'Google','model':'Argon',
           **({'composition':fragment()} if mode=='compose' else {'answer':'Eine Analyse'}),**fields}
    path=a.save_composition(value);self.assertTrue(path)
    return value,pathlib.Path(path)
 def test_empty_history_without_creating_folder(self):
    self.assertEqual(h.listing(a,{})['items'],[])
    self.assertFalse((self.directory/'Ergebnisse').exists())
 def test_old_and_new_results_search_filter_and_newest_first(self):
    first,p=self.save();os.utime(p,(100,100))
    second,q=self.save('two','analysis',source=source(),model='Claude',task='Mittelstimme prüfen')
    result=h.listing(a,{})
    self.assertEqual([x['id'] for x in result['items']],[q.name,p.name])
    self.assertEqual(result['items'][0]['title'],'Original')
    self.assertEqual(h.listing(a,{'query':'CLAUDE'})['total'],1)
    self.assertEqual(h.listing(a,{'query':'mittelstimme'})['items'][0]['mode'],'analysis')
    self.assertEqual(h.listing(a,{'mode':'compose'})['total'],1)
    self.assertEqual(h.listing(a,{'query':'unbekannt'})['total'],0)
 def test_reopen_composition_creates_no_duplicates_or_paid_calls(self):
    value,path=self.save(applied=True);original=path.read_bytes()
    with patch.object(a,'query_model') as query,patch.object(a,'save_composition') as save:
        for _ in range(2):
            loaded=h.open_record(a,path.name)
            self.assertEqual(loaded['composition'],c.validate(value['composition']))
            self.assertNotIn('applied',loaded)
        save.assert_not_called();query.assert_not_called()
    self.assertEqual(path.read_bytes(),original)
    self.assertEqual(h.listing(a,{})['total'],1)
 def test_analysis_reopen_normalizes_text_and_retains_source_and_origin(self):
    src=source();raw=r'E5 $\rightarrow$ D5'
    original,path=self.save('a','analysis',source=src,answer=raw,raw_response=raw)
    server=types.SimpleNamespace(compositions={},workspaces={})
    record=f.dispatch(server,'/workspace/history/open',{'id':path.name},a)
    self.assertEqual(record['answer'],'E5 → D5');self.assertEqual(record['raw_response'],raw)
    self.assertEqual(record['source'],src)
    self.assertIn(record['id'],server.compositions)
    self.assertIn(src['id'],server.workspaces)
    self.assertEqual(record['history_origin']['id'],'a')
 def test_old_bom_composition_without_mode_is_available(self):
    directory=self.directory/'Ergebnisse';directory.mkdir()
    path=directory/'altes-ergebnis.json';path.write_text(json.dumps({'composition':fragment(),'provider':'Import'}),encoding='utf-8-sig')
    self.assertEqual(h.listing(a,{})['items'][0]['kind'],'Komposition')
    self.assertEqual(h.open_record(a,path.name)['mode'],'compose')
 def test_failed_model_response_is_inspectable(self):
    record,path=self.save(composition=None,raw_response='{unvollständig',validation_error='Ungültige Notendaten')
    self.assertEqual(h.listing(a,{})['items'][0]['status'],'Prüfung fehlgeschlagen')
    loaded=h.open_record(a,path.name)
    self.assertEqual(loaded['raw_response'],'{unvollständig');self.assertTrue(loaded['validation_error'])
    with self.assertRaises(c.ScoreError):f.apply(a,loaded,'blank','')
 def test_cache_updates_and_file_removal(self):
    value,path=self.save();h.listing(a,{})
    value['composition']['title']='Neuer Titel';a.save_composition(value)
    self.assertEqual(h.listing(a,{})['items'][0]['title'],'Neuer Titel')
    path.unlink();self.assertEqual(h.listing(a,{})['total'],0)
 def test_pagination_is_complete(self):
    for i in range(55):self.save(str(i),'analysis')
    one=h.listing(a,{'limit':50});two=h.listing(a,{'offset':one['next_offset'],'limit':50})
    self.assertEqual(len(one['items']),50);self.assertEqual(len(two['items']),5)
    self.assertIsNone(two['next_offset']);self.assertEqual(len({x['id'] for x in one['items']+two['items']}),55)
 def test_corrupt_files_and_unsafe_names(self):
    _,path=self.save();path.write_text('{defekt')
    self.assertEqual(h.listing(a,{})['items'][0]['status'],'Nicht lesbar')
    with self.assertRaisesRegex(c.ScoreError,'beschädigt'):h.open_record(a,path.name)
    for name in ['../datei.json','a/b.json','..\\datei.json','',None,'file.txt']:
        with self.assertRaises(c.ScoreError):h.open_record(a,name)
    with self.assertRaisesRegex(c.ScoreError,'nicht mehr'):h.open_record(a,'fehlt.json')
 def test_atomic_save_preserves_old_record_on_failure(self):
    value,path=self.save();original=path.read_bytes();created=value['created']
    value['task']='Neuer Auftrag'
    with patch.object(os,'replace',side_effect=OSError('Testfehler')):
        self.assertIsNone(a.save_composition(value))
    self.assertEqual(path.read_bytes(),original)
    self.assertEqual(list(path.parent.glob('*.tmp')),[])
    self.assertEqual(value['created'],created)

if __name__=='__main__':unittest.main()
