#!/usr/bin/env python3
"""Fail-closed original-year 2014–17 ESPN draft/scoring/record audit regression."""
import json, pathlib, unittest, collections
R=pathlib.Path(__file__).resolve().parents[1]
D=json.loads((R/"reference/historical_legacy_draft_picks_2014_2017.json").read_text())
S=json.loads((R/"reference/historical_legacy_scoring_2014_2017.json").read_text())
O=json.loads((R/"reference/historical_legacy_official_standings_2014_2017.json").read_text())
H=json.loads((R/"reference/historical_regular_season_scores.json").read_text())
POSITIONS={"QB","RB","WR","TE","K","D/ST","P"}
class VerifiedOriginalYears(unittest.TestCase):
 def test_named_and_positioned_drafts(self):
  self.assertEqual(D["status"],"verified_original_year_player_metadata_complete")
  self.assertEqual((D["coverage"]["pick_count"],D["coverage"]["named_picks"],D["coverage"]["positioned_picks"]),(680,680,680))
  for s in D["seasons"]:
   with self.subTest(year=s["year"]):
    self.assertEqual(len(s["picks"]),170)
    self.assertEqual(s["player_enrichment"],"complete_original_year_ESPN_170_of_170")
    self.assertEqual(len({p["player_id"] for p in s["picks"]}),170)
    for p in s["picks"]:
     self.assertTrue(isinstance(p["player_name"],str) and len(p["player_name"].strip())>=3)
     self.assertIn(p["position"],POSITIONS)
     self.assertEqual(p["player_metadata_source"],"ESPN_season_players_wl_exact_original_draft_id")
    self.assertEqual(sum(p["position"]=="P" for p in s["picks"]),10)
    self.assertGreaterEqual(sum(p["position"]=="D/ST" for p in s["picks"]),10)
  self.assertEqual(D["seasons"][0]["picks"][0]["player_name"],"Adrian Peterson")
  self.assertEqual(D["seasons"][1]["picks"][0]["player_name"],"Le'Veon Bell")
  self.assertEqual(D["seasons"][2]["picks"][0]["player_name"],"Antonio Brown")
  self.assertEqual(D["seasons"][3]["picks"][0]["player_name"],"David Johnson")
 def test_scoring_rules_and_year_specificity(self):
  self.assertEqual(S["status"],"verified_source_scoring_definitions")
  self.assertEqual([x["year"] for x in S["seasons"]],[2014,2015,2016,2017])
  baseline=None
  for s in S["seasons"]:
   n=47 if s["year"]==2014 else 50
   self.assertEqual((s["league_id"],s["scoring_type"],s["scoring_item_count"]),(791996,"H2H_POINTS",n))
   self.assertEqual(len(s["items"]),n)
   self.assertEqual(len({x["statId"] for x in s["items"]}),n)
   self.assertEqual(s["lineup_slot_counts"]["18"],1)
   for item in s["items"]:
    self.assertTrue(type(item["statId"]) is int)
    self.assertTrue(type(item["points"]) in (int,float))
   if s["year"]==2014:baseline=s["items"]
   else:self.assertNotEqual(s["items"],baseline)
 def test_espn_official_regular_season_wlt_pf_pa(self):
  self.assertEqual(O["status"],"verified_official_wlt_pf_pa_official_rank_not_returned")
  self.assertEqual([x["year"] for x in O["seasons"]],[2014,2015,2016,2017])
  for s in O["seasons"]:
   self.assertEqual((s["record_count"],s["reconciled_count"]),(10,10))
   self.assertFalse(s["official_ranking_available"])
   saved=next(x for x in H["seasons"] if x["year"]==s["year"])
   matchups=json.loads((R/f"research/espn-791996-2014-2017/season_{s['year']}.json").read_text())["standings"]["rows"]
   for row in s["rows"]:
    x=next(x for x in matchups if x["espn_team_id"]==row["espn_team_id"])
    for field in ("wins","losses","ties","points_for","points_against"):
     self.assertAlmostEqual(row[field],x[field],places=2)
    self.assertEqual(row["wins"]+row["losses"]+row["ties"],14)
   self.assertEqual(saved["standings_verification"]["wins_losses_ties_pf_pa"],"all_10_exactly_reconciled")
   self.assertEqual(saved["standings_verification"]["official_seed_order"],"not_returned_do_not_infer")
 def test_no_private_fields(self):
  data=json.dumps([S,O,D]).lower()
  for field in ('"owner_name"','"manager_name"','"owner_id"','"manager_id"','"espn_s2"','"espn_swid"','"cookie"'):
   self.assertNotIn(field,data)
if __name__=="__main__":unittest.main()
