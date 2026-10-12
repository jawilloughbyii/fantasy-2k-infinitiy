#!/usr/bin/env python3
"""Retrospective draft grades from original-season ESPN weekly actuals.
Private input; public output contains only sanctioned fantasy fields and anonymous franchises.
Cost benchmark is leave-one-season-out, within-position comparable draft rounds;
2021–22 punters are marked era-only and excluded from cross-era Draft DNA.
"""
import json,math,statistics,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/"reference/historical_draft_picks.json").read_text())
F=json.loads((ROOT/"reference/franchise_continuity.json").read_text())
IN=ROOT/"output/draft-performance"
OUT=ROOT/"reference/historical_draft_grades.json"
REPLACEMENT_RANK={"QB":10,"RB":24,"WR":24,"TE":10,"K":10,"D/ST":10,"P":10}
SPECIAL={"K","D/ST"}
WEIGHTS=[.5,.3,.2]

def mean(a):return sum(a)/len(a) if a else 0
def clean(x):return round(float(x),4)
def records():
    source={}
    for d in D["seasons"][:5]:
        year=d["year"];r=json.loads((IN/f"player_performance_{year}.json").read_text())
        players={p["player_id"]:p for p in r["players"]}
        if r["metadata"]["league_id"]!=d["league_id"]:raise ValueError(f"{year}: source league mismatch")
        if len(players)!=r["metadata"]["all_players"] or len(d["picks"])!=r["metadata"]["drafted_player_count"]:
            raise ValueError(f"{year}: source coverage mismatch")
        for pick in d["picks"]:
            x=players.get(pick["player_id"])
            if not x or x["position"]!=pick["position"]:raise ValueError(f"{year}: draft player/position mismatch")
        # All eligible NFL players in this original-year pool determine positional
        # replacement; do not compare different fantasy scoring systems in raw points.
        groups=collections.defaultdict(list)
        for p in players.values():
            if p["position"] in REPLACEMENT_RANK:
                if len(p["weekly"])!=14 or abs(round(sum(p["weekly"]),2)-p["regular_pf"])>.011:
                    raise ValueError(f"{year}: invalid regular season weekly scoring")
                groups[p["position"]].append(p["regular_pf"])
        baseline={}
        for pos,rank in REPLACEMENT_RANK.items():
            if pos=="P" and year>=2023:continue
            vals=sorted(groups[pos],reverse=True)
            if len(vals)<rank:raise ValueError(f"{year}: missing replacement pool {pos}")
            replacement=vals[rank-1]
            # Unit interval: zero at positional replacement level, one at annual
            # top fantasy scorer for same position under this season's rules.
            peak=max(vals)
            if peak<=replacement:raise ValueError(f"{year}: no {pos} spread for draft model")
            baseline[pos]={"replacement_rank":rank,"replacement_pf":clean(replacement),
                           "top_pf":clean(peak),"pool_size":len(vals)}
        picks=[]
        for pick in d["picks"]:
            player=players[pick["player_id"]];pos=pick["position"];base=baseline[pos]
            actual=max(0,(player["regular_pf"]-base["replacement_pf"])/(base["top_pf"]-base["replacement_pf"]))
            picks.append({**pick,"regular_pf":player["regular_pf"],
                "recorded_scoring_weeks":player["weeks_with_stats"],
                "above_replacement_pf":clean(max(0,player["regular_pf"]-base["replacement_pf"])),
                "normalized_value":clean(actual),
                "draft_round_equivalent":(pick["overall"]-.5)/10,
                "availability_note":("limited_recorded_scoring_weeks" if player["weeks_with_stats"]<=7 else None)})
        source[year]={"year":year,"league_id":d["league_id"],"rounds":d["rounds"],
                      "pool_size":len(players),"benchmarks":baseline,"picks":picks}
    return source

def grade(source):
    # This excludes each evaluated season from its own expected-value cohort.
    # The same drafted position in the OTHER four seasons is weighted by
    # similarity of actual selection round; no modern ADP or scoring imported.
    output=[]
    for year,s in source.items():
        graded=[]
        for p in s["picks"]:
            pos=p["position"]
            if pos=="P":
                graded.append({k:v for k,v in p.items() if k!="draft_round_equivalent"}|{
                    "expected_value":None,"value_added":None,"tag":"ERA_ONLY","elite_hit":False,
                    "draft_weight":0})
                continue
            peers=[t for y,z in source.items() if y!=year for t in z["picks"] if t["position"]==pos]
            if len(peers)<10:raise ValueError(f"{year}: fewer than 10 held-out peers for {pos}")
            weighted=[(math.exp(-abs(t["draft_round_equivalent"]-p["draft_round_equivalent"])/2.25),
                       t["normalized_value"]) for t in peers]
            denom=sum(w for w,_ in weighted)
            expectation=sum(w*v for w,v in weighted)/denom
            actual=p["normalized_value"];delta=actual-expectation
            early=p["round"]<=2
            elite=early and actual>=.75 and delta>=.20
            if not early and delta>=.23 and actual>=.35:tag="STEAL"
            elif expectation>=.32 and delta<=-.23:tag="BUST"
            elif (delta>=.075 and actual>=.25) or elite:tag="HIT"
            else:tag="NEUTRAL"
            cost=.5+1.5*((s["rounds"]-p["round"]+1)/s["rounds"])**1.6
            if pos in SPECIAL:cost*=.5
            graded.append({k:v for k,v in p.items() if k!="draft_round_equivalent"}|{
                "expected_value":clean(expectation),"value_added":clean(delta),
                "tag":tag,"elite_hit":elite,"draft_weight":clean(cost)})
        season_franchises=[]
        ids={p["franchise_id"] for p in graded}
        if len(ids)!=10:raise ValueError("Franchise count mismatch")
        for fid in sorted(ids):
            gp=[p for p in graded if p["franchise_id"]==fid and p["tag"]!="ERA_ONLY"]
            main=[p for p in gp if p["position"] not in SPECIAL]
            early=[p for p in main if p["round"]<=4]
            late=[p for p in main if p["round"]>=8]
            if not gp or not early:raise ValueError(f"{year} franchise {fid}: no qualifying draft selections")
            residual=sum(p["value_added"]*p["draft_weight"] for p in gp)/sum(p["draft_weight"] for p in gp)
            early_hits=sum(p["tag"] in ("STEAL","HIT") or p["normalized_value"]>=p["expected_value"]-.07 for p in early)
            season_franchises.append({"franchise_id":fid,"draft_value_index":clean(100+100*residual),
                "net_value_added":clean(residual),"steal_rate":clean(sum(p["tag"]=="STEAL" for p in main)/len(main)),
                "bust_rate":clean(sum(p["tag"]=="BUST" for p in main)/len(main)),
                "early_hit_rate":clean(early_hits/len(early)),
                "late_value_added":clean(mean([p["value_added"] for p in late])),
                "eligible_picks":len(gp),"skill_picks":len(main)})
        output.append({"year":year,"league_id":s["league_id"],"benchmarks":s["benchmarks"],
                       "pool_size":s["pool_size"],"picks":graded,"franchises":season_franchises})
    return output

def dna(seasons):
    byfid=collections.defaultdict(list)
    for s in seasons:
        for f in s["franchises"]:byfid[f["franchise_id"]].append({"year":s["year"],**f})
    result=[]
    for fid,rows in sorted(byfid.items()):
        rows.sort(key=lambda x:x["year"],reverse=True)
        recent=rows[:3];weights=WEIGHTS[:len(recent)];weights=[w/sum(weights) for w in weights]
        metrics={}
        for key in ("draft_value_index","net_value_added","steal_rate","bust_rate","early_hit_rate","late_value_added"):
            metrics[key]=clean(sum(x[key]*w for x,w in zip(recent,weights)))
        if len(rows)<3:profile="INSUFFICIENT_HISTORY"
        elif metrics["steal_rate"]>=.15 and metrics["late_value_added"]>=.12:profile="Value Hunter"
        elif metrics["early_hit_rate"]>=.65 and metrics["net_value_added"]>=.06:profile="Early-Round Anchor"
        elif metrics["steal_rate"]>=.12 and metrics["bust_rate"]>=.12:profile="High-Variance Drafter"
        elif metrics["net_value_added"]<=-.06 and metrics["early_hit_rate"]<.50:profile="Draft Capital Underperformer"
        elif metrics["net_value_added"]>=0 and metrics["bust_rate"]<=.10:profile="Balanced Builder"
        else:profile="Mixed Returns"
        result.append({"franchise_id":fid,"completed_seasons":[r["year"] for r in rows],
                       "recent_year_weights":[{"year":x["year"],"weight":clean(w)} for x,w in zip(recent,weights)],
                       **metrics,"profile":profile})
    return result

def main():
    source=records();years=grade(source);fingerprints=dna(years)
    grades=collections.Counter(p["tag"] for s in years for p in s["picks"])
    assert sum(grades.values())==820 and grades["ERA_ONLY"]==20
    assert len(fingerprints)==11
    out={"status":"retrospective_verified_model_v1","source":"Original-season ESPN league-scored weekly actuals, 14 regular-season weeks, full eligible player pool per season; matched to verified ESPN draft player IDs and permanent franchise keys.",
         "methodology":{"scoring_weeks":"1–14 only; missing actual weekly stat is zero for retrospective total",
          "replacement_ranks":REPLACEMENT_RANK,
          "value":"Max(0, player regular PF - seasonal positional replacement PF)/(annual top positional PF - replacement PF)",
          "expected_value":"Leave evaluated season out; weighted same-position drafted players from other completed seasons, round proximity exponential exp(-absolute round difference/2.25).",
          "value_added":"Actual normalized value minus held-out expected normalized value; positive means above historical draft-cost expectation.",
          "tag_steal":"After round 2, value_added >= .23 and normalized_value >= .35",
          "tag_bust":"Expected normalized value >= .32 and value_added <= -.23",
          "tag_hit":"Value_added >= .075 and normalized_value >= .25, or first-two-round elite hit",
          "tag_neutral":"Neither STEAL, BUST nor HIT; a zero-producing late pick is not automatically a bust.",
          "elite_hit":"Round 1 or 2 with normalized_value >= .75 and value_added >= .20 (display as hit, not a steal).",
          "special_teams":"K and D/ST carry half capital weight; P receives ERA_ONLY and is excluded from cross-era Draft DNA.",
          "availability":"limited_recorded_scoring_weeks is a descriptive stat coverage flag when <=7 weeks; NOT an injury diagnosis.",
          "draft_value_index":"100 + 100 times season capital-weighted value_added (100 represents expected-value baseline).",
          "historical_dna":"Latest up to 3 completed seasons for each original owner-franchise, recency weights 50/30/20 normalized, 2026 excluded; profiles require at least 3 seasons.",
          "scope":"Retrospective fantasy production vs league's original actual draft cost, not manager roster utilization, injury causality, or in-season decision quality."},
         "coverage":{"seasons":[s["year"] for s in years],"pick_count":820,"era_only_punters":20,
                     "full_player_pool_count":sum(s["pool_size"] for s in years)},
         "tag_counts":dict(grades),
         "seasons":years,"franchise_dna":fingerprints}
    text=json.dumps(out,ensure_ascii=False,separators=(",",":"))+"\n"
    for token in ("espn_s2","espn_swid","owner_name","manager_name","session_cookie"):
        if token in text.lower():raise ValueError("Sensitive field in public draft grade snapshot")
    OUT.write_text(text)
    print("GRADE VALIDATION: 820/820 picks, 5 seasons, 11 owner-linked franchises.")
    print("TAG COUNTS: "+json.dumps(dict(grades),sort_keys=True))
    print("FINGERPRINTS: "+json.dumps([{k:d[k] for k in ("franchise_id","completed_seasons","draft_value_index","profile")} for d in fingerprints]))
    print(f"Prepared {OUT}, no site/dashboard change.")
if __name__=="__main__":main()
