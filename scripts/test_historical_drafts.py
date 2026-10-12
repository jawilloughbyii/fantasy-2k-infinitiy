#!/usr/bin/env python3
"""Offline source and owner-identity validation for six ESPN draft seasons."""
import json
from collections import Counter
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/"reference"/"historical_draft_picks.json").read_text())
F=json.loads((ROOT/"reference"/"franchise_continuity.json").read_text())
H=json.loads((ROOT/"reference"/"historical_regular_season_scores.json").read_text())
CURRENT=json.loads((ROOT/"data"/"league.json").read_text())
TEAM_IDS=json.loads((ROOT/"reference"/"team_id_map.json").read_text())
POS={"QB","RB","WR","TE","K","D/ST","P"}

class DraftValidation(unittest.TestCase):
    def test_coverage_and_lineup_eras(self):
        self.assertEqual(D["status"],"verified_picks_not_performance_grades")
        self.assertEqual([s["year"] for s in D["seasons"]],[2021,2022,2023,2024,2025,2026])
        self.assertEqual([s["total_picks"] for s in D["seasons"]],[170,170,160,160,160,160])
        self.assertEqual(sum(len(s["picks"]) for s in D["seasons"]),980)
        self.assertEqual({s["year"] for s in D["seasons"] if s["historical_punter_position"]},{2021,2022})
        self.assertEqual(sum(p["position"]=="P" for s in D["seasons"] for p in s["picks"]),20)
        self.assertEqual(CURRENT["completedThrough"],4) # Current 2026 state must remain unchanged.

    def test_picks_and_source_identity(self):
        for season in D["seasons"]:
            y=season["year"];n=season["total_picks"];m=F["season_to_franchise"][str(y)]
            with self.subTest(year=y):
                self.assertEqual(season["league_id"],F["league_ids_by_season"][str(y)])
                self.assertEqual(season["draft_type"],"SNAKE")
                self.assertEqual(season["rounds"],n//10)
                self.assertEqual(len(season["teams"]),10)
                self.assertEqual(len(season["picks"]),n)
                self.assertEqual([p["overall"] for p in season["picks"]],list(range(1,n+1)))
                self.assertEqual(len({p["player_id"] for p in season["picks"]}),n)
                self.assertEqual(set(t["espn_team_id"] for t in season["teams"]),set(map(int,m)))
                self.assertEqual(len({t["franchise_id"] for t in season["teams"]}),10)
                for t in season["teams"]:
                    self.assertEqual(t["franchise_id"],m[str(t["espn_team_id"])])
                self.assertEqual({p["franchise_id"] for p in season["picks"]},{t["franchise_id"] for t in season["teams"]})
                cnt=Counter(p["espn_team_id"] for p in season["picks"])
                self.assertEqual(set(cnt.values()),{season["rounds"]})
                for p in season["picks"]:
                    self.assertEqual(p["round"],(p["overall"]-1)//10+1)
                    self.assertIn(p["round_pick"],range(1,11))
                    self.assertIn(p["position"],POS)
                    self.assertTrue(p["player_name"].strip())
                    self.assertEqual(p["franchise_id"],m[str(p["espn_team_id"])])
                if y in (2021,2022):
                    self.assertEqual(sum(p["position"]=="P" for p in season["picks"]),10)
                else:
                    self.assertFalse(any(p["position"]=="P" for p in season["picks"]))

    def test_yearbook_aliases_and_current_franchise_mapping(self):
        historic={s["year"]:{t["espn_team_id"]:t["name"] for t in s["teams"]} for s in H["seasons"]}
        present={int(TEAM_IDS["baseline_to_espn"][str(t["id"])]):t["name"] for t in CURRENT["teams"]}
        for s in D["seasons"]:
            names=historic.get(s["year"],present)
            self.assertEqual({t["espn_team_id"]:t["season_team_name"] for t in s["teams"]},names)
        history=F["season_to_franchise"]
        self.assertEqual(history["2021"]["1"],history["2024"]["6"])
        self.assertNotEqual(history["2023"]["6"],history["2024"]["6"])
        self.assertNotEqual(history["2022"]["1"],history["2023"]["5"])

    def test_source_no_owner_identifiers(self):
        txt=json.dumps(D).lower()
        for private in ("owner_name","manager_name","espn_s2","espn_swid","session_cookie"):
            self.assertNotIn(private,txt)

if __name__=="__main__":unittest.main()
