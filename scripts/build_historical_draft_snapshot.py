#!/usr/bin/env python3
"""Approve only 980 verified named picks from season-specific ESPN drafts."""
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
IN=ROOT/"output"/"draft-coverage"
OUT=ROOT/"reference"/"historical_draft_picks.json"
IDENTITY=json.loads((ROOT/"reference"/"franchise_continuity.json").read_text())
HISTORY=json.loads((ROOT/"reference"/"historical_regular_season_scores.json").read_text())
CURRENT=json.loads((ROOT/"data"/"league.json").read_text())
CURRENT_IDS=json.loads((ROOT/"reference"/"team_id_map.json").read_text())
POSITIONS={1:"QB",2:"RB",3:"WR",4:"TE",5:"K",7:"P",16:"D/ST"}
EXPECTED={2021:170,2022:170,2023:160,2024:160,2025:160,2026:160}
historical={s["year"]:{int(t["espn_team_id"]):t["name"] for t in s["teams"]} for s in HISTORY["seasons"]}
now={int(CURRENT_IDS["baseline_to_espn"][str(t["id"])]):t["name"] for t in CURRENT["teams"]}
output={"source":"Authenticated ESPN mDraftDetail; player names and positions from each season's ESPN players_wl. Verified 2026-10-12. Franchise identity uses the confirmed (season, league, ESPN slot) reference.",
        "status":"verified_picks_not_performance_grades",
        "coverage":{"years":[2021,2022,2023,2024,2025,2026],"pick_count":980,"team_seasons":60,
                    "historical_punter_drafts":[2021,2022]},
        "seasons":[]}
for year,n in EXPECTED.items():
    row=json.loads((IN/f"draft_{year}.json").read_text())
    meta,picks=row["metadata"],row["picks"]
    assert meta["year"]==year and meta["source_league_id"]==IDENTITY["league_ids_by_season"][str(year)]
    assert meta["drafted"] is True and meta["in_progress"] is False and meta["draft_type"]=="SNAKE"
    assert len(picks)==n and meta["resolved_player_names"]==n and not meta["unresolved_player_ids"]
    ids=set(map(int,IDENTITY["season_to_franchise"][str(year)]))
    assert len(ids)==10 and {int(p["teamId"]) for p in picks}==ids
    names=historical[year] if year in historical else now
    assert set(names)==ids, f"{year}: team names not matched"
    assert [p["overallPickNumber"] for p in picks]==list(range(1,n+1))
    assert len({p["playerId"] for p in picks})==n, f"{year}: draft player duplicated"
    assert all(Counter(p["teamId"] for p in picks)[tid]==n//10 for tid in ids)
    for p in picks:
        rnd,slot=p["roundId"],p["roundPickNumber"]
        assert rnd==(p["overallPickNumber"]-1)//10+1
        assert slot in range(1,11)
        assert isinstance(p["playerName"],str) and p["playerName"].strip()
        assert p["positionId"] in POSITIONS, (year,p["playerId"],p["positionId"])
    if year<=2022:
        assert Counter(p["positionId"] for p in picks)[7]==10, f"{year}: missing 10 punters"
    else:assert not any(p["positionId"]==7 for p in picks)
    o={"year":year,"league_id":meta["source_league_id"],"draft_type":"SNAKE",
       "rounds":n//10,"total_picks":n,"historical_punter_position":year<=2022,
       "teams":[{"espn_team_id":tid,"season_team_name":names[tid],
                 "franchise_id":IDENTITY["season_to_franchise"][str(year)][str(tid)]}
                for tid in sorted(ids)],
       "picks":[{"overall":p["overallPickNumber"],"round":p["roundId"],"round_pick":p["roundPickNumber"],
                 "espn_team_id":p["teamId"],
                 "franchise_id":IDENTITY["season_to_franchise"][str(year)][str(p["teamId"])],
                 "player_id":p["playerId"],"player_name":p["playerName"],"position":POSITIONS[p["positionId"]]}
                for p in picks]}
    output["seasons"].append(o)
    print(f"{year}: validated {n} ESPN picks; {len(ids)} unique franchises; "
          f"{o['rounds']} rounds; player names complete; {'punters present' if year<=2022 else 'no punters'}")
assert sum(len(s["picks"]) for s in output["seasons"])==980
assert len({t["franchise_id"] for s in output["seasons"] for t in s["teams"]})==11
text=json.dumps(output,ensure_ascii=False,separators=(",",":"))+"\n"
for token in ("espn_s2","espn_swid","manager_name","owner_name","session_cookie"):
    assert token not in text.lower()
OUT.write_text(text,encoding="utf-8")
print(f"Approved public, anonymous draft snapshot: {OUT} ({len(text)} chars)")
