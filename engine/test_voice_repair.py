import json
import unittest
import workflows

class VoiceRepairTests(unittest.TestCase):
    def source(self):
        bars=[{'voices':[[['h',['C4']],['q',['D4']]]]} for _ in range(16)]
        bars[14]={'voices':[[['q',['C4']],['q',['D4']],['q',['E4']]], [['w',['G3']]]]}
        return {'title':'Test','time':[3,4],'key':[0,'major'],'tempo':90,
                'staves':[{'name':'Piano','clef':'treble','bars':bars}]}
    def record(self,original):
        return {'id':'orig','mode':'compose','validation_error':
                'System 1, Takt 15, Stimme 2: 3840/960 Viertel statt 2880/960.',
                'raw_response':json.dumps(original),'source':None,
                'ensemble':[{'name':'Piano','clef':'treble','program':0}],
                'bars':16,'transition_bars':0,'task':'Test'}
    def test_repairs_only_invalid_voice(self):
        original=self.source()
        class API:
            def query_model(self,*args,**kw):
                return {'answer':json.dumps({'voice':[['h',['G3']],['q',['A3']]]}),'usage':{}}
            def save_composition(self,r):return '/safe/new-version.json'
        result=workflows.repair(API(),self.record(original),
                               {'provider':'Google','key':'secret','model':'test','limit':8192})
        self.assertIsNone(result['validation_error'])
        self.assertEqual(result['repair_of'],'orig')
        revised=json.loads(result['raw_response'])
        self.assertEqual(revised['staves'][0]['bars'][14]['voices'][0],
                         original['staves'][0]['bars'][14]['voices'][0])
        self.assertEqual(original['staves'][0]['bars'][14]['voices'][1],[['w',['G3']]])
    def test_rejects_invalid_repair(self):
        original=self.source()
        class API:
            def query_model(self,*args,**kw):
                return {'answer':json.dumps({'voice':[['w',['G3']]]})}
            def save_composition(self,r):
                raise AssertionError('Must not save invalid result')
        with self.assertRaises(ValueError):
            workflows.repair(API(),self.record(original),
                             {'provider':'Google','key':'secret','model':'test'})
if __name__=='__main__':unittest.main()
