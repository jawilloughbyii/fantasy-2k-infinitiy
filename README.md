# Fantasy 2K Infinity

A read-only, mobile-friendly fantasy football league report for the 2026 season. The public site displays anonymous team names, approved final matchup scores and verified finalized roster summaries. ESPN credentials remain GitHub Actions secrets and are never part of published JSON.

## Dashboard sections

There are **three primary destinations** on both desktop and mobile:

- **Overview:** one PF-ranked compact league table (all ten teams), current form, and the sole season luck headline, **extra wins** (actual wins minus all-play expected wins). Selecting a team opens its report card. Detailed, existing historical schedule reshuffles (**What if?**) and **How the numbers work** are available in collapsed disclosures, not independent tabs. The calculation guide has five independently expandable topics: Results & Schedule Luck, Scoring & Team DNA, Lineup Quality, Historical Franchise DNA, and Data & Reliability. Presentation notes are deliberately minimal: standings show their PF ordering, luck shows positive/negative direction, the scoring map keeps the actual axis splits, lineup keeps its finalized-hindsight caveat, and History distinguishes scoring rank from W–L standings and displays only verified titles. Repeated methodology beneath cards has been removed; the glossary remains the source for how metrics are computed. Each metric describes what it measures, its calculation and how to interpret the result in plain English, with thresholds drawn from the canonical metric definitions. The duplicate selected-team hero, redundant KPI tiles and Overview lineup panel are removed.
- **Teams:** shared selected-franchise context with three accessible subviews. **Report Card** retains current DNA, extra wins, Starter-Worthy Rate, four secondary benchmarks (all-play, PF/week, recent form and ceiling captured), three weekly micro-trends, and one explanation. **Team DNA** opens with one compact two-column Scoring Identity card: **Currently (2026)** versus **Historically (recency-weighted)**, with a short alignment/divergence statement and a small current momentum badge. The detailed historical scoring strength, volatility, consistency, annual weights and lifetime baseline live in one collapsed Historical Metrics disclosure. The interactive Scoring Personality Map follows the summary; current-season trajectories expand below the map. **Lineup** owns deep SWR, legal roster ceiling, bench opportunities, weekly starter detail, weekly matchups and any separately verified pregame projections. Source calculations and historical franchise rules are unchanged.
- **History:** **Yearbook** ranks 2021–2025 by verified *regular-season PF*. The 2021–2022 seasons retain the old league's punter-inclusive scoring, while the champion field says **Not verified** because archived championship winners have not been confirmed. The 2023–2025 yearbooks continue to display their independently verified champions. It does **not** represent scoring order as official standings, or infer division-dependent playoff selection. **Franchise Legacy** connects historical team names across drafts using verified franchise IDs and shows season-level PF versus league, CV and DNA. **Championships** shows only the documented 2023–2025 winning franchises and their historical aliases. A complete bracket remains deferred until postseason rules are confirmed.

Preserved calculations include schedule reshuffle distributions, all-play and luck, CV and scoring history, legal-lineup optimization, and the 50/30/20 Historical DNA weighting. Only one persistent data-status badge is shown, indicating the latest approved completed week and disclosing use of the approved embedded fallback when needed. The approved 2026 `data/league.json` data model and public ESPN credentials policy are unchanged. Current-year data and history use independent approved sources.

Definitions shared by the Python builder and the browser live in [reference/metric_definitions.json](reference/metric_definitions.json). `scripts/sync_site_snapshot.py` embeds approved 2026 data, historical scoring and verified championship metadata in the HTML fallback. Change the canonical reference files rather than creating independent UI categories.

## Recovered original league history (2014–2017)

ESPN league **791996** (`Horny Bryant Men Pt. Deux`) is user-confirmed as the original competition. Four authenticated archived seasons, 2014–2017, are merged into the **History → Yearbook** alongside 2021–2025. Each has ten teams, 14 regular-season weeks, 70 final games and 140 team-week scores; all four source season records are preserved in `research/espn-791996-2014-2017/`. Original-era scoring includes a punter; league-relative comparisons are preferred over raw cross-era PF. The 2018–2020 bridge has not been recovered.

The **History → Championships** archive includes the ESPN-confirmed 2014, 2016 and 2017 winners brackets, while the 2015 ESPN final winner is explicitly provisional because archived semifinal advancement conflicts with the listed finalists. None of these titles is credited to a modern owner-franchise without explicit continuity verification; existing 2021–2025 trophies and brackets remain unchanged.

**History → Draft History** also includes 680 original ESPN selections (170 each year; ten teams, 17 rounds). Original ESPN player IDs, including valid negative team-defense IDs, are preserved in `reference/historical_legacy_draft_picks_2014_2017.json`. Old-era player-name and position enrichment, retrospective grades, and permanent franchise mappings are pending, so the UI labels those fields rather than inventing them. The original 2021–2026 draft records and 2021–2025 grading/DNA baselines are unchanged. `scripts/test_legacy_history.py` reconciles source week scores, original picks, archive totals and postseason caveats. The 2026 live dashboard source `data/league.json` is unchanged.

## Original-era championship trophies

The unified **History** view now awards source-verified **season-specific** trophies in 2014 (Sleazy Veasey's Teenie Peenie), 2016 (Jaqiuzz so much I Philip Rivers), and 2017 (The Bear Jew). The verified historical team names display the existing shared trophy marker in Yearbook, the Championship Archive/bracket, and original ESPN draft boards. The championship summary includes these three titles alongside the five previously verified 2021–2025 titles. The **2015** ESPN final is shown as disputed but receives **no trophy**, because semifinal winner fields conflict with the reported finalists.

The original ESPN league ID `791996` is user-confirmed, but permanent manager-franchise continuity with 2021–2026 is not yet verified. The three old-era championship records live separately under `legacy_champions` in `reference/championship_history.json`, with a null franchise ID and explicit original league ID. They **do not increase current-team title totals** or inherit modern franchise aliases until identity reconciliation is confirmed. The 2021–2025 owner-linked title reference remains intact.

## Verified championship markers

Every displayed team name uses the same franchise-keyed championship marker, including Overview standings, matchup opponents, Team Cards, Team DNA (including map labels), Who got lucky?, What if?, and the team selector. The current-season marker is one trophy per confirmed title-winning owner-franchise (with year(s) in the accessible label and a count for multiple titles). Historical-season team names show a trophy only if that particular year's title is confirmed; past names do not inherit future trophies. Currently verified: 2023 The Load Warriors (now Project Haily Mary), 2024 Mike Oxlong (now The Domestic House Cats), and 2025 General's Dorm Room. Quattro Padres has no verified title in the available records and gets no marker. Historical aliases resolve using the explicit season + ESPN ID map in `reference/franchise_continuity.json`, not by name. The published 2026 `data/league.json` model is unchanged; the HTML's public owner-free metadata is synchronized from `reference/championship_history.json`, `reference/franchise_continuity.json`, and `reference/team_id_map.json` by `scripts/sync_site_snapshot.py`. History now displays verified regular-season scoring yearbooks and winning franchises; unverified playoff qualification and full brackets remain deferred.

## Historical Franchise Fingerprint (Team DNA)

Teams → Team DNA shows a completed-season **Franchise Fingerprint** directly below Current Scoring Identity inside the same identity card, before the Scoring Personality Map. The historical category and current-versus-historical comparison are immediately visible next to Current DNA, while league-adjusted historical strength, volatility, consistency, annual results and weights expand on demand. The default card is intentionally brief on mobile. It is rendered once, not repeated in a second card. The current 2026 season stays separate and provisional; it never enters the historical baseline until completed and verified. Source: `reference/historical_regular_season_scores.json`, a sanitized 700-team-week extract of finalized 2021–2025 ESPN regular-season scores. The 2021–2022 scores came from old ESPN league 1493036707 (validated private run 38288934702), while 2023–2025 came from league 418244680 (private discovery run 38146729094). Fourteen weeks per season; playoffs are excluded. `scripts/test_historical_dna.py` reconciles 2021–2025 season totals, every team/week, source ESPN league IDs, franchise identities and calculations.

The rolling fingerprint uses the latest three completed seasons of the **same permanent franchise**, weights 50% most recent / 30% prior / 20% third. When only two are known, renormalize to 62.5% / 37.5%; when only one, show limited evidence. Each season's scoring strength = team PF/week divided by its own season's league PF/week, minus one. Each season's CV = population SD of its 14 weekly final PF divided by its average PF/week. Weight these continuous dimensions first, then apply the canonical four-quadrant thresholds; do not average categorical DNA labels. Show actual per-year classification and weights. Unweighted lifetime context displays mean league-adjusted scoring, average CV, and persistence of the most frequently observed season quadrant (or mixed if tied). Titles do not decay and are maintained in the separate championship reference. The 2023 team in ESPN slot 6 belongs to a different owner and cannot contribute to the current slot-6 franchise's history. The current slot-6 franchise returns from 2021–2022 after a 2023 absence; its latest three completed seasons are 2025, 2024, and 2022. Historical data is public scoring, not owner identities, credentials, roster comparisons or unverified postseason conclusions. Updating weekly snapshots preserves the independent historical JSON block through `scripts/sync_site_snapshot.py`.

## Roster-quality definitions

**For 2021–2022, lineup-quality metrics are deliberately unavailable.** Those ESPN seasons had one starting punter and seven bench slots, requiring separately verified punter eligibility/scoring before an era-specific Starter-Worthy Rate could be calculated. The current SWR denominator stays at eight; old-season punter-inclusive PF is preserved for league-adjusted history.

**Actual Starter-Worthy Rate (SWR)** counts NFL-wide weekly position qualifiers in the actual finalized starting lineup. Qualifying cutoffs: QB 10, RB 20, WR 20, TE 10, top ten additional FLEX-eligible RB/WR/TE after positional qualifiers, kicker 10 and DST 10; ties count. Seven skill slots count one point each; K/DST count half each; eight weighted points maximum.

**Roster ceiling** is the best *legal* qualifying lineup available from the actual starters and actual bench, excluding IR. **Ceiling captured** is actual weighted quality divided by roster ceiling, or N/A when that ceiling is zero. **Unavoidable shortfall** = (eight minus best available) / eight. Unrealized quality is split into rearranging current starters versus adding real bench players. These are final-score hindsight comparisons, not evidence that a bench player was a predictable pregame start.

## Data and approval workflow

1. The existing authenticated, read-only ESPN fetch uses `ESPN_S2` and `ESPN_SWID` GitHub Actions secrets. Never paste credentials in a commit, issue, chat, artifact or log.
2. A completed week enters `data/league.json` only after score and matchup reconciliation. Roster retrieval separately reconciles all ten finalized historical lineups per week against approved scores.
3. Inspect generated preview artifacts and run the tests before publishing. Only approve paired `index.html` **and** `data/league.json` in the same PR/commit. The embedded fallback and external JSON must agree.
4. Existing public roster metrics remain unavailable for any later week until its finalized rosters are separately validated.
5. Historical ESPN screenshot projections may be in-game values. Projection comparisons are hidden until **at least three explicitly verified pregame weekly captures** are available; an unverified snapshot never contributes.

## Tests

```bash
python scripts/test_pipeline.py
python scripts/test_roster_analysis.py
python scripts/test_historical_dna.py
python scripts/test_franchise_identity.py
node scripts/test_dashboard.cjs
```

The `validate-dashboard` GitHub Actions job runs without ESPN secrets and checks the approved snapshot, metric-definition consistency, current UI copy and calculations. A failed validation does not publish.

## Scope

The site has no team owner/manager identities, CSV export, automatic public publishing, or live opponent/projection substitutions. Public finalized fantasy player names and lineup results are included only after review. The scheduled builder and existing roster preview are read-only; publishing is a separate approval action.
