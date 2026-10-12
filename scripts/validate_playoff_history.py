#!/usr/bin/env python3
"""Fail-closed verification of ESPN archived championship bracket progression."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "postseason-research"
IDENTITY = json.loads((ROOT / "reference" / "franchise_continuity.json").read_text())
CHAMPS = json.loads((ROOT / "reference" / "championship_history.json").read_text())
KNOWN = {int(c["season"]): int(c["espn_team_id"]) for c in CHAMPS["champions"]}

def check_winner(m):
    assert len(m["sides"]) == 2, f"Not a two-sided matchup: {m['matchup_id']}"
    a, b = m["sides"]
    assert a["team_id"] != b["team_id"]
    assert a["points"] is not None and b["points"] is not None
    assert m["winner"] in ("HOME", "AWAY")
    expected = "HOME" if a["points"] > b["points"] else "AWAY" if a["points"] < b["points"] else None
    assert expected and m["winner"] == expected, f"Unexpected result: {m['matchup_id']}"
    return a if m["winner"] == a["side"].upper() else b

def check_season(year):
    d = json.loads((OUT / f"season_{year}.json").read_text())
    m = d["metadata"]
    assert d["season"] == year
    assert d["league_id"] == IDENTITY["league_ids_by_season"][str(year)]
    assert m["regular_season_matchup_periods"] == 14
    assert m["playoff_team_count"] == 6
    assert m["playoff_matchup_period_length"] == 1
    seeds = {int(t["espn_team_id"]): int(t["playoff_seed"]) for t in d["teams"]}
    assert sorted(seeds.values()) == list(range(1, 11))
    games = d["postseason_matchups"]
    assert len(games) == 16
    assert {x["matchup_period"] for x in games} == {15, 16, 17}
    assert len({x["matchup_id"] for x in games}) == 16
    winners = [x for x in games if x["playoff_tier_type"] == "WINNERS_BRACKET"]
    assert len(winners) == 7
    w15 = [x for x in winners if x["matchup_period"] == 15]
    w16 = [x for x in winners if x["matchup_period"] == 16]
    w17 = [x for x in winners if x["matchup_period"] == 17]
    assert (len(w15), len(w16), len(w17)) == (4, 2, 1)
    byes = [x for x in w15 if len(x["sides"]) == 1]
    r1 = [x for x in w15 if len(x["sides"]) == 2]
    assert len(byes) == 2 and len(r1) == 2
    bye_teams = {x["sides"][0]["team_id"] for x in byes}
    assert {seeds[x] for x in bye_teams} == {1, 2}
    assert all(x["winner"] == "UNDECIDED" for x in byes)
    r1_teams = [side["team_id"] for x in r1 for side in x["sides"]]
    assert len(set(r1_teams)) == 4
    assert {seeds[x] for x in r1_teams} == {3, 4, 5, 6}
    r1_winners = {check_winner(x)["team_id"] for x in r1}
    semis_teams = [s["team_id"] for x in w16 for s in x["sides"]]
    assert len(set(semis_teams)) == 4
    assert set(semis_teams) == bye_teams | r1_winners, f"{year}: semifinal advancement inconsistent"
    semi_winners = {check_winner(x)["team_id"] for x in w16}
    assert len(semi_winners) == 2
    final = w17[0]
    finalists = {x["team_id"] for x in final["sides"]}
    assert finalists == semi_winners, f"{year}: championship progression mismatch"
    champion = check_winner(final)
    runner = next(x for x in final["sides"] if x["team_id"] != champion["team_id"])
    third_matches = [x for x in games if x["matchup_period"] == 17 and
                     x["playoff_tier_type"] == "WINNERS_CONSOLATION_LADDER"]
    losers = {s["team_id"] for x in w16 for s in x["sides"]} - semi_winners
    assert len([x for x in third_matches if {s["team_id"] for s in x["sides"]} == losers]) == 1
    if year in KNOWN:
        assert champion["team_id"] == KNOWN[year], f"{year}: conflicts with verified champion"
    mapping = IDENTITY["season_to_franchise"][str(year)]
    assert str(champion["team_id"]) in mapping
    championship = {
        "season": year, "league_id": d["league_id"], "champion_espn_team_id": champion["team_id"],
        "champion_team_name": champion["team_name"], "champion_franchise_id": mapping[str(champion["team_id"])],
        "runner_up_espn_team_id": runner["team_id"], "runner_up_team_name": runner["team_name"],
        "championship_matchup_id": final["matchup_id"], "week": 17,
        "champion_points": champion["points"], "runner_up_points": runner["points"],
        "winner_field_verified": True, "bracket_progression_verified": True
    }
    # All competitive championship-bracket games, including semifinal and final;
    # separately label consolation/third-place, not as championship qualification.
    bracket = []
    for x in sorted(winners, key=lambda y: (y["matchup_period"], y["matchup_id"])):
        entry = {"week": x["matchup_period"], "matchup_id": x["matchup_id"],
                 "stage": {15: "first_round_or_bye", 16: "semifinal", 17: "championship"}[x["matchup_period"]],
                 "teams": [{"espn_team_id": z["team_id"], "name": z["team_name"],
                            "seed": seeds[z["team_id"]], "points": z["points"]} for z in x["sides"]]}
        if len(x["sides"]) == 2:
            winner = check_winner(x)
            entry["winner_espn_team_id"] = winner["team_id"]
        else:
            entry["bye"] = True
        bracket.append(entry)
    return championship, {
        "year": year, "league_id": d["league_id"], "playoff_teams": 6,
        "regular_season_weeks": 14, "playoff_weeks": [15, 16, 17],
        "championship_bracket": bracket, "champion": championship,
        "third_place_matchup_verified": True,
        "placement_games_excluded_from_title_inference": True,
        "status": "verified_espn_winners_bracket",
    }

def main():
    validated, bracket_years = [], []
    for year in range(2021, 2026):
        result, bracket = check_season(year)
        validated.append(result)
        bracket_years.append(bracket)
        print(f"{year}: VERIFIED CHAMPION {result['champion_team_name']} "
              f"({result['champion_points']:.2f}–{result['runner_up_points']:.2f}) "
              f"over {result['runner_up_team_name']}; franchise={result['champion_franchise_id']}")
    (OUT / "verified_champions_candidate.json").write_text(
        json.dumps({"status": "verified_for_review_not_published", "championships": validated}, indent=2) + "\n")
    (OUT / "verified_brackets_candidate.json").write_text(
        json.dumps({"status": "verified_for_review_not_published", "seasons": bracket_years}, indent=2) + "\n")
    print("PASS: 5 seasons; all championship advancement paths and existing titles agree. No publication.")

if __name__ == "__main__":
    main()
