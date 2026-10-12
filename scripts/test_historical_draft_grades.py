#!/usr/bin/env python3
"""Offline integrity of verified retrospective draft grades and franchise DNA."""
import json,math,collections,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
D=json.loads((ROOT/"reference/historical_draft_picks.json").read_text())
G=json.loads((ROOT/"reference/historical_draft_grades.json").read_text())
F=json.loads((ROOT/"reference/franchise_continuity.json").read_text())

class DraftGrades(unittest.TestCase):
    def test_complete_original_year_coverage(self):
        self.assertEqual(G["status"],"retrospective_verified_model_v1")
        self.assertEqual(G["coverage"]["pick_count"],820)
        self.assertEqual(G["coverage"]["era_only_punters"],20)
        self.assertEqual(G["coverage"]["full_player_pool_count"],5677)
        self.assertEqual([x["year"] for x in G["seasons"]],[2021,2022,2023,2024,2025])
        self.assertEqual(len(G["franchise_dna"]),11)
        self.assertEqual(sum(G["tag_counts"].values()),820)
        self.assertEqual(set(G["tag_counts"]),{"BUST","HIT","NEUTRAL","STEAL","ERA_ONLY"})

    def test_each_pick_matches_original_draft_and_original_season(self):
        observed=collections.Counter()
        for grade,source in zip(G["seasons"],D["seasons"][:5]):
            y=grade["year"]
            with self.subTest(year=y):
                self.assertEqual((y,grade["league_id"]),(source["year"],source["league_id"]))
                self.assertEqual(len(grade["picks"]),len(source["picks"]))
                self.assertEqual(len(grade["franchises"]),10)
                self.assertGreater(grade["pool_size"],1000)
                for p,q in zip(grade["picks"],source["picks"]):
                    for key in ("overall","round","round_pick","player_id","player_name","position","espn_team_id","franchise_id"):
                        self.assertEqual(p[key],q[key])
                    self.assertEqual(p["franchise_id"],F["season_to_franchise"][str(y)][str(p["espn_team_id"])])
                    self.assertEqual(p["regular_pf"],round(p["regular_pf"],2))
                    self.assertGreaterEqual(p["recorded_scoring_weeks"],0)
                    self.assertLessEqual(p["recorded_scoring_weeks"],14)
                    self.assertGreaterEqual(p["normalized_value"],0)
                    self.assertLessEqual(p["normalized_value"],1.00001)
                    self.assertGreaterEqual(p["above_replacement_pf"],0)
                    if p["position"]=="P":
                        self.assertIn(y,(2021,2022))
                        self.assertEqual(p["tag"],"ERA_ONLY")
                        self.assertIsNone(p["value_added"])
                        self.assertEqual(p["draft_weight"],0)
                    else:
                        self.assertIn(p["tag"],("STEAL","HIT","NEUTRAL","BUST"))
                        self.assertTrue(math.isfinite(p["value_added"]))
                        self.assertAlmostEqual(p["value_added"],p["normalized_value"]-p["expected_value"],places=3)
                        self.assertGreater(p["draft_weight"],0)
                    observed[p["tag"]]+=1
                self.assertEqual(sum(p["position"]=="P" for p in grade["picks"]),10 if y<2023 else 0)
        self.assertEqual(observed,G["tag_counts"])

    def test_franchise_recency_and_owner_transition(self):
        season_map={s["year"]:{x["franchise_id"]:x for x in s["franchises"]} for s in G["seasons"]}
        for d in G["franchise_dna"]:
            fid=d["franchise_id"];years=[y for y in range(2025,2020,-1) if fid in season_map[y]]
            self.assertEqual(d["completed_seasons"],years)
            recent=years[:3]
            self.assertEqual([x["year"] for x in d["recent_year_weights"]],recent)
            self.assertAlmostEqual(sum(x["weight"] for x in d["recent_year_weights"]),1,places=3)
            expect=sum(season_map[y][fid]["draft_value_index"]*w["weight"] for y,w in zip(recent,d["recent_year_weights"]))
            self.assertAlmostEqual(expect,d["draft_value_index"],places=2)
            self.assertIn(d["profile"],("Value Hunter","Early-Round Anchor","High-Variance Drafter",
                                        "Balanced Builder","Draft Capital Underperformer","Mixed Returns",
                                        "INSUFFICIENT_HISTORY"))
        returning=F["season_to_franchise"]["2024"]["6"]
        outgoing=F["season_to_franchise"]["2023"]["6"]
        self.assertNotEqual(returning,outgoing)
        byfid={x["franchise_id"]:x for x in G["franchise_dna"]}
        self.assertEqual(byfid[returning]["completed_seasons"],[2025,2024,2022,2021])
        self.assertEqual([r["year"] for r in byfid[returning]["recent_year_weights"]],[2025,2024,2022])
        self.assertEqual(byfid[outgoing]["completed_seasons"],[2023,2022,2021])
        self.assertNotIn(2026,G["coverage"]["seasons"])

    def test_no_private_identity_or_credentials(self):
        text=json.dumps(G).lower()
        for t in ("owner_name","manager_name","session_cookie","espn_s2","espn_swid"):
            self.assertNotIn(t,text)

if __name__=="__main__":unittest.main()
