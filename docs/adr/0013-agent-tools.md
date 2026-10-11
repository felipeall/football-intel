# 13. Agent tool surface: typed tools plus guarded SQL fallback

Status: Accepted — 2026-10-11

## Decision
Typed tools: `search_players(filters)`, `similar_players`, `player_profile`, `compare`, `market_value_history`, `render_chart`.
Fallback: read-only SQL against the marts schema only, with row and timeout limits.
Every fallback use is logged; frequent patterns become new typed tools.
