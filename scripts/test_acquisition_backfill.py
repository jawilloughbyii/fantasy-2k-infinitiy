#!/usr/bin/env python3
"""Offline tests; synthetic identities only, no ESPN authentication."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from backfill_acquisition_provenance import expected_slots,roster_check,boxscore_starters,transaction_check,audit

class TestBackfill(unittest.TestCase):
 def team(self,year):
  pairs=[];pid=100
  for slot,n in expected_slots(year).items():
   for _ in range(n):
    pid+=1;pairs.append((pid,slot))
  return {"starters":sorted(pairs),"all":sorted(pairs+[(999,20)])}
 def test_exact_year_specific_slots_and_invalid_duplicate(self):
  self.assertEqual(sum(expected_slots(2022).values()),10)
  self.assertEqual(expected_slots(2022)[18],1)
  self.assertEqual(sum(expected_slots(2026).values()),9)
  for year in (2022,2026):
   found={tid:self.team(year) for tid in range(1,11)}
   self.assertTrue(roster_check(found,year))
   found[1]["starters"].append(found[1]["starters"][0])
   self.assertFalse(roster_check(found,year))
 def test_matchup_agreement_can_verify_an_occupied_slot_vacancy(self):
  year=2022;found={tid:self.team(year) for tid in range(1,11)}
  found[10]["starters"]=[x for x in found[10]["starters"] if x[1]!=16]
  self.assertFalse(roster_check(found,year))
  self.assertTrue(roster_check(found,year,allow_vacant=True))
  games=[]
  for i in range(1,11,2):
   def side(tid):
    return {"teamId":tid,"rosterForCurrentScoringPeriod":{"entries":[{"playerId":pid,"lineupSlotId":slot} for pid,slot in found[tid]["starters"]]}}
   games.append({"matchupPeriodId":1,"home":side(i),"away":side(i+1)})
  box=boxscore_starters({"schedule":games},1,year)
  self.assertEqual(box[10]["starters"],found[10]["starters"])
 def test_matchup_scoped_lineup_requires_all_teams(self):
  year=2026;games=[]
  for i in range(1,11,2):
   def side(tid):
    return {"teamId":tid,"rosterForCurrentScoringPeriod":{"entries":[{"playerId":pid,"lineupSlotId":slot} for pid,slot in self.team(year)["starters"]]}}
   games.append({"matchupPeriodId":1,"home":side(i),"away":side(i+1)})
  self.assertEqual(len(boxscore_starters({"schedule":games},1,year)),10)
  self.assertIsNone(boxscore_starters({"schedule":games},2,year))
 def test_transaction_schema_is_not_completeness(self):
  empty,rows=transaction_check({"transactions":[]})
  self.assertEqual(empty["status"],"observed_not_chain_verified")
  self.assertEqual(rows,{})
  absent,_=transaction_check({"notTransactions":[]})
  self.assertEqual(absent["status"],"missing_list")
  bad,_=transaction_check({"transactions":[{"id":1,"items":[{"wrong":77}]}]})
  self.assertEqual(bad["malformed"],1)
 def test_fail_closed_full_period_synthetic(self):
  def request(year,view,week,cookie=None,filter_=None):
   if view=="mRoster":
    return {"teams":[{"id":tid,"roster":{"entries":[{"playerId":pid,"lineupSlotId":slot} for pid,slot in self.team(year)["all"]]}} for tid in range(1,11)]},{"status":"ok"}
   if view=="mTransactions2":return {"transactions":[]} ,{"status":"ok"}
   return {"schedule":[]},{"status":"ok"}
  # The live audit uses real source retrieval; mock fetch must not activate mix.
  with self.assertRaises(ValueError):
   audit(2014,request)
  x=audit(2026,request)
  self.assertEqual(len(x["periods"]),4)
  self.assertFalse(x["ready_for_attribution"])
  self.assertFalse(x["matchup_comparisons_agree"])

if __name__=="__main__":unittest.main()
