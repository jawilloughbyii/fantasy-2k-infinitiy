# Retrospective Draft Value and Historical Draft DNA — model v1

## Verified source and scope
- **2021–2025 only:** 820 picks, all matched by original ESPN player ID to year-specific ESPN league-scored weekly actuals (regular-season Weeks 1–14). The comparison pool contains 5,677 original-season eligible player records, including undrafted players.
- **2026:** selection history is available, but no final grades or Historical DNA contribution until the season completes.
- The canonical owner-franchise key follows the manager through renamed teams, ESPN league migration and participation gaps; `(year, league ID, ESPN team ID)` is the required source grain.
- 2021–2022 retain their original punter-era points. The 20 punter picks are labeled `ERA_ONLY` and contribute nothing to cross-era Draft DNA.
- Historical team and player names are public fantasy data. No owner/manager names, authentication values or private ESPN payloads are published.

## Per-pick value
Replacement ranks within the original season's **full eligible player pool**: QB10, RB24, WR24, TE10, K10, D/ST10, P10.

For each position and completed season:

`normalized_value = max(0, (player_regular_season_PF - positional_replacement_PF) / (top_positional_PF - positional_replacement_PF))`

This yields a 0–1 production score that adjusts for the 2021–2022 scoring environment and position-specific scoring levels. A *zero normalized score* means below the model's replacement benchmark, **not necessarily zero fantasy points scored**.

`expected_value` uses **other four completed seasons**, taking draft picks at the same position, weighting peer performance by proximity of their draft-cost round (`exp(-absolute_round_distance/2.25)`). The evaluated season is held out of its own cost baseline; using future seasons for retrospective evaluation is intentional and is **not** a pre-draft forecast.

`value_added = normalized_value - expected_value`. Displayed percentage points are normalized-value differences, not raw fantasy points.

## Tags (locked model-v1 definitions)
| Tag | Condition |
| --- | --- |
| STEAL | After Round 2, value added at least +0.23 and normalized realized value at least 0.35 |
| BUST | Expected value at least 0.32 and value added at most -0.23 |
| HIT | Value added at least +0.075 with realized value at least 0.25, OR early-round elite hit |
| NEUTRAL | All remaining skill and special-teams draft selections |
| ERA_ONLY | 2021–2022 punter picks, excluded from cross-era grades |
| PENDING | 2026 picks; no completed-year actuals yet, so no final tag |

Elite hit is an additional flag on a Round 1/2 pick with normalized value at least 0.75 and value added at least +0.20; it is not treated as a late-round steal. Tags are deliberately stringent: they do not guarantee similar counts of steals/busts each year. The v1 output is 76 steals, 78 hits, 632 neutrals, 14 busts, and 20 era-only punters.

## Franchise-level Historical Draft DNA

For each year and permanent franchise, draft efficiency is `100 + 100 * weighted_mean(value_added)`. Premium picks have higher investment weight. K and D/ST count at half that weight; P excluded. The 100-point benchmark means expected return relative to observed comparable draft costs.

Skill-position Steal Rate and Bust Rate exclude K/DST/P. Early-round Hit Rate covers skill-position Rounds 1–4. Late-round Value Added covers skill-position rounds 8+.

Historical Draft DNA uses the **most recent three completed participated seasons per permanent franchise**, weights 50% / 30% / 20% normalized when fewer are available. For the returning 2024 franchise, that means 2025 / 2024 / 2022, **not** the unrelated 2023 occupant's draft. A classification requires at least three completed seasons; outcomes include Value Hunter, Early-Round Anchor, High-Variance Drafter, Balanced Builder, Draft Capital Underperformer, or Mixed Returns. Exact classification thresholds are implemented in `scripts/grade_draft_value.py` and persisted in `reference/historical_draft_grades.json`.

## What this does and does not measure

These are **retrospective draft investment outcomes** across the full season—even if the player was traded, dropped or never started by the original drafter. They are not causal claims about a manager's predictive ability, actual lineup benefit, roster utilization, injury severity, medical availability, or the player's value only while rostered.

A `limited_recorded_scoring_weeks` flag merely indicates seven or fewer weeks with an ESPN weekly actual stat; it does **not** assert an injury, because zero-valued stats and missing games need separate evidence. Labels are model classifications, not verified clinical/availability diagnoses.

## Reproducibility and checks

- Private authenticated, read-only collection: `scripts/backfill_draft_player_performance.py`.
- Deterministic grading: `scripts/grade_draft_value.py`.
- Source-backed and identity tests: `scripts/test_historical_draft_grades.py`.
- Approved public reference: `reference/historical_draft_grades.json`.
- Verified source run: [GitHub Actions 38297398265](https://github.com/jawilloughbyii/fantasy-2k-infinitiy/actions/runs/38297398265). Minimized original player-score evidence is a private seven-day artifact.
