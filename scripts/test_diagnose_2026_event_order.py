#!/usr/bin/env python3
"""Synthetic same-period ordering diagnosis, without source attribution."""
import sys,pathlib,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from diagnose_2026_event_order import review
from test_conserve_2026_period_events import data
class Cases(unittest.TestCase):
 def test_conflict_keeps_order_unverified(self):
  picks,windows,rosters=data()
  pid=99001
  windows[2]=({"transactions":[{"type":"FREEAGENT","status":"EXECUTED","proposedDate":1789000000000,"items":[{"type":"ADD","playerId":pid,"toTeamId":1},{"type":"DROP","playerId":pid,"fromTeamId":1}]}]},{"status":"ok"})
  r=review(windows,picks,rosters)
  self.assertEqual(r["conflicting_pair_count"],1)
  row=r["periods"][1]["candidates"][0]
  self.assertFalse(row["strict_process_time_order_available"])
  self.assertEqual(row["candidate_final_action"],"unverified")
  self.assertFalse(r["ownership_chain_verified"])
 def test_distinct_processing_instants_are_diagnostic_only(self):
  picks,windows,rosters=data()
  pid=99001
  windows[2]=({"transactions":[
   {"type":"WAIVER","status":"EXECUTED","processDate":1789000000000,"items":[{"type":"ADD","playerId":pid,"toTeamId":1}]},
   {"type":"WAIVER","status":"EXECUTED","processDate":1789000001000,"items":[{"type":"DROP","playerId":pid,"fromTeamId":1}]}]},{"status":"ok"})
  r=review(windows,picks,rosters)
  row=r["periods"][1]["candidates"][0]
  self.assertTrue(row["strict_process_time_order_available"])
  self.assertEqual(row["candidate_final_action"],"drop")
  self.assertFalse(r["ready_for_publication"])
 def test_missing_week_fails(self):
  picks,windows,rosters=data()
  del windows[2]
  with self.assertRaisesRegex(ValueError,"Missing"):review(windows,picks,rosters)
if __name__=="__main__":unittest.main()
