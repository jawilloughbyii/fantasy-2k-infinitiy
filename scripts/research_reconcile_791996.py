#!/usr/bin/env python3
"""Read-only, privacy-safe ESPN team ownership continuity evidence.

Queries existing GitHub-secret-authenticated ESPN sources. Raw owner/member values
exist only in process memory: no hashes, usernames, names of people, cookies,
member payloads, raw API bodies or raw owner identifiers are printed, saved or
committed. A report may contain team names and already-public anonymous franchise
keys, accompanied by explicit source limitations. It NEVER changes published maps.
"""
import collections
import datetime as dt
import json
import os
import pathlib
import urllib.parse
import urllib.request
import urllib.error

ROOT=pathlib.Path(__file__).resolve().parents[1]
H=json.loads((ROOT/'reference/historical_regular_season_scores.json').read_text())
F=json.loads((ROOT/'reference/franchise_continuity.json').read_text())
OUTPUT=pathlib.Path('output/private-reconciliation-791996')
YEARS=tuple(range(2014,2018))+tuple(range(2021,2027))
SOURCE={y:(791996 if y<=2017 else 1493036707 if y<=2022 else 418244680) for y in YEARS}
URL="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"

def fetch(year,view,cookie):
    league=SOURCE[year]
    if year<2018:
        address=f"{URL}/leagueHistory/{league}?"
        q=[("seasonId",str(year)),("view",view)]
    else:
        address=f"{URL}/seasons/{year}/segments/0/leagues/{league}?"
        q=[("view",view)]
    req=urllib.request.Request(address+urllib.parse.urlencode(q),
      headers={"Cookie":cookie,"Accept":"application/json","User-Agent":"Fantasy-2K-read-only-reconciliation/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=30) as response:
            obj=json.load(response)
    except urllib.error.HTTPError as exc:
        return None,{"status":"http_error","http_status":exc.code}
    except (urllib.error.URLError,TimeoutError,ValueError,UnicodeDecodeError) as exc:
        return None,{"status":"request_error","error_type":type(exc).__name__}
    if isinstance(obj,list):
        if len(obj)!=1:return None,{"status":"history_response_length","count":len(obj)}
        obj=obj[0]
    if not isinstance(obj,dict):
        return None,{"status":"invalid_payload"}
    if int(obj.get("id",-1))!=league or (obj.get("seasonId") is not None and int(obj["seasonId"])!=year):
        return None,{"status":"league_or_season_mismatch"}
    return obj,{"status":"retrieved"}

def scalar_id(x):
    if isinstance(x,dict):
        # ESPN mTeam owners can be strings or member objects with an id
        x=x.get("id")
    if isinstance(x,bool) or not isinstance(x,(str,int)):return None
    v=str(x).strip().lower()
    return v if v and v not in ("0","none","null","-1") else None

def team_owners(team):
    raw=team.get("owners")
    if isinstance(raw,list):
        result=set(filter(None,(scalar_id(x) for x in raw)))
    else:
        result=set()
    for key in ("primaryOwner","ownerId"):
        v=scalar_id(team.get(key))
        if v:result.add(v)
    return result

def prepare_teams(year,payload):
    expected={t["espn_team_id"]:t["name"] for s in H["seasons"] if s["year"]==year for t in s["teams"]}
    teams=payload.get("teams") or []
    if not isinstance(teams,list) or len(teams)!=10 or {t.get("id") for t in teams}!=set(range(1,11)):
        raise ValueError(f"{year}: unexpected ESPN team coverage")
    # Match display names for old seasons; do not fail modern years due later rename.
    if year<=2017:
        for t in teams:
            name=str(t.get("name") or " ".join(str(t.get(k) or "") for k in ("location","nickname"))).strip()
            if name!=expected[t["id"]]:
                raise ValueError(f"{year}: recovered team display name mismatch for slot {t['id']}")
    return teams

def draft_members(source):
    details=source.get("draftDetail") if source else None
    picks=details.get("picks") if isinstance(details,dict) else None
    owners=collections.defaultdict(set)
    if not isinstance(picks,list):
        return owners,{"status":"no_draft_picks"}
    for p in picks:
        if not isinstance(p,dict):continue
        tid=p.get("teamId")
        id=scalar_id(p.get("memberId"))
        if type(tid) is int and tid in range(1,11) and id:
            owners[tid].add(id)
    return owners,{"status":"retrieved","picks":len(picks),
                  "team_slots_with_draft_member":sum(bool(v) for v in owners.values()),
                  "team_slots_with_multiple_draft_members":sum(len(v)>1 for v in owners.values())}

def main():
    s2,swid=os.getenv("ESPN_S2","").strip(),os.getenv("ESPN_SWID","").strip()
    if not s2 or not swid:raise SystemExit("SAFE ERROR: Required ESPN Actions credentials missing")
    cookie=f"espn_s2={s2}; SWID={swid}"
    records={}
    diagnostics=[]
    for year in YEARS:
        source,info=fetch(year,"mTeam",cookie)
        row={"season":year,"league_id":SOURCE[year],"mTeam":info}
        if source is None:
            diagnostics.append(row)
            print(f"{year}: mTeam={info['status']}")
            continue
        teams=prepare_teams(year,source)
        draft,di=fetch(year,"mDraftDetail",cookie)
        members,dstatus=draft_members(draft)
        row["mDraftDetail"]={**di,**dstatus}
        row["team_slots_with_espn_owner"]=sum(bool(team_owners(t)) for t in teams)
        row["team_slots_with_multiple_espn_owners"]=sum(len(team_owners(t))>1 for t in teams)
        # Identifiers are used only in-memory and never copied to report rows.
        records[year]={t["id"]:{"owner":team_owners(t),"draft":members.get(t["id"],set())} for t in teams}
        diagnostics.append(row)
        print(f"{year}: 10 verified slots; owner-bearing={row['team_slots_with_espn_owner']}, "
              f"draft-member-bearing={dstatus.get('team_slots_with_draft_member',0)}")
    if not all(year in records for year in range(2014,2018)):
        raise SystemExit("SAFE ERROR: Missing one or more source-authentic 2014–2017 team snapshots")
    # Match same evidence channel only; never compare arbitrary owner and drafter identifiers.
    modern=collections.defaultdict(lambda:collections.defaultdict(set))
    for y in range(2021,2027):
        if y not in records:continue
        refs=F["season_to_franchise"][str(y)]
        if SOURCE[y]!=F["league_ids_by_season"][str(y)]:
            raise ValueError(f"{y}: source league disagrees with confirmed mapping")
        for tid,v in records[y].items():
            fid=refs[str(tid)]
            for channel in ("owner","draft"):
                for value in v[channel]:
                    modern[channel][value].add(fid)
    old=collections.defaultdict(lambda:collections.defaultdict(list))
    for y in range(2014,2018):
        for tid,v in records[y].items():
            for channel in ("owner","draft"):
                for value in v[channel]:
                    old[channel][value].append((y,tid))
    seasons={}
    for y in range(2014,2018):
        names={t["espn_team_id"]:t["name"] for s in H["seasons"] if s["year"]==y for t in s["teams"]}
        rows=[]
        for tid in range(1,11):
            r=records[y][tid]
            same_era=collections.defaultdict(set)
            for channel in ("owner","draft"):
                for value in r[channel]:
                    for other_year,other_slot in old[channel][value]:
                        if other_year!=y:same_era[other_year].add(other_slot)
            # Only unique cross-era references are shown as candidate identities.
            hit=collections.defaultdict(set)
            conflicting=[]
            for channel in ("owner","draft"):
                for value in r[channel]:
                    fids=modern[channel].get(value,set())
                    if len(fids)==1:
                        hit[channel].update(fids)
                    elif len(fids)>1:
                        conflicting.append(channel)
            both=set.intersection(*[hit[c] for c in ("owner","draft")]) if all(hit.values()) else set()
            combined=hit["owner"] | hit["draft"]
            suggested=next(iter(combined)) if len(combined)==1 and not conflicting else None
            evidence="two_channels" if len(both)==1 and suggested in both else "one_channel" if suggested else "none_or_conflict"
            rows.append({"espn_team_id":tid,"historical_team":names[tid],
              "ownership_source_count":len(r["owner"]),"draft_member_source_count":len(r["draft"]),
              "within_2014_2017_evidence":{str(yr):sorted(slots) for yr,slots in sorted(same_era.items())},
              "candidate_modern_franchise_id":suggested,
              "evidence":evidence,
              "source_channels":sorted(k for k,v in hit.items() if v and suggested in v),
              "unresolved_source_conflict":bool(conflicting or len(combined)>1),
              "disposition":"CANDIDATE_NOT_PUBLISHED_REQUIRES_CONFIRMATION"})
        seasons[str(y)]=rows
    # Avoid source alias and team ID silently becoming approved manager links.
    OUTPUT.mkdir(parents=True,exist_ok=True)
    report={"status":"READ_ONLY_PRIVATE_RESEARCH_CANDIDATES_ONLY",
      "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "league_id":791996,"source_years":list(YEARS),
      "method":"Exact ESPN owner IDs and independently draft member IDs, compared only within matching evidence channels in runner memory; neither IDs nor hashes persisted",
      "limitations":["Account owner is evidence of account continuity, not definitive proof of which participant managed the team",
         "Co-managed or transferred team slots can be ambiguous","Only user-confirmed modern franchise IDs considered",
         "The 2018–2020 seasons are not recovered","No mappings or title counts are published from this report"],
      "diagnostics":diagnostics,"seasons":seasons}
    (OUTPUT/"identity_candidates.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    for y,rows in seasons.items():
        counts=collections.Counter(r["evidence"] for r in rows)
        print(f"{y}: {dict(counts)}; conflicting={sum(r['unresolved_source_conflict'] for r in rows)}")
    print("Only a sanitized, unapproved research report was written; no raw ESPN member identifiers.")

if __name__=="__main__":
    try:main()
    except (ValueError,TypeError,KeyError) as exc:
        raise SystemExit("SAFE ERROR: "+str(exc))
