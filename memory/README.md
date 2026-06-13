# Memory Architecture

Viko's persistent memory is stored in a vector database (ChromaDB) running as a Docker
service with a named volume. This directory contains only documentation — actual memory
data lives in the Docker volume `viko_memory`.

## Memory Units

### 1. Project Summary
- **What**: High-level state and recent decisions for a project
- **Granularity**: One active summary per project, updated over time
- **Example**: "forecast-inn last deployed to staging on 2026-06-10, pending production approval"

### 2. Decision
- **What**: A specific decision made during a task (approach chosen, trade-off accepted)
- **Granularity**: One entry per significant decision
- **Example**: "Chose Baileys over whatsapp-web.js for WA bridge — multi-device support needed"

### 3. Error
- **What**: An error encountered and how it was resolved
- **Granularity**: One entry per unique error pattern
- **Example**: "Bun WebSocket incompatibility with Baileys — resolved by switching to Node.js"

## TTL (Time to Live)

- Default: **30 days** from creation or last access
- Renewed automatically when the memory is accessed or referenced
- Expired memories are soft-deleted — recoverable within 7 days before permanent removal

## Curation Process

Viko never stores memory without Eksa's approval:

1. Viko proposes: "Layak diingat? [one-line summary]"
2. Eksa replies: approve / skip
3. On approval: Viko stores the entry in ChromaDB
4. On skip: Viko discards — no storage

## Storage

- Data: Docker volume `viko_memory` (persists across container restarts)
- Engine: ChromaDB (runs as part of the Docker Compose stack in `config/`)
- This git repo: never contains memory data — only this documentation
