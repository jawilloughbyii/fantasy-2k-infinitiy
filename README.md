# Fantasy 2K Infinity

A read-only, mobile-friendly fantasy football league report for the 2026 season. The public site displays anonymous team names, approved final matchup scores and verified finalized roster summaries. ESPN credentials remain GitHub Actions secrets and are never part of published JSON.

## Dashboard sections

- **Overview:** scoring-ranked standings with actual record, PF, all-play record, extra wins and (once eligible) trend; week-scoped talking points; selected-team legal lineup opportunities.
- **Team DNA & scoring:** one consistent four-quadrant Scoring Personality Map plus finalized weekly Starter-Worthy Rate and legal roster ceiling. A recent four-week DNA comparison appears starting at **seven** completed weeks. Scoring trend appears after **four** weeks (latest two versus preceding two), switching at Week 6 to latest three versus preceding three.
- **Who got lucky?:** **extra wins** is the only season schedule-luck headline: actual wins minus expected wins against all nine teams every completed week. Half credit for ties.
- **What if?:** historical schedule reshuffles and division finish distributions, as context rather than a second luck score.
- **How it works:** plain-language definitions and methodological limits.

League context in the Overview compares every team against all ten approved teams: arithmetic league averages and tied competition ranks (rank 1 is highest). Roster ceiling and realized-quality benchmarks exclude unvalidated weeks. All-play win/loss totals display whole numbers unless a true tied matchup creates a half-win. The mobile standings use full-width team cards rather than a horizontally clipped table.

Definitions shared by the Python builder and the browser live in [reference/metric_definitions.json](reference/metric_definitions.json). `scripts/sync_site_snapshot.py` embeds both approved data and those definitions in the HTML fallback. Change definitions there rather than creating independent UI categories.

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
