# Skill: GitNexus Codebase Indexing

⚠️ **Status**: `hermes gitnexus` subcommand is NOT available in the current Hermes version.
Do NOT attempt to run `hermes gitnexus index` — it will fail with "binary not found."

## What to Do Instead

For codebase exploration, use the terminal directly:

```bash
# List project structure
find $VIKO_PROJECTS_ROOT/<slug>/ -type f -name "*.ts" -o -name "*.py" -o -name "*.go" | head -50

# Count files by type
find $VIKO_PROJECTS_ROOT/<slug>/ -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -20

# Search for a symbol or function
grep -r "functionName" $VIKO_PROJECTS_ROOT/<slug>/src/ --include="*.ts" -l

# Recent changes
git -C $VIKO_PROJECTS_ROOT/<slug>/ log --oneline -20
```

## When GitNexus Becomes Available

If a future Hermes version adds `hermes gitnexus`, the commands will be:

```bash
export PATH="/opt/hermes/bin:$PATH"
hermes gitnexus index $VIKO_PROJECTS_ROOT/<slug>/
hermes gitnexus status
hermes gitnexus list
```

## Important Notes

- **Do NOT run gitnexus cron jobs** — the command doesn't exist yet
- If asked to "index the codebase," use grep/find instead and report what was found
- If asked to "run gitnexus," respond: "GitNexus belum tersedia di versi Hermes saat ini. Saya bisa lakukan eksplorasi codebase manual dengan grep/find — mau?"
