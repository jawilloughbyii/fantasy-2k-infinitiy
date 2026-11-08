#!/usr/bin/env python3
"""Synthetic read-only opening-evidence query tests."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from probe_2026_opening_evidence import compare_rosters,compare_transaction_queries
class Tests(unittest.TestCase):
 def test_identical_period_zero_never_claims_draft_day(self):
  raw={"teams":[{"id":t,"roster":{"entries":[{"playerId":1000+t,"lineupSlotId":0}]}} for t in range(1,11)]}
  r,sets=compare_rosters({None:(raw,{"status":"ok"}),0:(raw,{"status":"ok"}),1:(raw,{"status":"ok"})},[])
  self.assertEqual(r["distinct_observed_roster_sets"],1)
  self.assertTrue(r["queries"]["period_0"]["identical_to_unscoped"])
  self.assertFalse(r["draft_day_opening_roster_verified"])
 def test_earlier_transaction_view_may_reveal_primary_gap(self):
  a={"transactions":[{"id":1,"type":"FREEAGENT","items":[]}]}
  b={"transactions":[{"id":2,"type":"FREEAGENT","items":[]}]}
  x=compare_transaction_queries([("mTransactions2",None,a,{"status":"ok"}),("mTransactions",0,b,{"status":"ok"})])
  self.assertEqual(x["queries"]["mTransactions_period_0"]["additional_distinct_records"],1)
  self.assertFalse(x["full_draft_to_week_one_transaction_history_verified"])
if __name__=="__main__":unittest.main()
