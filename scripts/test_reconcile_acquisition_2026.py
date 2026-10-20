#!/usr/bin/env python3
"""Synthetic tests only. No ESPN player or team identity is used."""
import pathlib, sys, unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from reconcile_acquisition_2026 import (SLOTS, validate_draft, validate_starters,
                                        replay, private_summary)

DRAFT_AT = "2026-08-01T12:00:00+00:00"
GATES = dict(complete_transaction_feed=True, independently_corroborated=True,
             verified_player_locks=True, score_reconciled=True,
             source_event_schema_verified=True)

def fixture(weeks=2):
    picks = [{"player_id": 1000+team*100+i, "espn_team_id": team}
             for team in range(1,11) for i in range(16)]
    slots = list(SLOTS.elements())
    starts = [{"week": w, "player_id": 1000+team*100+i, "espn_team_id": team, "slot": slot}
              for w in range(1,weeks+1) for team in range(1,11)
              for i, slot in enumerate(slots)]
    locks = {(r["week"], r["player_id"]):
             (datetime(2026,9,7,tzinfo=timezone.utc) +
              timedelta(days=7*(r["week"]-1))).isoformat() for r in starts}
    return picks, starts, locks

class ChainTests(unittest.TestCase):
    def attempt(self, events=None, gates=None):
        picks, starts, locks = fixture()
        return replay(picks, DRAFT_AT, events or [], starts, [1,2], locks,
                      **(GATES if gates is None else gates))

    def test_full_synthetic_draft_replays_all_starter_weeks(self):
        rows=self.attempt()
        self.assertEqual(len(rows),180)
        self.assertEqual({x["source"] for x in rows},{"draft"})
        summary=private_summary(rows,2)
        self.assertEqual(summary["occupied_starter_appearances"],180)
        self.assertFalse(summary["ready_for_publication"])
        self.assertNotIn("player_id",repr(summary))

    def test_drop_then_waiver_reentry_does_not_keep_draft_credit(self):
        player=1100
        events=[
            {"event_key":"tx1:0","player_id":player,"espn_team_id":1,
             "effective_at":"2026-09-09T12:00:00+00:00","action":"drop"},
            {"event_key":"tx2:0","player_id":player,"espn_team_id":1,
             "effective_at":"2026-09-10T12:00:00+00:00","action":"waiver"}]
        rows=self.attempt(events)
        hit=[r for r in rows if r["player_id"]==player]
        self.assertEqual([r["source"] for r in hit],["draft","waiver"])

    def test_incomplete_evidence_never_returns_source_percentages(self):
        for name in GATES:
            flags={**GATES,name:False}
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.attempt(gates=flags)

    def test_invalid_draft_and_team_slot_coverage(self):
        picks, starts, locks=fixture()
        with self.assertRaisesRegex(ValueError,"160-pick"):
            validate_draft(picks[:-1])
        starts[0]["slot"]=99
        with self.assertRaisesRegex(ValueError,"nine-slot"):
            validate_starters(starts,[1,2],True)

    def test_missing_lock_and_lock_collision_fail(self):
        picks, starts, locks=fixture()
        locks.pop((1,1100))
        with self.assertRaisesRegex(ValueError,"lock"):
            replay(picks,DRAFT_AT,[],starts,[1,2],locks,**GATES)
        picks,starts,locks=fixture()
        events=[{"event_key":"tx1:0","player_id":1100,"espn_team_id":1,
                 "effective_at":locks[(2,1100)],"action":"drop"}]
        with self.assertRaisesRegex(ValueError,"Ambiguous transaction"):
            replay(picks,DRAFT_AT,events,starts,[1,2],locks,**GATES)

    def test_impossible_or_duplicate_chain_fails(self):
        duplicate=[{"event_key":"tx1:0","player_id":1100,"espn_team_id":1,
                    "effective_at":"2026-09-10T12:00:00+00:00","action":"waiver"}]
        with self.assertRaisesRegex(ValueError,"existing owner"):
            self.attempt(duplicate)
        dropped=[{**duplicate[0],"action":"drop"}]
        with self.assertRaisesRegex(ValueError,"pre-lock ownership"):
            self.attempt(dropped)
        same=[dropped[0],{**dropped[0],"event_key":"tx2:0"}]
        with self.assertRaisesRegex(ValueError,"Ambiguous simultaneous"):
            self.attempt(same)

    def test_trade_requires_source_and_current_owner(self):
        trade=[{"event_key":"tx-trade:0","player_id":1100,"espn_team_id":2,
                "from_team_id":3,"effective_at":"2026-09-10T12:00:00+00:00",
                "action":"trade"}]
        with self.assertRaisesRegex(ValueError,"documented source"):
            self.attempt(trade)
        del trade[0]["from_team_id"]
        with self.assertRaisesRegex(ValueError,"explicit original source"):
            self.attempt(trade)

    def test_no_name_matching_or_unverified_types(self):
        bad=[{"event_key":"tx:0","player_id":1100,"espn_team_id":1,
              "effective_at":"2026-09-10T12:00:00+00:00","action":"keeper"}]
        with self.assertRaisesRegex(ValueError,"Unsupported"):
            self.attempt(bad)
        bad[0]["action"]="waiver";bad[0]["effective_at"]="2026-09-10T12:00:00"
        with self.assertRaisesRegex(ValueError,"timezone"):
            self.attempt(bad)

if __name__=="__main__": unittest.main()
