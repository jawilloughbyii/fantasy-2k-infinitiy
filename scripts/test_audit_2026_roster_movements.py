#!/usr/bin/env python3
"""Synthetic net-movement checks; deliberately no claimed game locks."""
import sys,pathlib,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from audit_2026_roster_movements import audit
from test_conserve_2026_period_events import data
class Tests(unittest.TestCase):
 def test_draft_only_matches_observed_but_not_verified(self):
  picks,windows,rosters=data()
  r=audit(windows,picks,rosters)
  self.assertEqual(r["periods"]["1"]["derived_pair_count"],160)
  self.assertEqual(r["periods"]["1"]["derived_missing_from_observed_count"],0)
  self.assertFalse(r["ownership_chain_verified"])
  self.assertFalse(r["ready_for_publication"])
 def test_same_period_add_drop_is_ambiguous(self):
  picks,windows,rosters=data()
  pid=99001
  windows[2]=({"transactions":[{"status":"EXECUTED","type":"FREEAGENT","proposedDate":1789000000000,"items":[
    {"type":"ADD","playerId":pid,"toTeamId":1},
    {"type":"DROP","playerId":pid,"fromTeamId":1}]}]},{"status":"ok"})
  r=audit(windows,picks,rosters)
  self.assertEqual(r["periods"]["2"]["same_pair_both_added_and_removed"],1)
  self.assertFalse(r["periods"]["2"]["time_boundary_verified"])
 def test_missing_window_rejected(self):
  picks,windows,rosters=data()
  windows.pop(4)
  with self.assertRaisesRegex(ValueError,"Incomplete"):audit(windows,picks,rosters)
if __name__=="__main__":unittest.main()
