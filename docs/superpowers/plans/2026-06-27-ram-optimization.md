# RAM Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Hermes container memory footprint via Python malloc tuning and Docker memory limits, without degrading agent capability.

**Architecture:** Two levers — (1) `MALLOC_ARENA_MAX=2` env var eliminates Python glibc malloc arena fragmentation (20–40% RAM reduction per container, zero functional impact); (2) explicit `--memory` limits in docker-compose and spawn-hermes.py give Docker a hard ceiling per container so a runaway session can't consume all available RAM. Applied to both the admin container (docker-compose.yml) and all dynamically-spawned project containers (scripts/spawn-hermes.py).

**Tech Stack:** Docker Compose v2, Python (Hermes), shell env vars, Markdown docs

## Global Constraints

- Do NOT change any Hermes behavior, model config, skill, or rule files
- Do NOT reduce `max_concurrent_sessions` or any capability-facing config
- `MALLOC_ARENA_MAX=2` must be set as an env var (not code change) — Hermes is a third-party image
- Memory limits must allow headroom for active agent sessions: admin 1.5 GB, project 900 MB
- All changes go through git commit + push; no direct VPS edits without a corresponding repo change
- Current branch: `fix/soul-block-and-deploy-network` → create new branch `fix/ram-optimization`

---

> **Revision note:** Project container limit was revised from 900m → 1500m during implementation
> (siprodev was observed at 1.576 GB in production). --memory-swap was also dropped as too aggressive.
> All committed code uses 1500m. The task steps below reflect the original draft values.

### Task 1: Add MALLOC_ARENA_MAX + memory limit to admin container (docker-compose.yml)

**Files:**
- Modify: `docker-compose.yml`

**Interfaces:**
- Produces: `hermes` service with `MALLOC_ARENA_MAX=2` env var and `mem_limit: 1536m`

- [ ] **Step 1: Create and switch to new branch**

```bash
git checkout main && git pull origin main
git checkout -b fix/ram-optimization
```

- [ ] **Step 2: Add MALLOC_ARENA_MAX to hermes environment block**

In `docker-compose.yml`, find the `environment:` block of the `hermes` service (around line 100). Add after the last existing env var (before `command:`):

```yaml
      # Python glibc malloc arena tuning — reduces memory fragmentation by
      # capping arena count. 20–40% RAM reduction with zero functional impact.
      MALLOC_ARENA_MAX: "2"
```

- [ ] **Step 3: Add memory limit to hermes service**

In `docker-compose.yml`, add after the `restart: unless-stopped` line of the `hermes` service:

```yaml
    mem_limit: 1536m
```

- [ ] **Step 4: Add MALLOC_ARENA_MAX to 9router service**

In `docker-compose.yml`, find the `environment:` block of the `9router` service. Add:

```yaml
      MALLOC_ARENA_MAX: "2"
```

And add memory limit after `restart: unless-stopped`:

```yaml
    mem_limit: 512m
```

- [ ] **Step 5: Verify compose file is valid**

```bash
cd /Users/eksa/Projects/viko-nexus/viko-agent
docker compose config --quiet && echo "compose OK"
```

Expected: `compose OK` with no errors.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml
git commit -m "perf(hermes): add MALLOC_ARENA_MAX=2 + mem_limit to admin + 9router"
```

---

### Task 2: Add MALLOC_ARENA_MAX + memory limit to project containers (spawn-hermes.py)

**Files:**
- Modify: `scripts/spawn-hermes.py`

**Interfaces:**
- Consumes: `cmd` list built at line ~830 in `spawn-hermes.py`
- Produces: all dynamically-spawned `viko-hermes-{slug}` containers with `MALLOC_ARENA_MAX=2` and `--memory 900m`

- [ ] **Step 1: Add --memory flag to docker run command**

In `scripts/spawn-hermes.py`, find the `cmd = ["docker", "run", "-d", ...]` block (around line 830). After the `"--log-opt", "max-file=3",` lines, add:

```python
        # Cap per-project container memory. 900m gives ~200m headroom above the
        # ~680m observed baseline for active-session containers.
        "--memory", "900m",
        "--memory-swap", "900m",  # disable swap for this container
```

- [ ] **Step 2: Add MALLOC_ARENA_MAX env var to docker run**

In the same `cmd` list, after the SSL cert env vars (around line 892), add:

```python
        "-e", "MALLOC_ARENA_MAX=2",
```

- [ ] **Step 3: Verify spawn-hermes.py has no syntax errors**

```bash
python3 -m py_compile scripts/spawn-hermes.py && echo "syntax OK"
```

Expected: `syntax OK`

- [ ] **Step 4: Commit**

```bash
git add scripts/spawn-hermes.py
git commit -m "perf(spawn): add MALLOC_ARENA_MAX=2 + --memory 900m to project containers"
```

---

### Task 3: Update docs — DEPLOYMENT.md VPS requirements + memory guidance

**Files:**
- Modify: `docs/overview/DEPLOYMENT.md`

**Interfaces:**
- Produces: documented RAM requirements and per-container memory budget

- [ ] **Step 1: Add VPS requirements section**

In `docs/overview/DEPLOYMENT.md`, find the VPS prerequisites section (around line 5). Add or expand with:

```markdown
### VPS Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 4 GB | 8 GB |
| CPU | 2 vCPU | 4 vCPU |
| Disk | 40 GB | 100 GB |

**Memory budget per container (with MALLOC_ARENA_MAX=2 tuning):**
- `viko-hermes` (admin + bridge): ~770 MB baseline, limit 1.5 GB
- `viko-9router`: ~150 MB baseline, limit 512 MB
- `viko-hermes-{slug}` (per project): ~500–700 MB baseline, limit 900 MB
- Infra (postgres, redis, minio, traefik): ~280 MB combined

**Practical capacity:** 8 GB RAM comfortably supports ~7–8 simultaneous active project containers.
```

- [ ] **Step 2: Commit**

```bash
git add docs/overview/DEPLOYMENT.md
git commit -m "docs(deployment): add VPS RAM requirements and per-container memory budget"
```

---

### Task 4: Update docs — ARCHITECTURE.md resource constraints section

**Files:**
- Modify: `docs/overview/ARCHITECTURE.md`

**Interfaces:**
- Produces: architecture doc with memory isolation model documented

- [ ] **Step 1: Add resource isolation note**

In `docs/overview/ARCHITECTURE.md`, find the section describing per-project Hermes containers. Add a subsection:

```markdown
### Resource Limits

Each container has explicit Docker memory limits to prevent a single runaway agent session from starving the host:

| Container | `mem_limit` |
|-----------|-------------|
| `viko-hermes` (admin) | 1536 MB |
| `viko-9router` | 512 MB |
| `viko-hermes-{slug}` (project) | 900 MB |

Python's glibc malloc arena count is capped via `MALLOC_ARENA_MAX=2` in all Hermes containers, reducing baseline RAM usage by 20–40% vs the default (8 arenas per CPU core).
```

- [ ] **Step 2: Commit**

```bash
git add docs/overview/ARCHITECTURE.md
git commit -m "docs(architecture): document container memory limits and malloc tuning"
```

---

### Task 5: Update README.md — quick-start memory note

**Files:**
- Modify: `README.md`

**Interfaces:**
- Produces: README with VPS RAM callout visible to new setup users

- [ ] **Step 1: Add RAM callout to README**

In `README.md`, find the prerequisites or setup section. Add:

```markdown
> **VPS RAM:** 8 GB recommended. Each active project agent container uses ~500–700 MB. See [DEPLOYMENT.md](docs/overview/DEPLOYMENT.md) for full resource breakdown.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): add VPS RAM recommendation callout"
```

---

### Task 6: Push branch + apply to running containers on VPS

**Files:**
- No file changes — VPS operation only

- [ ] **Step 1: Push branch and open PR**

```bash
git push origin fix/ram-optimization
gh pr create --title "perf: RAM optimization — MALLOC_ARENA_MAX + memory limits" \
  --body "Adds MALLOC_ARENA_MAX=2 and Docker mem_limit to all Hermes containers.
  
  - Admin + 9router: via docker-compose.yml
  - Project containers: via spawn-hermes.py --memory flag
  - Docs: DEPLOYMENT.md VPS requirements, ARCHITECTURE.md resource limits, README callout
  
  Expected impact: 20–40% baseline RAM reduction per container with no capability loss." \
  --base main
```

- [ ] **Step 2: Merge PR then pull on VPS**

```bash
gh pr merge --squash --auto
# Wait for merge, then:
ssh doasas-deploy "cd /home/deploy/viko-agent && git pull origin main && echo 'pulled OK'"
```

- [ ] **Step 3: Recreate admin container to apply new env + limit**

```bash
ssh doasas "cd /home/deploy/viko-agent && docker compose --profile full up -d --force-recreate hermes 9router"
```

Expected: both containers restart with new `MALLOC_ARENA_MAX` and `mem_limit`.

- [ ] **Step 4: Verify memory reduction**

```bash
ssh doasas "sleep 30 && docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}'"
```

Expected: `viko-hermes` below 900 MB, `viko-9router` below 200 MB.

- [ ] **Step 5: Note on project containers**

Project containers (`viko-hermes-{slug}`) pick up the new settings on their next spawn (re-onboard or container restart). Existing running containers are unaffected until restarted. To apply immediately to a specific project:

```bash
ssh doasas "docker restart viko-hermes-siprodev"
# Note: this restarts the agent — any active session is lost
```

Do NOT mass-restart all project containers at once — coordinate with users first.
