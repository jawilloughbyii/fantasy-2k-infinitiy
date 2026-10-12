# Historical franchise continuity (stable manager identity)

Source of truth: [franchise_continuity.json](franchise_continuity.json).

## Identity policy (confirmed October 12, 2026)

The permanent franchise key follows the **manager/participant**, not the changing team name or ESPN roster slot. Public dashboard cards display the **current fantasy team name**, with original historical team names in annual yearbooks; private person names are not embedded in public data.

Composite historical input key is **(season, ESPN league ID, ESPN team ID)**. Seasons 2021–2022 belong to ESPN league `1493036707`. Seasons 2023–2026 belong to league `418244680`. The explicit map joins those season slots to an anonymous, stable franchise ID; matching the numeric slot across different ESPN leagues is forbidden.

### Participation changes

| Year | Participant change | Historical assignment |
| --- | --- | --- |
| 2021–2022 | Original 10 people | Archived team slots 1–10 mapped to the same 10 stable franchise identities |
| 2023 | New entrant joins; returning franchise absent | Comepig is new entrant franchise (ID 5); Team Figueroa remains legacy franchise (ID 6) |
| 2024 | Original participant returns; prior slot occupant departs | Returnee controls Alan's Cordon Bleu Cavern (ID 6); new entrant retains Comepig (ID 5) |
| 2025–2026 | No further changes confirmed | Returning franchise: Alan's Cordon Bleu Cavern → Got Rice?; new entrant: Comepig |

The returning franchise's 2021–2022 results join to its 2024–2026 record, **with a missing 2023** (never carry another franchise's results into the gap). The departed franchise's 2021–2022 results join to Team Figueroa in 2023 and stop there. The new entrant franchise starts in 2023 and remains separate.

### Dashboard semantics

- **Owner-based** Historical Team DNA, Franchise Legacy, all-time records, and championship credit.
- Current teams shown by their current 2026 fantasy display names; in historical yearbooks use the team name used in that season.
- Keep 2026 current scoring separate from completed historical years.
- Historical DNA uses the **most recent three completed seasons in which the manager participated**, weighted 50/30/20. Gaps remain visible; they are not counted as zero or silently assigned.
- Archived 2021–2022 championship metadata stays unavailable until separately verified. No new trophy markers are inferred from team names.
- Only verified scoring data should enter the public historical JSON; the source snapshots are read-only authenticated ESPN data, and private owner credentials are never included.

## Source files

- `reference/franchise_continuity.json`: anonymous ID mapping, source league per year, and confirmed transitions
- `reference/team_id_map.json`: mapping from **2026 dashboard ID** to 2026 ESPN team ID (different numbering)
- `reference/historical_regular_season_scores.json`: approved published historical final regular-season scoring (currently 2023–2025 until old-season scores are explicitly published)
- `scripts/franchise_identity.py`: strict identity validation/resolution
- `scripts/test_franchise_identity.py`: continuity regression tests
- `scripts/validate_archived_2021_2022.py` (separate PR #26): validated archived scoring preview; output remains private until approved

Do not publish person names, raw authenticated API responses, owner/manager identifiers, or ESPN cookies.
