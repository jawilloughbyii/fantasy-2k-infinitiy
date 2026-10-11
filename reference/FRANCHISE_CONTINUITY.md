# Historical franchise continuity (research only)

Source of truth: [franchise_continuity.json](franchise_continuity.json). This is a separate, opt-in reference for **league 418244680**. It is not connected to the live 2026 dashboard, its embedded fallback, the published league JSON, or the ingestion/data model.

## Confirmed identity rule

A franchise is a continuous historical participant, not a display name and not necessarily an ESPN team slot. Resolve with the **(season, ESPN team ID)** pair, then map to `franchise_id`. Do not join to the dashboard's different internal team IDs without using [team_id_map.json](team_id_map.json). The user confirmed continuity for ESPN IDs 1–10 across 2023–2026, **with one exception**:

| ESPN slot | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|
| 6 | `franchise-06-legacy-2023` (Team Figueroa) | `franchise-06-current-2024` | `franchise-06-current-2024` | `franchise-06-current-2024` |

The change of ownership/franchise occurred **after 2023, before 2024**, confirmed by the user October 11, 2026. All other nine ESPN slots retain their franchise key across those four years. There are **11** franchises represented across the four seasons, but always 10 teams within each season. No owner identifiers are recorded.

## Analysis safeguards

- Keep Team Figueroa's 2023 games, PF, record, luck, and scoring profile in **2023 league-wide analysis**; do not add them to the current slot 6 franchise's lifetime totals.
- Include 2023 legacy and 2024+ current as **separate franchise IDs** in longitudinal analysis.
- Team display names can change freely and are not primary keys.
- Do not claim verified continuity for 2022 or earlier or 2027 onward. Extend the explicit season map only when verified.
- Keep regular season and postseason distinctions independent of this identity mapping.
- ESPN ID 6 is an ESPN identifier. In the approved **2026 dashboard**, its corresponding internal baseline ID is **10**; the internal ID 6 maps instead to ESPN ID 10.
- The prior historical ESPN discovery artifacts are exploratory research, not yet approved for publication.

To resolve an identity in future historical research:

```python
from franchise_identity import load_mapping, franchise_for
mapping = load_mapping()
franchise_id = franchise_for(2023, 6, mapping)
```

For regression checks: `python scripts/test_franchise_identity.py`. The dedicated GitHub workflow executes these checks when the continuity reference or resolver changes.
