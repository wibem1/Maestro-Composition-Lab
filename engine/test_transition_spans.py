"""Native tick/ticks lines, confirmed against Maestro's official example file."""
import copy,unittest
import composition as c
import transition as t
import workspace as w
from test_transition import fixture,proposal
from test_workspace import execute,fragment
from test_expression import EXPRESS_MODEL

class Tests(unittest.TestCase):
 def test_native_multibar_line_before_tail_is_preserved_by_real_lua(self):
  line={'kind':'crescendo','tick':0,'ticks':3840}
  model,src=fixture("music.staves[1].measures[1].hairpins={{kind='crescendo',tick=0,ticks=3840}}\n")
  plan=t.plan(src,2);self.assertFalse(any(m['kind']=='hairpins' for m in plan['marks']))
  result=execute(model+t.writer(proposal(),src,2,2)+'\nreturn json(score:raw())')
  self.assertEqual(result['staves'][0]['measures'][0]['hairpins'],[line])
 def test_native_line_inside_tail_removed_before_new_expression(self):
  model,src=fixture("music.staves[1].measures[3].hairpins={{kind='crescendo',tick=0,ticks=3840}}\n")
  result=execute(model+t.writer(proposal(),src,2,2)+'\nreturn json(score:raw())')
  self.assertEqual(result['staves'][0]['measures'][2]['hairpins'],[])
  self.assertEqual(len(result['staves'][0]['measures'][3]['hairpins']),1)
 def test_native_line_crossing_boundary_is_blocked_before_generation(self):
  _,src=fixture("music.staves[1].measures[2].hairpins={{kind='crescendo',tick=960,ticks=1920}}\n")
  with self.assertRaisesRegex(c.ScoreError,'über die Übergangsgrenze'):t.plan(src,2)
  self.assertTrue(t.plan(src,3))
 def test_line_anchored_at_end_of_protected_bar_is_checked_before_writing(self):
  _,src=fixture("music.staves[1].measures[2].hairpins={{tick=1920,ticks=960}}\n")
  with self.assertRaisesRegex(c.ScoreError,'vorherigen Takt'):t.plan(src,2)
 def test_actual_lengths_with_meter_change_and_partial_first_bar(self):
  bars=[{'ticks':960},{'ticks':2880},{'ticks':1920},{'ticks':1920}]
  self.assertEqual(t.timed_span({'tick':240,'ticks':3600},1,bars),(240,3840))
  self.assertEqual(t.timed_span({'tick':0,'ticks':3840},3,bars),(3840,7680))
  self.assertEqual(t.timed_span({'tick':480,'endTick':1440},2,bars),(1440,2400))
 def test_invalid_inconsistent_or_out_of_score_spans_stay_blocked(self):
  bars=[{'ticks':1920}]*4
  for item in ({'tick':0,'ticks':-1},{'tick':0,'ticks':True},{'tick':0,'ticks':float('nan')},{'tick':0,'ticks':float('inf')},{'tick':0,'ticks':9000},{'tick':2000,'ticks':1},{'tick':0,'ticks':960,'endTick':480},{'tick':0,'ticks':960,'endMeasure':3},{'tick':0,'unknown':960},{'tick':0,'ticks':960.5}):
   with self.subTest(item=item),self.assertRaises(c.ScoreError):t.timed_span(item,1,bars)
 def test_gaenseliesel_32_bars_line_21_through_22_does_not_block_tail(self):
  # Measure count, meter and wedge positions from the uploaded MusicXML;
  # pitches are synthetic, not redistributed from the user's composition.
  model=EXPRESS_MODEL+'''\nscore:appendMeasures(30)
for si,st in ipairs(music.staves) do for bi=3,32 do st.measures[bi].entries={event('e'..si..'_'..bi,'h',{'C4'})} end end
music.staves[1].measures[21].hairpins={{kind='crescendo',tick=0,ticks=3840}}
'''
  src=execute(model+w.read_lua('all')+'\nreturn output[2]')|{'id':'source','score_id':'bound'}
  for tail in (2,3,4):
   with self.subTest(tail=tail):
    self.assertEqual(t.plan(src,tail)['first'],33-tail)
    data=fragment(2,tail+2)
    result=execute(model+t.writer(data,src,tail,2)+'\nreturn json(score:raw())')
    self.assertEqual(result['count'],34)
    self.assertEqual(result['staves'][0]['measures'][20]['hairpins'],[{'kind':'crescendo','tick':0,'ticks':3840}])
 def test_all_time_based_expression_collections_use_same_boundary_check(self):
  for kind in t.SPAN_FIELDS:
   with self.subTest(kind=kind):
    _,src=fixture(f"music.staves[1].measures[1].{kind}={{{{tick=0,ticks=3840}}}}\n")
    self.assertTrue(t.plan(src,2))
    src['staves'][0]['measures'][0][kind][0]['ticks']=4800
    with self.assertRaisesRegex(c.ScoreError,'über die Übergangsgrenze'):t.plan(src,2)

if __name__=='__main__':unittest.main()
