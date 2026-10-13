#!/usr/bin/env python3
"""Pure synthetic Acquisition DNA tests; no claimed historical/2026 transactions."""
import json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import acquisition_dna as a

class AcquisitionDNACases(unittest.TestCase):
 def rows(self):
  return [
   {"week":1,"player_id":11,"slot":"QB","source":"draft","worthy":True},
   {"week":1,"player_id":22,"slot":"RB","source":"trade","worthy":True},
   {"week":1,"player_id":-33,"slot":"K","source":"unknown","worthy":True},
   {"week":2,"player_id":11,"slot":"QB","source":"draft","worthy":False},
   {"week":2,"player_id":44,"slot":"RB","source":"waiver","worthy":False},
   {"week":2,"player_id":-33,"slot":"K","source":"unknown","worthy":True}]
 def summary(self,rows=None,ceiling=None):
  return a.summarize("franchise-test",2026,[1,2],self.rows() if rows is None else rows,
                     ["QB","RB","K"],{"QB":1,"RB":1,"K":.5},ceiling)
 def test_each_starter_week_is_one_mix_denominator_including_unknown(self):
  x=self.summary()
  self.assertEqual(x["starter_week_count"],6)
  self.assertEqual(x["known_source_starter_weeks"],4)
  self.assertEqual(x["source_coverage"],"partial")
  m={s["source"]:s for s in x["mix"]}
  self.assertEqual({s:m[s]["starter_weeks"] for s in ("draft","trade","waiver","unknown")},
                   {"draft":2,"trade":1,"waiver":1,"unknown":2})
  self.assertEqual(m["draft"]["mix_pct"],33.33)
  self.assertEqual(m["unknown"]["mix_pct"],33.33)
  self.assertEqual(m["draft"]["yield_pct"],50)
  self.assertEqual(m["trade"]["yield_pct"],100)
  self.assertEqual(m["waiver"]["yield_pct"],0)
  self.assertEqual(m["unknown"]["yield_pct"],100)
 def test_execution_is_independent_of_acquisition_and_uses_available_ceiling(self):
  x=self.summary(ceiling={1:2.5,2:1.5})
  self.assertEqual((x["execution"]["weighted_hits"],x["execution"]["attainable_weighted_ceiling"],x["execution"]["capture_pct"]),(3,4,75))
  with self.assertRaisesRegex(ValueError,"Impossible legal"):
   self.summary(ceiling={1:1,2:1.5})
  with self.assertRaisesRegex(ValueError,"every completed week"):
   self.summary(ceiling={1:2.5})
 def test_partial_or_missing_quality_does_not_claim_yield(self):
  rows=self.rows();rows[0].pop("worthy")
  x=self.summary(rows)
  self.assertEqual(x["mix"][0]["yield_status"],"unavailable")
  with self.assertRaisesRegex(ValueError,"complete"):
   self.summary(rows,ceiling={1:2.5,2:1.5})
 def test_missing_duplicate_and_illegal_rosters_fail(self):
  with self.assertRaisesRegex(ValueError,"Incomplete starter"):
   self.summary(self.rows()[:-1])
  rows=self.rows();rows[1]["player_id"]=11
  with self.assertRaisesRegex(ValueError,"duplicated"):
   self.summary(rows)
  rows=self.rows();rows[1]["slot"]="WR"
  with self.assertRaisesRegex(ValueError,"Invalid source/slot"):
   self.summary(rows)
  rows=self.rows();rows[2]["source"]="draft" # Not verified source? This synthetic valid but must never silently infer it from live data.
  self.assertEqual(self.summary(rows)["source_coverage"],"partial")
 def test_last_entry_overrides_draft_after_drop(self):
  events=[{"player_id":11,"franchise_id":"F","effective_at":"2026-08-01T10:00:00-04:00","action":"draft"},
          {"player_id":11,"franchise_id":"F","effective_at":"2026-09-01T10:00:00-04:00","action":"drop"},
          {"player_id":11,"franchise_id":"F","effective_at":"2026-09-10T10:00:00-04:00","action":"waiver"}]
  lookup=lambda date,verified:a.last_verified_source(11,"F",date,events,complete_chain=verified)
  self.assertEqual(lookup("2026-08-30T13:00:00-04:00",True),"draft")
  self.assertEqual(lookup("2026-09-05T13:00:00-04:00",True),"unknown")
  self.assertEqual(lookup("2026-09-12T13:00:00-04:00",True),"waiver")
  self.assertEqual(lookup("2026-09-12T13:00:00-04:00",False),"unknown")
  self.assertEqual(lookup("2026-09-09T13:00:00-04:00",True),"unknown")
 def test_equal_weight_complete_season_only(self):
  x=self.summary()
  self.assertEqual(a.equal_weight_history([x])["status"],"unavailable")
  x["mix"]=[{**row,"mix_pct":round(row["starter_weeks"]*100/6,2)} for row in x["mix"]]
  x["source_coverage"]="verified"
  x2=json.loads(json.dumps(x));x2["year"]=2025
  # A punter-era 10-slot season should receive one vote, not 10/9 of a vote.
  x2["starter_week_count"]=20;x2["mix"][0]["mix_pct"]=50
  y=a.equal_weight_history([x,x2])
  self.assertEqual(y["verified_seasons"],[2025,2026])
  self.assertEqual(y["mix"]["draft"],41.66)
  with self.assertRaisesRegex(ValueError,"Duplicate"):
   a.equal_weight_history([x,x])
 def test_verified_vacant_slot_is_not_unknown_acquisition(self):
  rows=self.rows()[:-1]
  with self.assertRaisesRegex(ValueError,"Incomplete starter"):
   self.summary(rows)
  x=a.summarize("franchise-test",2026,[1,2],rows,["QB","RB","K"],
                {"QB":1,"RB":1,"K":.5},vacant_slots_by_week={1:[],2:["K"]})
  self.assertEqual(x["starter_week_count"],5)
  self.assertEqual(x["verified_vacant_slots"],1)
  self.assertEqual(sum(r["starter_weeks"] for r in x["mix"]),5)
  with self.assertRaisesRegex(ValueError,"vacant"):
   a.summarize("franchise-test",2026,[1,2],rows,["QB","RB","K"],
               vacant_slots_by_week={1:[],2:["WR"]})
 def test_no_keeper_source_or_transaction_is_accepted(self):
  self.assertEqual(a.CATEGORIES,("draft","trade","waiver","free_agent","other","unknown"))
  self.assertNotIn("keeper",json.loads((ROOT/"reference/metric_definitions.json").read_text())["acquisitionDna"]["sourceCategories"])
  rows=self.rows();rows[0]["source"]="keeper"
  with self.assertRaisesRegex(ValueError,"Invalid source"):
   self.summary(rows)
  with self.assertRaisesRegex(ValueError,"Unrecognized acquisition"):
   a.last_verified_source(11,"F","2026-09-12T13:00:00-04:00",
       [{"player_id":11,"franchise_id":"F","effective_at":"2026-09-01T10:00:00-04:00","action":"keeper"}],complete_chain=True)
 def test_trade_out_and_release_end_an_ownership_spell(self):
  for exit_action in ("drop","trade_out","release"):
   events=[{"player_id":11,"franchise_id":"F","effective_at":"2026-08-01T10:00:00-04:00","action":"draft"},
           {"player_id":11,"franchise_id":"F","effective_at":"2026-09-01T10:00:00-04:00","action":exit_action}]
   self.assertEqual(a.last_verified_source(11,"F","2026-09-10T13:00:00-04:00",events,complete_chain=True),"unknown")
 def test_current_published_data_has_no_invented_provenance(self):
  r=json.loads((ROOT/"reference/acquisition_dna.json").read_text())
  self.assertEqual(r["status"],"awaiting_verified_starter_acquisition_provenance")
  self.assertEqual(r["coverage"]["verified_source_starter_weeks"],0)
  self.assertFalse(r["season_summaries"])
  audit=r["source_readiness"]
  self.assertEqual(audit["audit_status"],"sampled_endpoints_only_not_qualified_for_source_mix")
  self.assertIn("mRoster returns identical",audit["legacy_history_2014_2017"])
  self.assertIn("full 14-week",audit["modern_history_2021_2025"].lower())
  self.assertEqual(audit["excluded_years"],[2018,2019,2020])
  live=json.loads((ROOT/"data/league.json").read_text())
  self.assertNotIn("acquisitionDna",live)
  self.assertIn("rosterAnalysis",live)

if __name__=="__main__":unittest.main()
