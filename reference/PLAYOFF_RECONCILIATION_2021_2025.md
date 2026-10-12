# ESPN postseason history — 2021–2025 (validated research)

The read-only discovery and fail-closed playoff bracket validation were executed in [Actions run 38292261261](https://github.com/jawilloughbyii/fantasy-2k-infinitiy/actions/runs/38292261261), using ESPN authentication held only in GitHub Actions secrets.

**This research is not yet published to the dashboard.** A sanitized 5-year bracket JSON and championship candidate JSON are available inside that run's private `postseason-research-private` artifact. No owner names, manager IDs or cookies are exported.

## League playoff structure recovered from ESPN

- 10 teams per season; 14 regular-season weeks; 6 teams actually entered ESPN's `WINNERS_BRACKET` each season.
- Single-week playoff periods 15, 16, 17; top two ESPN playoff seeds received Week 15 byes in all five seasons.
- Round 1 contains 2 played games + 2 byes; Week 16 contains 2 semifinals; Week 17 contains 1 championship game.
- ESPN explicitly labeled the championship matches `WINNERS_BRACKET`, provided scores and winning side, and all final participants match Week 16 advancing winners.
- Third-place and consolation/placement matches were recorded separately. Do not credit their winners as league champions.

## Verified championship results

| Year | Champion (historical team name) | Champion stable franchise | Runner-up | Championship score (champion–runner-up) | ESPN championship matchup |
| --- | --- | --- | --- | --- | --- |
| 2021 | Lord Farquaad | `franchise-07` | Watertown Teapots | 146.36–136.60 | Week 17, ID 82 |
| 2022 | Quatro Padres | `franchise-03` | TimmyT's Golden Ponies | 123.43–109.77 | Week 17, ID 82 |
| 2023 | The Load Warriors | `franchise-07` | Team Lasky | 111.26–110.22 | Week 17, ID 82 |
| 2024 | Mike Oxlong | `franchise-10` | Jan. 6 Freedom Fighters | 147.28–145.92 | Week 17, ID 82 |
| 2025 | General's Dorm Room | `franchise-01` | James and the Giant Jazz | 134.38–91.96 | Week 17, ID 82 |

2023–2025 championship winners independently reconcile with `reference/championship_history.json`. The 2021 and 2022 titles are newly verified by ESPN's championship bracket, not by regular-season points-for standings.

## Important 2025 qualification discrepancy

In 2025 ESPN's `playoffSeed` field lists **Quattro Padres** as seed 5 and **Comepig** as seed 7, yet actual `WINNERS_BRACKET` schedule shows **Comepig competing in the playoffs** and Quattro Padres placed in the consolation ladder. Thus numeric `playoffSeed <= 6` **is not a reliable test of actual playoff qualification for that year**. Use participation in the ESPN `WINNERS_BRACKET` to identify qualifiers.

This does not affect the observed champion or final score. The cause of the seed/placement difference (e.g. commissioner settings, divisions or another circumstance) has not been verified. Do not model playoff-qualification scenarios or claim an official seed selection rule until clarified.

## Publishing gates

1. A separate PR should import the sanitized candidate brackets and append the **new 2021 and 2022 titles** to `reference/championship_history.json`, not infer additional trophies.
2. Synchronize the embedded fallback in `index.html` and expand the History → Championships view to support bracket results, maintaining the yearbook's historical team names and the current franchise display names.
3. Update regression tests for years, stable identity, finals/scores and 2025 qualification discrepancy. Preserve 2026 current-season data and lineup-quality denominator.
4. No early playoff-prediction or qualification simulation rules should be introduced without confirming league manager selections and tie-breaking policies.

## Implementation/reproduction

- `scripts/discover_playoff_history.py` fetches the five year-specific ESPN leagues privately.
- `scripts/validate_playoff_history.py` checks winners, score direction, round progression, first-round byes, known 2023–2025 titles and explicit franchise keys.
- `.github/workflows/discover-playoff-history.yml` performs read-only discovery and verification, storing the private artifact for seven days.

There are no API secrets or personal owner identities in public data or committed source.
