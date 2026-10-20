import pathlib, unittest
import maestro_analyse as m
class PlatformUITest(unittest.TestCase):
 def test_each_platform_has_distinct_ui(self):
  root=pathlib.Path(m.__file__).parent
  mac=(root/'ui/mac.html').read_text(encoding='utf-8')
  win=(root/'ui/windows.html').read_text(encoding='utf-8')
  self.assertIn('__TOKEN__',mac)
  self.assertIn('__TOKEN__',win)
  self.assertNotEqual(mac,win)
 def test_version(self):self.assertEqual(m.VERSION,'3.0.0')
