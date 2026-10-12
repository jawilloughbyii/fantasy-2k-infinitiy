# Archived 2021–2022 validation and franchise reconciliation

## Scoring status

Private read-only GitHub Actions run [38281776553](https://github.com/jawilloughbyii/fantasy-2k-infinitiy/actions/runs/38281776553) completed successfully against ESPN league `1493036707`. `scripts/validate_archived_2021_2022.py` checks the score grain, 14 regular-season weeks, 5 unique matchups per week, two final scores per matchup, nonnegative cent-precision points, and that ESPN winner fields match the scores.

| Season | Teams | Regular-season games | Team-week scores | Total PF | PF per team-week | Excluded postseason / placement entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021 | 10 | 70 | 140 | 19,773.13 | 141.24 | 16 |
| 2022 | 10 | 70 | 140 | 19,061.08 | 136.15 | 16 |

**Status:** Regular-season scores are internally reconciled to ESPN's archived schedule, but an independent ESPN season-total comparison is not included in the sanitized discovery extract. The excluded entries must not be used for championship or playoff claims without further validation.

The private Actions artifact contains a derived `validated-historical/historical_regular_season_2021_2022.json` with season-level scoring only; no raw ESPN response or owner identifiers. It is **not** an approved public reference file.

## Identity status: unresolved across league IDs

The 2021/2022 ESPN league ID is **1493036707**. The existing 2023–2026 ESPN league ID is **418244680**. A slot ID is not a portable person/franchise key, even where the display name is unchanged.

| Old ESPN slot | 2021 alias | 2022 alias |
| --- | --- | --- |
| 1 | Fully Staffed Young Hoes | Let's Go Brandin |
| 2 | Tier 1 Sanchez | Tier 1 Sanchez |
| 3 | Lord Farquaad | Puss in Boots |
| 4 | General's Moose Knuckle | Najee By Nature |
| 5 | Quatro Padres | Quatro Padres |
| 6 | TimmyT's Golden Ponies | TimmyT's Golden Ponies |
| 7 | Elon Musk's Union Aversion | Alan's Milking Table |
| 8 | Skeeter's Yeeters | Skeeter's Yeeters |
| 9 | Tyreek in the Sheets | Tyreek in the Sheets |
| 10 | Watertown Teapots | Watertown Teapots |

Names and same-ID slot carryover can be used as **candidates for review**, not proof of continuity. There is suggestive overlap with the 2023 name `Golden Ponies Reigning Champs` (2023 ID 4), but it does not prove a franchise join or a 2022 title. No ownership fields were exported or committed.

### Approval gate

1. Confirm 2021-to-2022 franchise continuity for each archived slot, especially slots with different team names.
2. Explicitly map 2022 franchises to 2023 franchise IDs or mark them as historical-only; **never join on slot ID across the two ESPN league IDs**.
3. Honor the verified 2023 slot-6 franchise break between 2023 and 2024.
4. Separately verify playoff results before adding any 2021/2022 championship markers.
5. Only then add sanitized historical scores to the public history reference and dashboard in a separate PR.

No dashboard publication is included in this PR.
