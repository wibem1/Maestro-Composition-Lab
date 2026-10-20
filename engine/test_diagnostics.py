import json,types,unittest
import diagnostics as d

class Tests(unittest.TestCase):
 def test_only_relevant_context_and_no_credentials(self):
    server=types.SimpleNamespace()
    report=d.record_error(server,'/workspace/run',{'mode':'continue','model':'Argon','key':'secret-value','body':{'notes':'large'},'task':'Fortsetzen'},ValueError('Fehler mit secret-value'))
    text=json.dumps(report)
    self.assertNotIn('secret-value',text);self.assertNotIn('notes',text)
    self.assertEqual(report['mode'],'continue');self.assertEqual(report['error_type'],'ValueError')
 def test_ui_report_preserves_backend_error_context(self):
    server=types.SimpleNamespace()
    d.record_error(server,'/workspace/run',{'model':'Argon','mode':'continue'},ValueError('Fehlertext'))
    d.report_ui(server,{'message':'Fehlertext','mode':'continue'})
    self.assertEqual(server.last_error['route'],'/workspace/run')
    self.assertEqual(server.last_error['model'],'Argon')
    d.report_ui(server,{'message':'Anderer UI-Fehler','mode':'compose'})
    self.assertEqual(server.last_error['route'],'ui')
 def test_malformed_request_is_still_diagnosable(self):
    server=types.SimpleNamespace();d.record_error(server,'/workspace/run',None,KeyError('source'))
    self.assertIn('source',server.last_error['message'])

if __name__=='__main__':unittest.main()
