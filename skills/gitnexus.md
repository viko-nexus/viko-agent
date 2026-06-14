# Skill: GitNexus Codebase Indexing

## When to Use

Use GitNexus when Eksa asks to:
- Index or re-index a project codebase
- Build or refresh the knowledge graph for a project
- Run daily/scheduled codebase indexing (from cron)

## How GitNexus Works

GitNexus builds a symbol-level knowledge graph from source code.
It clones/pulls the repo, parses all files, and stores a graph in `/opt/data/gitnexus/`.
This lets Hermes answer deep questions about code structure without reading every file.

## Running GitNexus

```bash
export PATH="/opt/hermes/bin:$PATH"

# Index a single project (by GitHub URL or local path)
hermes gitnexus index <repo_url_or_local_path>

# Check index status
hermes gitnexus status

# List indexed repos
hermes gitnexus list
```

## Indexing All Projects (Cron / General)

```bash
export PATH="/opt/hermes/bin:$PATH"

# Step 1: discover available projects
ls $VIKO_PROJECTS_ROOT/viko-agent/projects/

# Step 2: for each project with a local code folder, run index
# Local path: $VIKO_PROJECTS_ROOT/<slug>/
# Example: $VIKO_PROJECTS_ROOT/mankop/

hermes gitnexus index $VIKO_PROJECTS_ROOT/mankop/
hermes gitnexus index $VIKO_PROJECTS_ROOT/forecastinn/
hermes gitnexus index $VIKO_PROJECTS_ROOT/luxso/
hermes gitnexus index $VIKO_PROJECTS_ROOT/forecastcrm/
```

## Important Notes

- **Terminal timeout is 600s** — git clone + npm install can take several minutes
- **Do NOT serve the web UI** during cron runs — indexing only
- **Report to WA** after each project: name, symbols indexed, time taken, or error
- If a project folder doesn't exist, skip it and note it in the report — do not stop

## Error Handling

| Error | Action |
|-------|--------|
| Folder not found | Skip project, note in summary |
| Timeout during clone | Retry once; if fails again, skip |
| Index already up to date | Note "no changes" and move on |

## Expected Output (WA Report)

```
GitNexus indexing selesai:
- mankop: 1.240 symbols, 42s
- forecastinn: 890 symbols, 31s
- luxso: folder tidak ditemukan, skip
- forecastcrm: no changes
```
