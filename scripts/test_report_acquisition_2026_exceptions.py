#!/usr/bin/env python3
"""Synthetic exception report tests; no authenticated player or transaction data."""
import copy,json,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from report_acquisition_2026_exceptions import inspect
from test_audit_acquisition_2026 import request,PUBLISHED,MAPPING
class ReportCases(unittest.TestCase):
    def evidence(self):
        boxes={w:request(2026,"mBoxscore",week=w)[0] for w in range(1,PUBLISHED["completedThrough"]+1)}
        first=boxes[1]["schedule"][0]["home"]
        p=first["rosterForCurrentScoringPeriod"]["entries"][0]
        pid=p["playerId"]; team=first["teamId"]
        for w,box in boxes.items():
            for game in box["schedule"]:
                for side in ("home","away"):
                    for e in game[side]["rosterForCurrentScoringPeriod"]["entries"]:
                        if e.get("playerId")==pid:
                            e["playerPoolEntry"]={"id":pid,"player":{"fullName":"Synthetic Player A"}}
        return boxes,pid,team
    def test_join_and_exact_minimized_fields(self):
        boxes,pid,team=self.evidence()
        tx={"transactions":[{"id":88,"status":"EXECUTED","type":"FREEAGENT",
             "proposedDate":1788500000000,"items":[{"type":"ADD","playerId":pid,
             "fromTeamId":None,"toTeamId":team}]}]}
        r=inspect(tx,boxes,PUBLISHED,MAPPING,[])
        self.assertEqual(r["exception_item_count"],1)
        self.assertEqual(r["counts_by_action"],{"FREEAGENT/ADD":1})
        item=r["items"][0]
        self.assertEqual(item["player"],"Synthetic Player A")
        self.assertIn(1,item["finalized_starter_weeks"])
        self.assertIsNone(item["process_at_utc"])
        self.assertFalse(r["ready_for_publication"])
        blob=json.dumps(r)
        for secret in ('"player_id"','"transaction_id"','"cookie"','"owner"','"member"'):
            self.assertNotIn(secret,blob)
        self.assertNotIn(str(pid),blob)
    def test_skip_processed_and_failed_and_do_not_infer_name(self):
        boxes,pid,team=self.evidence()
        rows=[{"id":1,"status":"FAILED_INVALIDPLAYERSOURCE","type":"FREEAGENT",
               "proposedDate":1788500000000,"items":[{"type":"ADD","playerId":pid,"toTeamId":team}]},
              {"id":2,"status":"EXECUTED","type":"WAIVER","proposedDate":1788500000000,
               "items":[{"type":"ADD","playerId":pid,"toTeamId":team}]},
              {"id":3,"status":"EXECUTED","type":"ROSTER","processDate":1788500000000,
               "proposedDate":1788500000000,"items":[{"type":"DROP","playerId":pid,
               "fromTeamId":team,"toTeamId":None}]}]
        r=inspect({"transactions":rows},boxes,PUBLISHED,MAPPING,[])
        self.assertEqual(r["exception_item_count"],0)
    def test_bad_original_week_and_missing_date_fail_or_exclude(self):
        boxes,pid,team=self.evidence()
        invalid=copy.deepcopy(boxes)
        invalid.pop(2)
        with self.assertRaisesRegex(ValueError,"coverage"):
            inspect({"transactions":[]},invalid,PUBLISHED,MAPPING,[])
        tx={"transactions":[{"id":8,"status":"EXECUTED","type":"ROSTER",
             "items":[{"type":"DROP","playerId":pid,"fromTeamId":team,"toTeamId":None}]}]}
        self.assertEqual(inspect(tx,boxes,PUBLISHED,MAPPING,[])["exception_item_count"],0)
    def test_conflicting_names_are_explicit(self):
        boxes,pid,team=self.evidence()
        tx={"transactions":[{"id":8,"status":"EXECUTED","type":"ROSTER",
             "proposedDate":1788500000000,"items":[{"type":"DROP","playerId":pid,"fromTeamId":team,"toTeamId":None}]}]}
        draft=[{"player_id":pid,"player_name":"Different Synthetic Name"}]
        r=inspect(tx,boxes,PUBLISHED,MAPPING,draft)
        self.assertEqual(r["items"][0]["name_status"],"conflicting_display_labels")
if __name__=="__main__":unittest.main()
