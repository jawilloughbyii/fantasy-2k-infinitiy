#!/usr/bin/env python3
"""Synthetic ESPN transaction shape tests; no live/source identifiers."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from normalize_acquisition_2026 import normalize_executed
NOW=1789000000000
def record(kind,items,status="EXECUTED",id=1,date=NOW):
    return {"id":id,"type":kind,"status":status,"processDate":date,"items":items}
def item(action,pid,source=None,dest=None):
    return {"type":action,"playerId":pid,"fromTeamId":source,"toTeamId":dest}
class Normalization(unittest.TestCase):
    def test_executed_only_and_lineup_is_not_acquisition(self):
        r={"transactions":[
          record("WAIVER",[item("ADD",100,None,1),item("DROP",200,1,None)]),
          record("FREEAGENT",[item("ADD",300,-1,2)],id=2),
          record("ROSTER",[item("LINEUP",100,None,None),item("DROP",400,2,-1)],id=3),
          record("TRADE_ACCEPT",[item("TRADE",500,1,2)],id=4),
          record("WAIVER",[item("ADD",600,None,3)],status="FAILED_INVALIDPLAYERSOURCE",id=5),
          record("TRADE_PROPOSAL",[item("TRADE",500,1,2)],status="PENDING",id=6),
          {"type":"TRADE_UPHOLD","status":"EXECUTED","items":[]},
          {"type":"ROSTER","status":"EXECUTED","items":[item("LINEUP",500,None,None)]}]}
        rows,counts=normalize_executed(r)
        self.assertEqual(len(rows),5)
        self.assertEqual(counts["nonexecuted_ignored"],2)
        self.assertEqual(counts["lineup_edits_ignored"],2)
        self.assertEqual(counts["empty_trade_uphold_ignored"],1)
        self.assertEqual(counts["trade"],1)
        self.assertEqual({r["action"] for r in rows},{"waiver","free_agent","drop","trade"})
        trade=next(r for r in rows if r["action"]=="trade")
        self.assertEqual((trade["from_team_id"],trade["espn_team_id"]),(1,2))
        self.assertTrue(all("+00:00" in r["effective_at"] for r in rows))
    def test_unsupported_or_ambiguous_actions_fail_closed(self):
        fixtures=[
          record("ROSTER",[item("ADD",100,None,1)]),
          record("WAIVER",[item("ADD",100,1,2)]),
          record("FREEAGENT",[item("DROP",100,None,None)]),
          record("TRADE_ACCEPT",[item("TRADE",100,None,2)]),
          record("WAIVER",[item("ADD",100,None,1)],date=None),
          record("DRAFT",[item("ADD",100,None,1)]),
          record("WAIVER",[item("KEEPER",100,None,1)]),
        ]
        for x in fixtures:
            with self.subTest(kind=x["type"],action=x["items"][0]["type"]),self.assertRaises(ValueError):
                normalize_executed({"transactions":[x]})
    def test_repeat_event_rejected_and_unexecuted_skipped(self):
        r=record("WAIVER",[item("ADD",100,None,1)])
        with self.assertRaisesRegex(ValueError,"Duplicate executed"):
            normalize_executed({"transactions":[r,r]})
        self.assertEqual(normalize_executed({"transactions":[{**r,"status":"CANCELED"}]})[0],[])
        with self.assertRaisesRegex(ValueError,"missing"):
            normalize_executed({})
if __name__=="__main__":unittest.main()
