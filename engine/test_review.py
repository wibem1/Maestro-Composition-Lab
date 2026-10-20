import copy,json,types,unittest
from unittest.mock import patch
import composition as c
import workflows as f
import replacement as r
import review
import maestro_analyse as a
from test_workspace import source

def analysis(scope='all'):
    return {'id':'analysis-1','mode':'analysis','task':'Prüfe die Stimmführung.',
        'answer':'Takt 1: Entwickle das Motiv und führe die Mittelstimme geschmeidiger.',
        'raw_response':'Unveränderte ursprüngliche Antwort','provider':'Kritiker','model':'Modell A','source':source(scope)}

class Tests(unittest.TestCase):
 def test_whole_score_analysis_produces_separate_bound_revision(self):
    original=analysis();before=copy.deepcopy(original)
    selected=copy.deepcopy(original['source']);selected['scope']='selection'
    result={'cells':[{'staff':p['staff'],'bar':p['bar'],'layer':p['layer'],'events':[['h',['C4']]]} for p in r.targets(selected)]}
    body={'provider':'Bearbeiter','key':'secret','model':'Modell B'}
    with patch.object(f,'assert_current') as guard,patch.object(a,'query_model',return_value={'answer':json.dumps(result)}) as query,patch.object(a,'save_composition',return_value='saved'):
        revision=review.create(a,body,original)
    self.assertEqual(original,before);self.assertEqual(revision['mode'],'revise')
    self.assertEqual(revision['revise_kind'],'replace');self.assertIsNone(revision['validation_error'])
    self.assertEqual(revision['source']['scope'],'selection')
    self.assertEqual(revision['source']['selected_ids'],original['source']['selected_ids'])
    self.assertEqual(revision['source']['score_id'],'bound-score');guard.assert_called_once()
    request=json.loads(query.call_args.args[4])
    self.assertEqual(request['Vorhandene_Analyse']['analysis'],original['answer'])
    self.assertEqual(len(request['Vorhandene_Partitur']['staves']),2)
    self.assertEqual(query.call_args.args[:3],('Bearbeiter','secret','Modell B'))
    self.assertNotIn('secret',json.dumps(revision));self.assertNotIn('applied',revision)
    self.assertEqual(revision['review_origin']['model'],'Modell A')

 def test_partial_analysis_falls_back_to_precise_patches(self):
    original=analysis('selection');original['source']['selected_ids']=['a'];original['source']['selected_entries']=original['source']['selected_entries'][:1]
    result={'explanation':'Gezielte Verbesserung','changes':[{'id':'a','articulations':['tenuto']}]}
    with patch.object(f,'assert_current'),patch.object(a,'query_model',return_value={'answer':json.dumps(result)}),patch.object(a,'save_composition',return_value='saved'):
        revision=review.create(a,{'provider':'Test','key':'k','model':'m'},original)
    self.assertEqual(revision['revise_kind'],'patch');self.assertEqual(revision['source']['selected_ids'],['a'])
    self.assertIsNone(revision['validation_error'])

 def test_stale_analysis_blocks_before_paid_request(self):
    with patch.object(f,'assert_current',side_effect=c.ScoreError('Partitur verändert')),patch.object(a,'query_model') as query:
        with self.assertRaisesRegex(c.ScoreError,'verändert'):review.create(a,{},analysis())
    query.assert_not_called()

 def test_missing_analysis_or_source_gives_clear_error(self):
    for value in [None,{'mode':'compose'},{'mode':'analysis','answer':'Vorschlag'},{'mode':'analysis','answer':''}]:
        with self.assertRaises(c.ScoreError):review.create(a,{},value)

 def test_dispatch_stores_revision_and_analysis_remains_loadable(self):
    original=analysis();server=types.SimpleNamespace(compositions={'analysis-1':original},workspaces={})
    revised={'id':'revision','source':{'id':'new-source'},'mode':'revise'}
    with patch.object(review,'create',return_value=revised):
        result=f.dispatch(server,'/workspace/review',{'id':'analysis-1'},a)
    self.assertIs(result,revised);self.assertIs(server.compositions['analysis-1'],original)
    self.assertEqual(server.workspaces['new-source'],revised['source'])

if __name__=='__main__':unittest.main()
