#!/usr/bin/env python3
"""Synthetic lock-field evidence tests, no assumed kickoff times."""
import unittest,sys,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from audit_2026_player_lock_fields import inspect
from test_audit_acquisition_2026 import request,PUBLISHED
class Cases(unittest.TestCase):
 def boxes(self):
  boxes={w:request(2026,"mBoxscore",week=w)[0] for w in range(1,PUBLISHED["completedThrough"]+1)}
  for box in boxes.values():
   for game in box["schedule"]:
    for side in ("home","away"):
     for e in game[side]["rosterForCurrentScoringPeriod"]["entries"]:
      if e["lineupSlotId"] not in (20,21):
       e["playerPoolEntry"]={"player":{"proTeamId":12}}
  return boxes
 def test_team_identity_is_not_kickoff_proof(self):
  r=inspect(self.boxes(),PUBLISHED["completedThrough"])
  self.assertEqual(r["observed_starter_appearances"],90*PUBLISHED["completedThrough"])
  self.assertEqual(r["player_nfl_team_identity_coverage"],90*PUBLISHED["completedThrough"])
  self.assertEqual(r["candidate_direct_time_field_occurrences"],0)
  self.assertFalse(r["verified_individual_game_locks"])
  self.assertFalse(r["ready_for_publication"])
 def test_extra_fantasy_scoring_period_does_not_become_lock(self):
  boxes=self.boxes()
  e=boxes[1]["schedule"][0]["home"]["rosterForCurrentScoringPeriod"]["entries"][0]
  e["scoringPeriodId"]=1;e["playerPoolEntry"]["scoringPeriodId"]=1
  r=inspect(boxes,PUBLISHED["completedThrough"])
  self.assertEqual(r["candidate_direct_time_field_occurrences"],0)
  self.assertFalse(r["transaction_before_lock_verified"])
 def test_missing_week_rejected(self):
  boxes=self.boxes();boxes.pop(2)
  with self.assertRaisesRegex(ValueError,"coverage"):inspect(boxes,PUBLISHED["completedThrough"])
if __name__=="__main__":unittest.main()
