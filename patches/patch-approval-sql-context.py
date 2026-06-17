#!/usr/bin/env python3
"""Patch: SQL danger patterns only fire when SQL is actually executed.

``DANGEROUS_PATTERNS`` flags SQL keywords (TRUNCATE / DROP / DELETE) wherever they
appear in a command string — including as plain *text* inside a Python heredoc that
draws a PDF or report (e.g. a pymupdf comparison table whose content mentions
"TRUNCATE TABLE"). That false-positives benign document-generation scripts, spams the
approval gate, and trains the agent to reformulate around it — eroding the gate for
the patterns that aren't HARDLINE.

Fix: when a SQL-family pattern matches, additionally require a real SQL *execution*
context near it — a database client invocation (psql/mysql/sqlite3/mongosh/…) or a
driver/ORM execute call (.execute(/cursor/sqlalchemy/…). A keyword with no such
context is text, not an execution, and is not flagged. HARDLINE patterns and every
non-SQL danger pattern are untouched, and approvals.mode=manual still gates every
genuine dangerous SQL command. Conservative by design: if any execution indicator is
present it still flags (no weakening of real detection).

Idempotent. Applied at image build (Dockerfile.hermes) and re-runnable live.
"""
import sys
import pathlib

TARGET = pathlib.Path("/opt/hermes/tools/approval.py")
MARKER = "_sql_exec_context_present"

HELPER = r'''
# --- viko patch: SQL danger keywords require a real execution context ---------
# A SQL keyword (TRUNCATE/DROP/DELETE) is only dangerous when run against a database.
# When it appears merely as text in a script (e.g. a pymupdf/docx report that prints
# the word "TRUNCATE"), there is no DB client or driver call — it must not trip the
# approval gate. This regex detects a genuine execution context.
_SQL_EXEC_CONTEXT_RE = re.compile(
    r"\b(psql|mysql|mariadb|sqlite3?|mongosh|mongo|clickhouse-client|clickhouse|"
    r"sqlcmd|usql|pgcli|mycli|litecli|duckdb|cockroach|sequelize|knex|sqlalchemy|"
    r"psycopg2?|pymysql|asyncpg|aiomysql|mysqldb|pg8000)\b"
    r"|\.execute(?:script|many|_driver_sql)?\s*\("
    r"|\.exec(?:_driver_sql)?\s*\("
    r"|\bcursor\b"
    r"|\b(?:conn|connection|engine|session|db|tx|trx)\.(?:execute|exec|begin|query|raw|cursor)\b"
    r"|\.query\s*\(",
    re.IGNORECASE,
)


def _sql_exec_context_present(command_lower):
    """True when the command actually executes SQL (vs mentioning a keyword as text)."""
    return bool(_SQL_EXEC_CONTEXT_RE.search(command_lower))
# --- end viko patch -----------------------------------------------------------

'''

OLD_LOOP = """        if pattern_re.search(command_lower):
            pattern_key = description
            return (True, pattern_key, description)"""

NEW_LOOP = """        if pattern_re.search(command_lower):
            # viko patch: a SQL keyword present only as text (no DB client/driver) is
            # not an execution and must not trip the approval gate.
            if description.startswith("SQL ") and not _sql_exec_context_present(command_lower):
                continue
            pattern_key = description
            return (True, pattern_key, description)"""

ANCHOR = "def detect_dangerous_command(command: str) -> tuple:"


def main():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found", file=sys.stderr)
        return 1
    src = TARGET.read_text()
    if MARKER in src:
        print("approval.py already patched (SQL exec-context); skipping")
        return 0
    if ANCHOR not in src:
        print("ERROR: detect_dangerous_command def not found — aborting", file=sys.stderr)
        return 1
    if OLD_LOOP not in src:
        print("ERROR: detect_dangerous_command loop body not found — aborting", file=sys.stderr)
        return 1
    src = src.replace(ANCHOR, HELPER.lstrip("\n") + ANCHOR, 1)
    src = src.replace(OLD_LOOP, NEW_LOOP, 1)
    TARGET.write_text(src)
    print("approval.py patched: SQL patterns now require an execution context")
    return 0


if __name__ == "__main__":
    sys.exit(main())
