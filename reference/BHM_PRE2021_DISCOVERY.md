# Pre-2021 BHM ESPN discovery — league 1435116

Research date: October 12, 2026. The user supplied ESPN league ID **1435116** as the source for BHM Trois / Quatre, before 2021. The exact calendar years for those two seasons have **not** been established from this source.

## What was actually checked

- Authenticated `lm-api-reads.fantasy.espn.com` modern season endpoint for every year **2010–2020**, including multiple data views
- Authenticated `/leagueHistory/1435116?seasonId=YEAR` endpoint for every year **2010–2020**, including the required historical one-element-array response handling
- Explicit endpoint compatibility matrix for 2015–2021, covering *no view*, `mTeam`, `mSettings`, and `mMatchupScore`, on both endpoints
- Legacy `fantasy.espn.com` host, 2019–2020, using single `mTeam` queries in modern/history formats
- Authenticated **positive control**: 2022 league `1493036707`, `mTeam`, returned HTTP 200 and the requested league ID with the same GitHub secrets

## Observed results

Every tested modern/history request for league **1435116** on the authenticated ESPN read host returned **HTTP 404**. The alternate public host yielded non-JSON responses for its four checks and thus did not provide usable league data. The known 2022 control succeeded.

These results **do not prove that BHM Trois or Quatre did not exist**. They establish only that their season records were *not retrievable through the tested ESPN interfaces using the available authentication*. Causes such as source league ID mismatch, missing archived record, different source game/season, or an inaccessible retired league have **not** been distinguished.

No teams, points, scoring rules, draft picks, postseason games, trophies, or season-to-franchise identities for this earlier era have been verified. There is **no basis for a public backfill or expanding Historical Team DNA** from this result.

## Exact private evidence

- [Initial read-only 2010–2020 discovery](https://github.com/jawilloughbyii/fantasy-2k-infinitiy/actions/runs/38305085068)
- [Modern + legacy history endpoint discovery](https://github.com/jawilloughbyii/fantasy-2k-infinitiy/actions/runs/38305195807)
- [No-view and single-view endpoint matrix](https://github.com/jawilloughbyii/fantasy-2k-infinitiy/actions/runs/38305322285)
- [Known-good 2022 control and alternate host check](https://github.com/jawilloughbyii/fantasy-2k-infinitiy/actions/runs/38305441553)

Artifacts have seven-day retention and contain only sanitized status and league-source diagnostics. Re-run the workflow for later reconciliation; never publish raw ESPN authenticated responses or cookies.

## Required next evidence

Obtain the actual ESPN **League History URL showing BHM Trois or Quatre**, including its `seasonId` / selected year, or a commissioner-provided ESPN archived-season/export record. Reconcile the URL's game, year and league ID against `1435116` before expanding to scores, playoffs, drafts, owner continuity, or championships. If ESPN has retired access to that league, an authenticated export or screenshots can establish a limited, clearly sourced reconstruction.

**Publication gate:** preserve the current 2021–2026 history and all associated identities unchanged until a source year and at least one independently verifiable original-season record have been recovered.
