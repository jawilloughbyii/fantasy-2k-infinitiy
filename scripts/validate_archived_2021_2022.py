#!/usr/bin/env python3
"""Validate sanitized 2021–2022 ESPN discovery results without publishing data."""
import argparse
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

def validate_season(path, expected_year, league_id):
    source = json.loads(Path(path).read_text(encoding="utf-8"))
    assert source["season"] == expected_year and source["league_id"] == league_id
    assert source["metadata"]["regular_season_matchup_count"] == 14
    teams = source["teams"]
    ids = [int(t["espn_team_id"]) for t in teams]
    assert len(ids) == len(set(ids)) == 10
    by_week = defaultdict(list)
    for match in source["matchups"]:
        by_week[int(match["week"])].append(match)
    scores = {tid: {} for tid in ids}
    winners_checked = 0
    total = Decimal("0")
    for week in range(1, 15):
        matchups = by_week[week]
        assert len(matchups) == 5, f"{expected_year} week {week}: expected five matches"
        participants = []
        for match in matchups:
            sides = match["sides"]
            assert len(sides) == 2
            home, away = sides
            a, b = int(home["team_id"]), int(away["team_id"])
            assert a != b and a in scores and b in scores
            participants.extend([a, b])
            for side in sides:
                value = side["points"]
                assert type(value) in (int, float) and value >= 0
                amount = Decimal(str(value))
                assert amount.as_tuple().exponent >= -2
                tid = int(side["team_id"])
                assert week not in scores[tid]
                scores[tid][week] = value
                total += amount
            expected_winner = ("HOME" if home["points"] > away["points"]
                               else "AWAY" if home["points"] < away["points"] else "TIE")
            assert match["winner"] == expected_winner, (
                f"{expected_year} week {week}: winner mismatch"
            )
            winners_checked += 1
        assert len(participants) == len(set(participants)) == 10
        assert set(participants) == set(ids)
    assert all(len(week_scores) == 14 for week_scores in scores.values())
    clean = {"year": expected_year, "source_league_id": league_id,
             "regular_season_weeks": 14,
             "teams": [
                 {"espn_team_id": int(t["espn_team_id"]), "name": t["name"].strip(),
                  "scores": [scores[int(t["espn_team_id"])][w] for w in range(1, 15)]}
                 for t in sorted(teams, key=lambda t: int(t["espn_team_id"]))
             ]}
    report = {"year": expected_year, "teams": 10, "regular_season_weeks": 14,
              "matchups": winners_checked, "team_week_scores": 140,
              "total_points": float(total),
              "league_pf_per_team_week": round(float(total) / 140, 2),
              "excluded_postseason_or_placement_records": len(source["matchups"]) - 70,
              "winner_mismatches": 0,
              "status": "validated_regular_season_only"}
    return clean, report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="output/historical-discovery")
    parser.add_argument("--output-dir", default="output/validated-historical")
    parser.add_argument("--league-id", type=int, default=1493036707)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    seasons, reports = [], []
    for year in (2021, 2022):
        clean, report = validate_season(
            Path(args.input_dir) / f"season_{year}.json", year, args.league_id)
        seasons.append(clean)
        reports.append(report)
        print(f"{year}: PASS — {report['team_week_scores']} final regular-season "
              f"team scores; {report['matchups']} winner-verified matchups; "
              f"total PF {report['total_points']:.2f}")
    (out / "historical_regular_season_2021_2022.json").write_text(
        json.dumps({"league_id": args.league_id,
                    "status": "validated scoring only; franchise continuity with 2023 not verified",
                    "seasons": seasons}, indent=2) + "\n")
    (out / "validation_summary.json").write_text(
        json.dumps({"status": "passed", "seasons": reports,
                    "identity": "unmapped across historical league boundary",
                    "postseason": "excluded; championship results not validated"}, indent=2) + "\n")
    print("No dashboard or public reference file modified.")

if __name__ == "__main__":
    main()
