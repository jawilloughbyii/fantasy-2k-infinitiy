#!/usr/bin/env python3
"""Pure synthetic checks of private provenance preview; no authenticated data."""
import json, pathlib, sys, unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from audit_acquisition_2026 import draft_check, transaction_evidence, score_check, preview
from backfill_acquisition_provenance import expected_slots
ROOT=pathlib.Path(__file__).resolve().parents[1]
PUBLISHED=json.loads((ROOT/"data/league.json").read_text())
DRAFT=next(s for s in json.loads((ROOT/"reference/historical_draft_picks.json").read_text())["seasons"] if s["year"]==2026)["picks"]
MAPPING=json.loads((ROOT/"reference/team_id_map.json").read_text())["baseline_to_espn"]
RAW_DRAFT={"draftDetail":{"picks":[{"playerId":p["player_id"],"teamId":p["espn_team_id"]} for p in DRAFT]}}

def team_roster(tid):
    slots=[s for slot,n in expected_slots(2026).items() for s in [slot]*n]
    starts=[{"playerId":tid*100000+i+1,"lineupSlotId":slot} for i,slot in enumerate(slots)]
    return starts+[{"playerId":tid*100000+999,"lineupSlotId":20}]

def request(year,view,week=None,filter_=None,cookie=None):
    assert year==2026
    if view=="mDraftDetail":return RAW_DRAFT,{"status":"ok"}
    if view=="mTransactions2":
        return {"transactions":[{"id":17,"type":"WAIVER","status":"EXECUTED",
                                 "processDate":1789000000000,
                                 "items":[{"type":"ADD","playerId":999}]}]},{"status":"ok"}
    if view=="mRoster":
        return {"teams":[{"id":tid,"roster":{"entries":team_roster(tid)}} for tid in range(1,11)]},{"status":"ok"}
    if view=="mBoxscore":
        games=[]
        for a in range(1,11,2):
            def side(tid):
                bid=next(k for k,v in MAPPING.items() if int(v)==tid)
                tm=next(t for t in PUBLISHED["teams"] if t["id"]==int(bid))
                return {"teamId":tid,"totalPoints":tm["weeks"][week-1]["pf"],
                        "rosterForCurrentScoringPeriod":{"entries":team_roster(tid)}}
            games.append({"matchupPeriodId":week,"home":side(a),"away":side(a+1)})
        return {"schedule":games},{"status":"ok"}
    raise ValueError("Unexpected view")

class PreviewTests(unittest.TestCase):
    def test_reference_draft_must_match_original_160_picks(self):
        self.assertTrue(draft_check(RAW_DRAFT,DRAFT)["draft_matches_approved_reference"])
        wrong=json.loads(json.dumps(RAW_DRAFT))
        wrong["draftDetail"]["picks"][0]["teamId"]=9 if wrong["draftDetail"]["picks"][0]["teamId"]!=9 else 8
        self.assertFalse(draft_check(wrong,DRAFT)["draft_matches_approved_reference"])
        self.assertFalse(draft_check({},DRAFT)["original_draft_retrieved"])

    def test_transaction_endpoint_presence_does_not_prove_chain(self):
        raw={"transactions":[{"id":17,"type":"WAIVER","status":"EXECUTED",
                              "processDate":1789000000000,"items":[{"type":"ADD","playerId":999}]}]}
        rec=json.dumps(raw["transactions"][0],sort_keys=True,separators=(",",":"))
        s=transaction_evidence(raw,[{17:rec}])
        self.assertTrue(s["unscoped_contains_period_records"])
        self.assertFalse(s["chain_completeness_verified"])
        self.assertEqual(s["item_action_counts"],{"ADD":1})
        self.assertFalse(transaction_evidence({"transactions":[]},[{17:rec}])["unscoped_contains_period_records"])

    def test_score_check_must_reconcile_every_independent_week(self):
        boxes={w:request(2026,"mBoxscore",week=w)[0] for w in range(1,PUBLISHED["completedThrough"]+1)}
        self.assertTrue(score_check(boxes,PUBLISHED,MAPPING))
        boxes[1]["schedule"][0]["home"]["totalPoints"]+=1
        self.assertFalse(score_check(boxes,PUBLISHED,MAPPING))

    def test_full_private_preview_never_publishes_source_percentages(self):
        r=preview(request,PUBLISHED,DRAFT,MAPPING)
        self.assertEqual(r["expected_occupied_starts"],90*PUBLISHED["completedThrough"])
        self.assertTrue(r["draft"]["draft_matches_approved_reference"])
        self.assertTrue(r["gates"]["verified_original_week_pf"])
        self.assertFalse(r["gates"]["complete_executed_ownership_chain"])
        self.assertIsNone(r["source_mix"])
        self.assertIsNone(r["source_yield"])
        self.assertFalse(r["ready_for_publication"])
        blob=json.dumps(r).lower()
        for forbidden in ('"player_id"','"owner"','"member"','"cookie"','"espn_s2"','"espn_swid"'):
            self.assertNotIn(forbidden,blob)

if __name__=="__main__":unittest.main()
