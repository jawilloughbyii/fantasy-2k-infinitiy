#!/usr/bin/env python3
"""Synthetic invariants for research-only period conservation (no ESPN data)."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from conserve_2026_period_events import examine
from test_probe_2026_opening_evidence import Tests as RosterTests

def data():
    picks=[{"player_id":1000+t*100+i,"espn_team_id":t} for t in range(1,11) for i in range(16)]
    tx=[]
    for p in picks:
        tx.append({"type":"DRAFT","status":"EXECUTED","proposedDate":1788500000000,
                   "items":[{"type":"DRAFT","playerId":p["player_id"],"toTeamId":p["espn_team_id"]}]})
    r={"teams":[{"id":t,"roster":{"entries":[{"playerId":1000+t*100+i,"lineupSlotId":20} for i in range(16)]}} for t in range(1,11)]}
    windows={i:({"transactions":tx if i==1 else []},{"status":"ok"}) for i in range(1,6)}
    rosters={i:(r,{"status":"ok"}) for i in (None,0,1,2,3,4,5)}
    return picks,windows,rosters

class ConservationTests(unittest.TestCase):
    def test_complete_draft_and_no_publication(self):
        picks,windows,rosters=data()
        result=examine(windows,picks,rosters)
        self.assertEqual(result["executed_draft_items_matching_reference"],160)
        self.assertTrue(result["draft_event_coverage_complete"])
        self.assertFalse(result["full_ownership_chain_verified"])
        self.assertFalse(result["ready_for_publication"])
        self.assertEqual(result["timestamp_basis_counts"]["proposedDate_unverified"],160)
    def test_duplicate_draft_is_rejected(self):
        picks,windows,rosters=data()
        windows[2]=({"transactions":[dict(windows[1][0]["transactions"][0],proposedDate=1788500001000)]},{"status":"ok"})
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            examine(windows,picks,rosters)
    def test_exact_repeated_record_is_not_counted_twice(self):
        picks,windows,rosters=data()
        windows[2]=({"transactions":[windows[1][0]["transactions"][0]]},{"status":"ok"})
        report=examine(windows,picks,rosters)
        self.assertEqual(report["exact_duplicate_query_records_ignored"],1)
        self.assertEqual(report["executed_draft_items_matching_reference"],160)
    def test_missing_period_fails(self):
        picks,windows,rosters=data()
        del windows[3]
        with self.assertRaisesRegex(ValueError,"unavailable"):examine(windows,picks,rosters)
    def test_conflicting_draft_franchise_fails(self):
        picks,windows,rosters=data()
        windows[1][0]["transactions"][0]["items"][0]["toTeamId"]=9
        with self.assertRaisesRegex(ValueError,"conflicts"):examine(windows,picks,rosters)
if __name__=="__main__":unittest.main()
