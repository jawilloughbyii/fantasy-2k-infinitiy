# Fantasy 2K Infinity

A read-only, mobile-friendly fantasy football league report for the 2026 season. The public site displays anonymous team names, approved final matchup scores and verified finalized roster summaries. ESPN credentials remain GitHub Actions secrets and are never part of published JSON.

## Dashboard sections

- **Overview:** compact PF-ranked desktop data table with actual record, PF, all-play, extra wins, recent PF/week form, DNA quadrant and scoring volatility (CV%). On mobile, all ten teams are visible as concise rows (rank, team, record, PF, extra wins); tap one row to expand its all-play, form, DNA and CV, then choose View Team to focus the existing lineup-quality drill-down. No standings sparkline grid.
- **Team Cards:** ten screenshot-first, one-team-at-a-time report cards sized for a mobile viewport. Minimalist fingerprint, four-leaf clover and target icons introduce DNA, extra wins and Starter-Worthy Rate. Six secondary KPIs include same-window league comparisons (the natural all-play midpoint; PF/week; recent relative form; ceiling captured; missed bench and unavoidable weighted quality per week), three verified weekly micro-trends and one data-derived insight. Buttons and existing team selector change cards. Cards show unavailable metrics as unavailable rather than fabricating values. No owner names or independent metrics pipeline.
- **Team DNA & scoring:** one consistent four-quadrant Scoring Personality Map plus finalized weekly Starter-Worthy Rate and legal roster ceiling. A recent four-week DNA comparison appears starting at **seven** completed weeks. Scoring trend appears after **four** weeks (latest two versus preceding two), switching at Week 6 to latest three versus preceding three.
- **Who got lucky?:** **extra wins** is the only season schedule-luck headline: actual wins minus expected wins against all nine teams every completed week. Half credit for ties.
- **What if?:** historical schedule reshuffles and division finish distributions, as context rather than a second luck score.
- **How it works:** plain-language definitions and methodological limits.

League context in the Overview compares every team against all ten approved teams: arithmetic league averages and tied competition ranks (rank 1 is highest). Roster ceiling and realized-quality benchmarks exclude unvalidated weeks. All-play win/loss totals display whole numbers unless a true tied matchup creates a half-win. The mobile standings use full-width team cards rather than a horizontally clipped table.

Definitions shared by the Python builder and the browser live in [reference/metric_definitions.json](reference/metric_definitions.json). `scripts/sync_site_snapshot.py` embeds both approved data and those definitions in the HTML fallback. Change definitions there rather than creating independent UI categories.

## Verified championship markers

Every displayed team name uses the same franchise-keyed championship marker, including Overview standings, matchup opponents, Team Cards, Team DNA (including map labels), Who got lucky?, What if?, and the team selector. The marker is one trophy per confirmed title-winning franchise (with year(s) in the accessible label and a count for multiple titles), not a judgment about current-year performance. Currently verified: 2023 The Load Warriors (now Project Haily Mary), 2024 Mike Oxlong (now The Domestic House Cats), and 2025 General's Dorm Room. Quattro Padres has no verified title in the available records and gets no marker. Historical aliases resolve using the explicit season + ESPN ID map in `reference/franchise_continuity.json`, not by name. The published 2026 `data/league.json` model is unchanged; the HTML's public owner-free metadata is synchronized from `reference/championship_history.json`, `reference/franchise_continuity.json`, and `reference/team_id_map.json` by `scripts/sync_site_snapshot.py`. No History tab has been added yet.

## Historical Franchise Fingerprint (Team DNA)

The Team DNA & Scoring tab shows a separate completed-season **Franchise Fingerprint** beneath the current Scoring Personality Map. The current 2026 season stays separate and provisional; it never enters the historical baseline until completed and verified. Source: `reference/historical_regular_season_scores.json`, a sanitized 420-team-week extract of final 2023–2025 ESPN regular-season scores from private discovery run 38146729094. Fourteen weeks per season; playoffs are excluded. `scripts/test_historical_dna.py` reconciles 2023/24/25 league totals, every team/week, franchise identities and calculations.

The rolling fingerprint uses the latest three completed seasons of the **same permanent franchise**, weights 50% most recent / 30% prior / 20% third. When only two are known, renormalize to 62.5% / 37.5%; when only one, show limited evidence. Each season's scoring strength = team PF/week divided by its own season's league PF/week, minus one. Each season's CV = population SD of its 14 weekly final PF divided by its average PF/week. Weight these continuous dimensions first, then apply the canonical four-quadrant thresholds; do not average categorical DNA labels. Show actual per-year classification and weights. Unweighted lifetime context displays mean league-adjusted scoring, average CV, and persistence of the most frequently observed season quadrant (or mixed if tied). Titles do not decay and are maintained in the separate championship reference. The 2023 team in ESPN slot 6 belongs to a legacy franchise and cannot contribute to the current slot-6 franchise's history. Historical data is public scoring, not owner identities, credentials, roster comparisons or unverified postseason conclusions. Updating weekly snapshots preserves the independent historical JSON block through `scripts/sync_site_snapshot.py`.

## Roster-quality definitions

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
node scripts/test_dashboard.cjs
```

The `validate-dashboard` GitHub Actions job runs without ESPN secrets and checks the approved snapshot, metric-definition consistency, current UI copy and calculations. A failed validation does not publish.

## Scope

The site has no team owner/manager identities, CSV export, automatic public publishing, or live opponent/projection substitutions. Public finalized fantasy player names and lineup results are included only after review. The scheduled builder and existing roster preview are read-only; publishing is a separate approval action.
