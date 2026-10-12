#!/usr/bin/env python3
"""Read-only ESPN history coverage probe for candidate league 791996.

Writes only sanitized endpoint/season statuses to a temporary Actions artifact.
Never stores API payloads, cookies, team owner details, or changes published data.
"""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

CANDIDATE = 791996
YEARS = range(2010, 2021)
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
OUT = Path("output/research-791996")
CONTROL_ID, CONTROL_YEAR = 1493036707, 2022


def request_json(url, cookie):
    req = urllib.request.Request(url, headers={
        "Cookie": cookie,
        "Accept": "application/json",
        "User-Agent": "Fantasy2KInfinity-ReadOnlyResearch/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            payload = json.load(res)
    except urllib.error.HTTPError as exc:
        return {"status": "http_error", "http_status": exc.code}, None
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"status": "request_error", "error_type": type(exc).__name__}, None
    except (ValueError, UnicodeDecodeError) as exc:
        return {"status": "non_json", "error_type": type(exc).__name__}, None
    if isinstance(payload, list):
        if len(payload) != 1:
            return {"status": "unexpected_array_length", "length": len(payload)}, None
        payload = payload[0]
    if not isinstance(payload, dict):
        return {"status": "unexpected_json_shape"}, None
    return {"status": "json"}, payload


def endpoint(league_id, year, kind, view):
    query = [("seasonId", str(year))] if kind == "history" else []
    if view:
        query.append(("view", view))
    if kind == "history":
        url = f"{BASE}/leagueHistory/{league_id}"
    else:
        url = f"{BASE}/seasons/{year}/segments/0/leagues/{league_id}"
    return url + "?" + urllib.parse.urlencode(query) if query else url


def inspect(year, league_id, kind, view, cookie):
    result, payload = request_json(endpoint(league_id, year, kind, view), cookie)
    record = {"endpoint": kind, "view": view or "no_view", **result}
    if payload is None:
        return record
    try:
        actual_id = int(payload.get("id", -1))
        actual_year = payload.get("seasonId")
        actual_year = int(actual_year) if actual_year is not None else None
    except (ValueError, TypeError):
        record["status"] = "invalid_identity_fields"
        return record
    if actual_id != league_id:
        record["status"] = "league_id_mismatch"
        return record
    if actual_year is not None and actual_year != year:
        record["status"] = "season_mismatch"
        return record
    teams = payload.get("teams")
    schedule = payload.get("schedule")
    record.update(status="retrieved_matching_id", returned_season=actual_year,
                  team_count=len(teams) if isinstance(teams, list) else None,
                  matchup_count=len(schedule) if isinstance(schedule, list) else None,
                  has_settings=isinstance(payload.get("settings"), dict))
    return record


def main():
    s2, swid = os.getenv("ESPN_S2", "").strip(), os.getenv("ESPN_SWID", "").strip()
    if not s2 or not swid:
        raise SystemExit("SAFE ERROR: ESPN Actions credentials are not configured")
    cookie = f"espn_s2={s2}; SWID={swid}"
    OUT.mkdir(parents=True, exist_ok=True)
    control = inspect(CONTROL_YEAR, CONTROL_ID, "modern", "mTeam", cookie)
    print(f"Known-good 2022 control: {control['status']} (HTTP {control.get('http_status', '?')})")
    seasons = []
    for year in YEARS:
        # Legacy format should be preferred for pre-2018; test both forms.
        kinds = ("history", "modern") if year < 2018 else ("modern", "history")
        attempts = []
        for kind in kinds:
            for view in ("mTeam", None):
                record = inspect(year, CANDIDATE, kind, view, cookie)
                attempts.append(record)
                if record["status"] == "retrieved_matching_id":
                    break
            if attempts[-1]["status"] == "retrieved_matching_id":
                break
        found = next((r for r in attempts if r["status"] == "retrieved_matching_id"), None)
        status = "retrieved_matching_id" if found else (
            "not_retrievable_via_tested_endpoints" if all(
                a["status"] == "http_error" and a["http_status"] == 404 for a in attempts)
            else "inconclusive")
        seasons.append({"season": year, "status": status, "attempts": attempts})
        print(f"{year}: {status}; tests={len(attempts)}")
    report = {
        "candidate_league_id": CANDIDATE,
        "status": "RESEARCH_ONLY_UNVERIFIED_NO_PRODUCTION_IMPORT",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "credential_control": {"league_id": CONTROL_ID, "season": CONTROL_YEAR, **control},
        "seasons": seasons,
        "note": "An HTTP 404 is not proof a league did not exist. No identity/continuity inferred.",
    }
    (OUT / "sanitized_coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Sanitized research report written; no production data or source references modified.")


if __name__ == "__main__":
    main()
