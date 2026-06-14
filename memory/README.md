# Memory Architecture

Viko uses **Holographic** for persistent memory — pure local, no external API required.

## Storage

- **Engine**: Holographic (SQLite-backed, HRR-based compositional retrieval)
- **Data file**: `data/hermes/memory_store.db` (gitignored, persists across restarts)
- **Configured via**: `memory.provider: holographic` in `data/hermes/config.yaml`

## Memory Types

| Type | What | Granularity |
|------|------|-------------|
| Entity | People, projects, servers | One entry per entity |
| Decision | Approach chosen, trade-off accepted | One per significant decision |
| Error | Error encountered and how it was resolved | One per unique error pattern |
| Context | Project state, recent activity | Updated per session |

## TTL

- Default: **30 days** from last access
- Renewed automatically when the memory is accessed
- Expired memories are soft-deleted before permanent removal

## Notes

- This repo never contains memory data — only this documentation
- Memory data lives in `data/hermes/memory_store.db` (bind-mounted, gitignored)
- No ChromaDB, no API key, no external service — runs entirely inside the container
