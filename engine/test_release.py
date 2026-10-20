"""Release regressions: current surfaces and v3 merge recovery rules."""
import copy,json,pathlib,re,unittest
import composition,score_response
from test_workspace import fragment
ROOT=pathlib.Path(__file__).resolve().parent
class ReleaseTests(unittest.TestCase):
 def test_surfaces_have_identical_controls_and_current_version(self):
  pages=[(ROOT/'ui'/name).read_text(encoding='utf-8') for name in ('mac.html','windows.html')]
  self.assertEqual(*[set(re.findall(r'id="([^"]+)"',p)) for p in pages])
  for page in pages:
   self.assertIn('Maestro · 3.0.0 · 20.10.2026',page)
   self.assertIn("r.warnings.join",page)
 def test_invalid_optional_annotation_warns_without_changing_notes(self):
  value=fragment();value['staves'][0]['slurs']=[[1,1,1,99,1,1]]
  warnings=[];result=composition.validate(value,warnings)
  self.assertEqual(len(warnings),1)
  self.assertEqual(result['staves'][0]['bars'][0]['voices'][0][0][1],['F4'])
 def test_nested_second_voice_preserves_events(self):
  value=fragment(staves=1);value['staves'][0]['bars'][0]['voices']=[[['h',['F4']],[['h',['A3']]]]]
  warnings=[];fixed=score_response.decode(json.dumps(value),warnings)
  checked=composition.validate(fixed)
  self.assertEqual(len(checked['staves'][0]['bars'][0]['voices']),2);self.assertTrue(warnings)
 def test_truncated_answer_does_not_invent_music(self):
  with self.assertRaises(ValueError):score_response.decode(json.dumps(fragment())[:-20],[])
 def test_native_assembly_version(self):
  self.assertIn('<Version>3.0.0</Version>',(ROOT.parent/'windows/desktop/MaestroDesktop.csproj').read_text(encoding='utf-8'))
