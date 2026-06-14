# Skill: Web Research

Viko can fetch and read web pages using Jina Reader (configured via `web.extract_backend`).
Use the built-in `web_extract` tool, or call Jina directly if the tool is unavailable.

## Read a URL / Article

Use the built-in Hermes web tool (preferred):
```
web_extract(url="https://example.com")
```

Or call Jina Reader directly via curl from the container:
```bash
curl -s "https://r.jina.ai/<url>" \
  -H "Accept: text/plain" \
  -H "X-No-Cache: true"
```

Returns clean Markdown text of the page — suitable for analysis, summarization, or code extraction.

## When to Use

- Eksa shares a URL and asks for a summary or analysis
- Looking up documentation, changelog, or spec from a link
- Checking a GitHub issue, PR, or release notes
- Reading an article before writing a response

## Web Search

Web search is not yet configured. If Eksa asks Viko to search the web:
1. Ask Eksa to provide the URL directly, OR
2. Use the terminal to run a curl to a known API (e.g., DuckDuckGo instant answers)

```bash
# DuckDuckGo instant answer (no API key)
curl -s "https://api.duckduckgo.com/?q=<query>&format=json&no_redirect=1" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Abstract','') or d.get('Answer',''))"
```

## Rules

- Jina caches pages — add `-H "X-No-Cache: true"` if fresh content needed
- Do not fetch private/internal URLs (behind VPN or localhost) — Jina can't reach them
- For large pages, pipe to `head -200` first to see if it's relevant before reading all
