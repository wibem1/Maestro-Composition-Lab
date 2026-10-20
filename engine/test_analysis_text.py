import json,unittest
from unittest.mock import patch
from analysis_text import readable
import workflows as f
import maestro_analyse as a
from test_workspace import source

class Tests(unittest.TestCase):
 def test_reported_arrows(self):
  self.assertEqual(readable(r'E5/F3 (Septime) $\rightarrow$ D5/F3 (Sexte) $\rightarrow$ C5/E3 (Dezime) $\rightarrow$ B4/D3'),
   'E5/F3 (Septime) → D5/F3 (Sexte) → C5/E3 (Dezime) → B4/D3')
 def test_math_wrappers_symbols_and_prose(self):
  self.assertEqual(readable(r'\(C\sharp\) → $B\flat$; \[\text{Verhältnis }\frac{3}{2}\]'), 'C♯ → B♭; Verhältnis 3/2')
  self.assertEqual(readable('C#4, Bb3: dolce → cantabile; Kosten 0,32 €.'),'C#4, Bb3: dolce → cantabile; Kosten 0,32 €.')
 def test_idempotent_and_plain_text_html(self):
  value=readable('## Harmonik\n**Klar:** $\\rightarrow$ <script>x</script>')
  self.assertEqual(value,'Harmonik\nKlar: → <script>x</script>')
  self.assertEqual(readable(value),value)
 def test_new_analysis_retains_raw_response(self):
  src=source();raw=r'Die Melodie: E5 $\rightarrow$ D5.'
  body={'mode':'analysis','task':'Beurteilen','provider':'Test','key':'secret','model':'m'}
  with patch.object(a,'query_model',return_value={'answer':raw}),patch.object(a,'save_composition',return_value='saved'):
   record=f.run(a,body,src)
  self.assertEqual(record['answer'],'Die Melodie: E5 → D5.')
  self.assertEqual(record['raw_response'],raw)
 def test_loading_old_analysis_normalizes_only_display(self):
  raw=r'E5 $\rightarrow$ D5'
  with patch.object(a,'save_composition',return_value='saved'):
   record=f.load(a,json.dumps({'mode':'analysis','answer':raw,'raw_response':raw}))
  self.assertEqual(record['answer'],'E5 → D5');self.assertEqual(record['raw_response'],raw)

if __name__=='__main__':unittest.main()
