#!/usr/bin/env python3
"""Promote only exhaustively reconciled 2014-17 player, scoring, official-record data.

Consumes the sanitized same-run authenticated ESPN source audit, NEVER raw ESPN
owner/member payloads. Fails closed rather than creating partial draft boards.
"""
import collections,json,math,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
AUDIT=ROOT/"output/legacy-2014-17-verification/source_review.json"
DRAFT=ROOT/"reference/historical_legacy_draft_picks_2014_2017.json"
SCORES=ROOT/"reference/historical_regular_season_scores.json"
RULES=ROOT/"reference/historical_legacy_scoring_2014_2017.json"
RECORDS=ROOT/"reference/historical_legacy_official_standings_2014_2017.json"
POSITION={1:"QB",2:"RB",3:"WR",4:"TE",5:"K",7:"P",16:"D/ST"}
YEARS=[2014,2015,2016,2017]

def die(msg):raise ValueError(msg)
def write(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
def num(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):die("Invalid ESPN numeric record")
    return round(x,2)

def main():
    source=json.loads(AUDIT.read_text(encoding="utf-8"))
    if source.get("status")!="PRIVATE_RESEARCH_NOT_APPROVED" or source.get("source_league_id")!=791996:die("Invalid source")
    if [s["year"] for s in source["seasons"]]!=YEARS:die("Incomplete source years")
    drafts=json.loads(DRAFT.read_text(encoding="utf-8"))
    scores=json.loads(SCORES.read_text(encoding="utf-8"))
    if [s["year"] for s in drafts["seasons"]]!=YEARS or drafts["coverage"]["pick_count"]!=680:die("Incomplete original picks")
    if [s["year"] for s in scores["seasons"][:4]]!=YEARS:die("Source year mismatch")
    scored=[];official=[]
    for s in source["seasons"]:
        y=s["year"]
        d=next(x for x in drafts["seasons"] if x["year"]==y)
        hs=next(x for x in scores["seasons"] if x["year"]==y)
        pool=s["draft_player_lookup"];players=pool["players"]
        if pool["matched"]!=170 or pool["missing"]!=0 or len(players)!=170:die(f"{y}: partial player lookup")
        lookup={p["player_id"]:p for p in players}
        if len(lookup)!=170 or set(lookup)!={p["player_id"] for p in d["picks"]}:die(f"{y}: player ID mismatch")
        if any(p.get("source_route")!="season_players" or p.get("position_id") not in POSITION or
               p.get("position")!=POSITION[p["position_id"]] or not p.get("name") for p in players):
            die(f"{y}: source year player metadata not verified")
        for pick in d["picks"]:
            p=lookup[pick["player_id"]]
            pick["player_name"]=p["name"]
            pick["position"]=p["position"]
            pick["player_metadata_source"]="ESPN_season_players_wl_exact_original_draft_id"
        d["player_enrichment"]="complete_original_year_ESPN_170_of_170"
        settings=s["scoring"]
        expected=47 if y==2014 else 50
        if settings["scoring_type"]!="H2H_POINTS" or settings["item_count"]!=expected or len(settings["items"])!=expected:die(f"{y}: rule count mismatch")
        if not any(k=="18" and v==1 for k,v in settings["lineup_slot_counts"].items()):die(f"{y}: no original punter slot")
        original=json.loads((ROOT/f"research/espn-791996-2014-2017/season_{y}.json").read_text())
        if settings["lineup_slot_counts"]!=original["settings"]["lineup_slot_counts"]:die(f"{y}: source lineup mismatched")
        if expected!=original["settings"]["scoring_item_count"]:die(f"{y}: original archived scoring count mismatched")
        scored.append({"year":y,"league_id":791996,"source":"authenticated_ESPN_leagueHistory_mSettings",
                       "scoring_type":settings["scoring_type"],"scoring_item_count":expected,
                       "lineup_slot_counts":settings["lineup_slot_counts"],"items":settings["items"]})
        reported=s["standings"]
        if len(reported)!=10 or {x["team_id"] for x in reported}!=set(range(1,11)):die(f"{y}: official coverage")
        rows=[]
        for row in reported:
            official_row=row["espn_overall"]
            derived=row["derived"]
            if any(k not in official_row for k in ("wins","losses","ties","pointsFor","pointsAgainst")):die(f"{y}: incomplete ESPN official record")
            for src,calc in (("wins","wins"),("losses","losses"),("ties","ties"),("pointsFor","points_for"),("pointsAgainst","points_against")):
                if num(official_row[src])!=num(derived[calc]):die(f"{y}: mismatch team {row['team_id']} {src}")
            if sum(official_row[k] for k in ("wins","losses","ties"))!=14:die(f"{y}: incomplete team record")
            original_row=next(x for x in original["standings"]["rows"] if x["espn_team_id"]==row["team_id"])
            if any(num(original_row[calc])!=num(derived[calc]) for calc in ("wins","losses","ties","points_for","points_against")):
                die(f"{y}: original archive mismatch")
            rows.append({"espn_team_id":row["team_id"],"name":row["team_name"],
                        "wins":int(official_row["wins"]),"losses":int(official_row["losses"]),
                        "ties":int(official_row["ties"]),
                        "points_for":num(official_row["pointsFor"]),"points_against":num(official_row["pointsAgainst"])})
        official.append({"year":y,"league_id":791996,"official_ranking_available":False,
                         "ranking_note":"ESPN mTeam record.overall returned W/L/T, PF and PA, not official seed/rank; standings display remains derived.",
                         "source":"authenticated_ESPN_leagueHistory_mTeam_record_overall",
                         "record_count":len(rows),"reconciled_count":len(rows),"rows":sorted(rows,key=lambda x:x["espn_team_id"])})
        hs["standings_verification"]={"source":"ESPN_mTeam_record_overall",
            "record_count":10,"wins_losses_ties_pf_pa":"all_10_exactly_reconciled",
            "official_seed_order":"not_returned_do_not_infer"}
        hs["scoring_environment"]["scoring_rule_reference"]="reference/historical_legacy_scoring_2014_2017.json"
        hs["scoring_environment"]["scoring_item_count"]=expected
        print(f"{y}: player_names=170/170, scoring_rule_items={expected}, official records=10/10 reconciled")
    drafts["status"]="verified_original_year_player_metadata_complete"
    drafts["source"]+=" Names and positions verified from each original season's ESPN seasons/{year}/players?view=players_wl via exact draft player IDs."
    drafts["coverage"]["named_picks"]=680
    drafts["coverage"]["positioned_picks"]=680
    write(DRAFT,drafts);write(SCORES,scores)
    write(RULES,{"source":"Authenticated ESPN historical league 791996 mSettings; original per-year scoring points and overrides retained by stat ID, no modern scoring substituted","status":"verified_source_scoring_definitions","seasons":scored})
    write(RECORDS,{"source":"Authenticated ESPN historical league 791996 mTeam record.overall compared against all 280 original matchup results","status":"verified_official_wlt_pf_pa_official_rank_not_returned","seasons":official})
    print("PROMOTION PASS: original draft metadata, exact scoring rules, original ESPN regular-season W/L/T PF PA reconciled.")

if __name__=="__main__":
    try:main()
    except (ValueError,KeyError,TypeError) as e:raise SystemExit("SAFE ERROR: "+str(e))
