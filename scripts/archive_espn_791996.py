#!/usr/bin/env python3
"""Archive four user-confirmed ESPN seasons on an isolated research branch only.

Data are strictly whitelisted: league display name, team display names, settings,
matchups, and draft pick metadata. Never collect members, owners, private fields,
or authenticated ESPN response bodies. No production/dashboard sources are touched.
"""
import datetime as dt
import json
import math
import os
from collections import defaultdict
from pathlib import Path

from inspect_espn_791996 import ID, YEARS, VIEWS, inspect, read, finite_score

OUT = Path("research/espn-791996-2014-2017")
SAFE_DRAFT_FIELDS = ("overallPickNumber", "roundId", "roundPickNumber",
                     "teamId", "playerId", "keeper", "bidAmount")


def derive_standings(season):
    tid_to_name = {t["espn_team_id"]: t["display_name"] for t in season["teams"]}
    ids = set(tid_to_name)
    if len(ids) != 10:
        raise ValueError("Expected ten distinct historical ESPN team IDs")
    reg = [m for m in season["matchups"] if m["week"] in range(1, 15)]
    if len(reg) != 70 or len({m["matchup_id"] for m in reg}) != 70:
        raise ValueError("Expected 70 unique regular-season games")
    weekly = defaultdict(set)
    stats = {tid: {"espn_team_id": tid, "name": name, "wins": 0, "losses": 0,
                   "ties": 0, "points_for": 0., "points_against": 0.,
                   "weekly_points": []} for tid, name in tid_to_name.items()}
    anomalies = []
    for m in reg:
        w = m["week"]
        if len(m["sides"]) != 2 or m["winner"] not in ("HOME", "AWAY", "TIE"):
            raise ValueError(f"Regular-season game incomplete at week {w}")
        home, away = (next((x for x in m["sides"] if x["side"] == side), None)
                      for side in ("home", "away"))
        if home is None or away is None:
            raise ValueError("Missing home/away side")
        h, a = home["espn_team_id"], away["espn_team_id"]
        hp, ap = home["points"], away["points"]
        if h == a or h not in ids or a not in ids or hp is None or ap is None:
            raise ValueError("Invalid participants or scores")
        if not (math.isfinite(hp) and math.isfinite(ap)):
            raise ValueError("Nonfinite score")
        if h in weekly[w] or a in weekly[w]:
            raise ValueError(f"Week {w}: team appears twice")
        weekly[w].update((h, a))
        for team, own, opponent in ((h, hp, ap), (a, ap, hp)):
            stats[team]["points_for"] += own
            stats[team]["points_against"] += opponent
            stats[team]["weekly_points"].append({"week": w, "points": own})
        if m["winner"] == "HOME":
            stats[h]["wins"] += 1
            stats[a]["losses"] += 1
        elif m["winner"] == "AWAY":
            stats[a]["wins"] += 1
            stats[h]["losses"] += 1
        else:
            stats[a]["ties"] += 1
            stats[h]["ties"] += 1
        # ESPN winner field is authoritative in tied scores: preserve tiebreak.
        expected = "HOME" if hp > ap else "AWAY" if hp < ap else None
        if expected is not None and expected != m["winner"]:
            anomalies.append({"week": w, "matchup_id": m["matchup_id"],
                              "reason": "winner_field_disagrees_with_score"})
    if set(weekly) != set(range(1, 15)) or any(v != ids for v in weekly.values()):
        raise ValueError("Missing a regular-season week/team")
    if sum(r["wins"] for r in stats.values()) + sum(r["ties"] for r in stats.values()) // 2 != 70:
        raise ValueError("Regular-season result accounting failed")
    out = []
    for r in stats.values():
        r["points_for"] = round(r["points_for"], 2)
        r["points_against"] = round(r["points_against"], 2)
        r["weekly_points"].sort(key=lambda p: p["week"])
        if len(r["weekly_points"]) != 14:
            raise ValueError("Team lacks 14 scores")
        out.append(r)
    out.sort(key=lambda t: (-t["wins"] - t["ties"] / 2, -t["points_for"], t["espn_team_id"]))
    return out, anomalies


def playoffs(season):
    games = [m for m in season["matchups"] if m["week"] in (15, 16)]
    if len(games) != 10:
        raise ValueError("Expected ten recorded postseason matchups")
    bracket = [m for m in games if m["playoff_tier_type"] == "WINNERS_BRACKET"]
    semi = [m for m in bracket if m["week"] == 15]
    finals = [m for m in bracket if m["week"] == 16]
    if len(semi) != 2 or len(finals) != 1:
        return {"status": "unresolved_bracket_structure", "winner_record": None}
    def winner(m):
        if len(m["sides"]) != 2 or m["winner"] not in ("HOME", "AWAY"):
            return None
        return next((x for x in m["sides"] if x["side"].upper() == m["winner"]), None)
    s_winners = [winner(m) for m in semi]
    final = finals[0]
    f_winner = winner(final)
    if any(x is None for x in s_winners) or f_winner is None:
        return {"status": "unresolved_missing_winner_fields", "winner_record": None}
    finalists = {x["espn_team_id"] for x in final["sides"]}
    advance = finalists == {x["espn_team_id"] for x in s_winners}
    points = [x["points"] for x in final["sides"]]
    numeric_winner = None if None in points or points[0] == points[1] else final["sides"][0 if points[0] > points[1] else 1]["espn_team_id"]
    name_map = {t["espn_team_id"]: t["display_name"] for t in season["teams"]}
    champion_id = f_winner["espn_team_id"]
    record = {"espn_team_id": champion_id, "team_name": name_map[champion_id],
              "final_matchup_id": final["matchup_id"], "final_week": 16,
              "final_points": f_winner["points"],
              "runner_up_team_id": next(x["espn_team_id"] for x in final["sides"] if x["espn_team_id"] != champion_id),
              "semifinal_advancement_matches_finalists": advance,
              "winner_field_matches_final_score": numeric_winner == champion_id}
    # Only label a champion verified when the whole path and final agree. A tied
    # semifinal may have an ESPN tiebreak; rely on its explicit winner field.
    ok = advance and numeric_winner == champion_id
    return {"status": "validated_bracket_path" if ok else "source_final_record_only_advancement_unresolved",
            "winner_record": record}


def draft(year, cookie, team_ids):
    src, diagnostic = read(year, ("mDraftDetail",), cookie)
    if src is None:
        return {"status": "unavailable", "retrieval": diagnostic, "picks": []}
    detail = src.get("draftDetail")
    if not isinstance(detail, dict):
        return {"status": "view_missing_draft_detail", "picks": []}
    raw = detail.get("picks")
    if not isinstance(raw, list) or not raw:
        return {"status": "no_picks_returned", "drafted": detail.get("drafted"), "picks": []}
    safe = []
    for q in raw:
        if not isinstance(q, dict):
            return {"status": "invalid_pick_shape", "picks": []}
        r = {k: q.get(k) for k in SAFE_DRAFT_FIELDS}
        if type(r["teamId"]) is not int or r["teamId"] not in team_ids:
            return {"status": "unknown_draft_team", "picks": []}
        if type(r["overallPickNumber"]) is not int or r["overallPickNumber"] <= 0:
            return {"status": "invalid_overall_pick", "picks": []}
        # ESPN uses negative identifiers for drafted team defenses; they are valid.
        if type(r["playerId"]) is not int or r["playerId"] == 0:
            return {"status": "invalid_player_id", "reported_pick_count": len(raw),
                    "diagnostic": {"value": r["playerId"], "value_type": type(r["playerId"]).__name__,
                                   "available_pick_keys": sorted(q.keys()),
                                   "overall": r["overallPickNumber"], "round": r["roundId"]},
                    "picks": []}
        safe.append(r)
    numbers = [p["overallPickNumber"] for p in safe]
    if len(numbers) != len(set(numbers)):
        return {"status": "duplicate_overall_picks", "picks": []}
    safe.sort(key=lambda x: x["overallPickNumber"])
    # Original player IDs are retained; do not substitute contemporary players
    # or invent player names. The draft picks can be enriched later from original-year data.
    return {"status": "retrieved_original_espn_picks",
            "drafted": detail.get("drafted"),
            "pick_count": len(safe),
            "round_count": len({p["roundId"] for p in safe}),
            "team_pick_counts": {str(tid): sum(p["teamId"] == tid for p in safe) for tid in sorted(team_ids)},
            "picks": safe}


def main():
    s2, swid = os.getenv("ESPN_S2", "").strip(), os.getenv("ESPN_SWID", "").strip()
    if not s2 or not swid:
        raise SystemExit("SAFE ERROR: Missing existing ESPN Actions credentials")
    cookie = f"espn_s2={s2}; SWID={swid}"
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for year in YEARS:
        s = inspect(year, cookie)
        if s.get("status") != "retrieved_unverified_identity_research":
            raise ValueError(f"{year}: missing authentic source")
        if s.get("source_league_id") != ID or s.get("league_name") != "Horny Bryant Men Pt. Deux":
            raise ValueError(f"{year}: wrong candidate league")
        if s["settings"]["regular_season_matchup_period_count"] != 14:
            raise ValueError(f"{year}: regular-season boundary changed")
        if len(s["matchups"]) != 80:
            raise ValueError(f"{year}: expected 80 games")
        standings, anomalies = derive_standings(s)
        ps = playoffs(s)
        dr = draft(year, cookie, {t["espn_team_id"] for t in s["teams"]})
        archive = {
            "season": year, "league_id": ID,
            "verification": {"league_identity": "user_confirmed_2026_10_12",
                             "source": "authenticated_ESPN_leagueHistory",
                             "regular_season": "70_game_14_week_reconciled",
                             "postseason": ps["status"], "draft": dr["status"],
                             "franchise_mapping": "not_started"},
            "league_name": s["league_name"],
            "settings": s["settings"],
            "teams": s["teams"],
            "standings": {"type": "derived_from_ESPN_regular_season_matchups_not_official_rank",
                          "rows": standings, "score_winner_anomalies": anomalies},
            "postseason": ps,
            "matchups": s["matchups"],
            "draft": dr,
            "publication": "ISOLATED_RESEARCH_NOT_IMPORTED",
        }
        path = OUT / f"season_{year}.json"
        path.write_text(json.dumps(archive, indent=2, ensure_ascii=False) + "\n")
        report.append({"season": year, "regular_games": 70, "team_weeks": 140,
                       "postseason_games": 10, "postseason_status": ps["status"],
                       "draft_status": dr["status"], "draft_picks": dr.get("pick_count", 0),
                       "regular_season_pf_total": round(sum(x["points_for"] for x in standings), 2)})
        print(f"{year}: 70 regular games, 140 team-weeks; playoff={ps['status']}; "
              f"draft={dr['status']}, picks={dr.get('pick_count', 0)}")
    manifest = {"candidate_league_id": ID, "league_name": "Horny Bryant Men Pt. Deux",
                "identity": "user_confirmed", "scope": "2014-2017 only",
                "status": "ISOLATED_RESEARCH_NO_PRODUCTION_IMPORT",
                "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "seasons": report,
                "privacy": "Selected fantasy team display names and scores only; no owners or cookies",
                "not_linked_to": ["2013 candidate 1435116", "2021-2022 league 1493036707",
                                  "2023-2026 league 418244680"]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Validated sanitized research dataset prepared; production files untouched.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError) as exc:
        raise SystemExit("SAFE ERROR: " + str(exc))
