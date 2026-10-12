#!/usr/bin/env python3
"""Isolated authenticated ESPN league-ID access probe, no prior-league assumptions.

Does not infer league years, team identity, owner continuity, scoring, or
relation to other leagues. Only safe response metadata is saved privately.
"""
import collections
import datetime as dt
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

LEAGUE = 1435116
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games"
OUT = Path("output/isolated-league-1435116")
GAMES = ("ffl", "fba", "flb", "fhl")
# Exhaustive calendar scan for football and broad independent cross-game scan.
YEARS = {
    "ffl": range(2005, 2027),
    "fba": range(2010, 2027),
    "flb": range(2010, 2027),
    "fhl": range(2010, 2027),
}


def one(url, label, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            payload = json.load(res)
        if isinstance(payload, list):
            if len(payload) != 1:
                return {"target": label, "result": "invalid_array_size", "size": len(payload)}
            payload = payload[0]
        if not isinstance(payload, dict):
            return {"target": label, "result": "invalid_response_shape"}
        result = {
            "target": label, "result": "http_200",
            "returned_id": payload.get("id"),
            "declared_season": payload.get("seasonId"),
            "team_count": len(payload.get("teams") or []),
            "previous_seasons": (payload.get("status") or {}).get("previousSeasons"),
            "league_name_private_only": payload.get("settings", {}).get("name")
                if isinstance(payload.get("settings"), dict) else None,
            "returned_keys": sorted(payload.keys()),
        }
        if str(result["returned_id"]) != str(LEAGUE):
            result["result"] = "id_mismatch"
        return result
    except urllib.error.HTTPError as exc:
        return {"target": label, "result": "http_error", "code": exc.code}
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {"target": label, "result": "request_error", "error_type": type(exc).__name__}


def main():
    s2, swid = os.getenv("ESPN_S2", "").strip(), os.getenv("ESPN_SWID", "").strip()
    if not s2 or not swid:
        raise SystemExit("SAFE ERROR: missing ESPN Actions authentication")
    headers = {
        "Cookie": f"espn_s2={s2}; SWID={swid}",
        "Accept": "application/json",
        "User-Agent": "Fantasy2KInfinity-IsolatedLeagueAccess/1.0",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    # A positive control only validates auth/endpoint, never establishes a
    # relationship between this league and any known iteration.
    controls = [
        ("control_ffl_2022_known", f"{BASE}/ffl/seasons/2022/segments/0/leagues/1493036707?view=mTeam"),
        ("control_ffl_2026_known", f"{BASE}/ffl/seasons/2026/segments/0/leagues/418244680?view=mTeam"),
    ]
    control_results = [one(url, label, headers) for label, url in controls]
    for control in control_results:
        print(f"CONTROL {control['target']}: {control['result']} "
              f"status={control.get('code')} returned_id={control.get('returned_id')}")
    results = []
    for game in GAMES:
        for year in YEARS[game]:
            for shape in ("modern", "leagueHistory"):
                root = (
                    f"{BASE}/{game}/seasons/{year}/segments/0/leagues/{LEAGUE}"
                    if shape == "modern"
                    else f"{BASE}/{game}/leagueHistory/{LEAGUE}?seasonId={year}"
                )
                label = f"{game}_{year}_{shape}"
                record = one(root, label, headers)
                record.update({"game": game, "year": year, "endpoint": shape})
                # Repeat a successful root request with status view only, to
                # recover historical season pointers if supported.
                if record["result"] == "http_200":
                    query = "&view=mStatus" if "?" in root else "?view=mStatus"
                    status = one(root + query, label + "_status", headers)
                    record["status_view"] = status
                results.append(record)
                if record["result"] != "http_error" or record.get("code") != 404:
                    print(f"DISCOVERY {label}: {record['result']} "
                          f"status={record.get('code')} id={record.get('returned_id')}")
        summary = collections.Counter(
            f"{r['result']}:{r.get('code','')}" for r in results if r["game"] == game)
        print(f"GAME {game}: {dict(summary)}")
    output = {
        "league_id_probed": LEAGUE,
        "scope": "isolated private research only; no relationship to existing league asserted",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "authentication_controls": control_results,
        "results": results,
    }
    (OUT / "access_matrix.json").write_text(json.dumps(output, indent=2) + "\n")
    valid = [r for r in results if r["result"] == "http_200"]
    print(f"FINAL: {len(results)} independent league-ID requests; "
          f"{len(valid)} HTTP-200 league matches")
    for r in valid:
        print(f"MATCH game={r['game']} year={r['year']} endpoint={r['endpoint']} "
              f"teams={r.get('team_count')} declared={r.get('declared_season')}")
    print("No public data or main-branch changes were made.")


if __name__ == "__main__":
    main()
