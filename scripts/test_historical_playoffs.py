#!/usr/bin/env python3
"""No-network integrity checks for public championship and playoff bracket history."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
B = json.loads((ROOT / "reference/historical_playoff_brackets.json").read_text())
C = json.loads((ROOT / "reference/championship_history.json").read_text())
F = json.loads((ROOT / "reference/franchise_continuity.json").read_text())
H = json.loads((ROOT / "reference/historical_regular_season_scores.json").read_text())


def winner(game):
    week, match_id, participants, target = game
    if len(participants) == 1:
        assert target is None
        return participants[0][0]
    assert len(participants) == 2
    a, b = participants
    assert a[0] != b[0] and a[2] != b[2]
    assert target == (a[0] if a[2] > b[2] else b[0]), (week, match_id)
    return target


class VerifiedPlayoffs(unittest.TestCase):
    def test_seasons_and_publishing(self):
        self.assertEqual(sorted(map(int, B["seasons"])), [2021, 2022, 2023, 2024, 2025])
        self.assertEqual([x["season"] for x in C["champions"]], [2021, 2022, 2023, 2024, 2025])
        self.assertTrue({int(s) for s in B["seasons"]}.issubset({s["year"] for s in H["seasons"]}))
        self.assertEqual({s["year"] for s in H["seasons"] if s.get("postseason")}, {2014,2015,2016,2017})
        self.assertEqual(B["status"], "verified_brackets")
        self.assertEqual(len(set(x["franchise_id"] for x in C["champions"])), 4)

    def test_bracket_progression_and_identity(self):
        for ystr, season in B["seasons"].items():
            year = int(ystr)
            with self.subTest(year=year):
                self.assertEqual(season["league_id"], F["league_ids_by_season"][ystr])
                self.assertEqual(len(season["qualifier_ids"]), 6)
                self.assertEqual(len(set(season["qualifier_ids"])), 6)
                games = season["games"]
                self.assertEqual(len(games), 7)
                self.assertEqual([sum(g[0] == week for g in games) for week in (15, 16, 17)], [4, 2, 1])
                self.assertEqual(len({g[1] for g in games}), 7)
                first = [g for g in games if g[0] == 15]
                semi = [g for g in games if g[0] == 16]
                final = next(g for g in games if g[0] == 17)
                byes = [g for g in first if len(g[2]) == 1]
                played = [g for g in first if len(g[2]) == 2]
                self.assertEqual((len(byes), len(played)), (2, 2))
                self.assertEqual({g[2][0][1] for g in byes}, {1, 2})
                self.assertEqual({q[0] for g in first for q in g[2]}, set(season["qualifier_ids"]))
                self.assertEqual({q[0] for g in semi for q in g[2]},
                                 {winner(g) for g in first})
                self.assertEqual({q[0] for q in final[2]},
                                 {winner(g) for g in semi})
                title = next(c for c in C["champions"] if c["season"] == year)
                self.assertEqual(winner(final), title["espn_team_id"])
                self.assertEqual(F["season_to_franchise"][ystr][str(title["espn_team_id"])],
                                 title["franchise_id"])
                self.assertEqual(title["source_league_id"], season["league_id"])
                names = {t["espn_team_id"]: t["name"] for t in
                         next(s for s in H["seasons"] if s["year"] == year)["teams"]}
                self.assertEqual(names[title["espn_team_id"]], title["team_name_at_win"])
                self.assertTrue(all(len(g[2]) in (1, 2) for g in games))
                if year == 2025:
                    self.assertEqual(season["seed_exception_ids"], [3, 5])
                    self.assertIn(5, season["qualifier_ids"])
                    self.assertNotIn(3, season["qualifier_ids"])
                else:
                    self.assertEqual(season["seed_exception_ids"], [])

    def test_legacy_season_trophies_do_not_infer_manager_identity(self):
        expected={2014:8,2016:9,2017:3}
        records=C['legacy_champions']
        self.assertEqual({x['season']:x['espn_team_id'] for x in records},expected)
        for c in records:
            season=next(s for s in H['seasons'] if s['year']==c['season'])
            final=season['postseason']
            self.assertEqual((c['source_league_id'],season['league_id']),(791996,791996))
            self.assertEqual((c['status'],c['bracket_status']),('confirmed_legacy_season','validated_bracket_path'))
            self.assertIsNone(c['franchise_id'])
            self.assertTrue(final['bracket_validated'])
            self.assertEqual((c['espn_team_id'],c['team_name_at_win']),
                             (final['winner_espn_team_id'],final['winner_team_name']))
            self.assertNotIn(str(c['season']),F['season_to_franchise'])
        self.assertFalse(next(s for s in H['seasons'] if s['year']==2015)['postseason']['bracket_validated'])
        self.assertNotIn(2015,expected)
        self.assertEqual([x['season'] for x in C['champions']],[2021,2022,2023,2024,2025])

    def test_manager_gap_and_multiple_trophies(self):
        legacy = F["season_to_franchise"]
        self.assertEqual(legacy["2021"]["3"], legacy["2023"]["7"])
        self.assertEqual([c["season"] for c in C["champions"]
                          if c["franchise_id"] == legacy["2023"]["7"]], [2021, 2023])
        self.assertEqual(legacy["2022"]["5"], legacy["2026"]["3"])
        self.assertNotEqual(legacy["2023"]["6"], legacy["2024"]["6"])

    def test_no_person_names_or_credentials(self):
        for source in (B, C):
            text = json.dumps(source).lower()
            for forbidden in ("manager_name", "owner_name", "espn_s2", "espn_swid",
                              "session_cookie"):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
