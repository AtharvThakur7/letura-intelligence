"""Validation for model-proposed SQL (defence in depth).

Layer 1 (this module): reject anything that is not a single, plain SELECT over
approved objects. Layer 2: the dedicated MySQL account only has SELECT on
approved objects. Layer 3: sessions are READ ONLY with MAX_EXECUTION_TIME.
Layer 4: row limit is forced.
"""
from __future__ import annotations

import re

from letura.db import APPROVED_OBJECTS

# Tables the free-form SQL tool may touch (aggregated/analytics + the safe listing view).
SQL_ALLOWED_TABLES = tuple(o for o in APPROVED_OBJECTS if o not in {"int_hamburg_listings", "meta_pipeline_runs"})
MAX_ROWS = 200
MAX_LENGTH = 2000

FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "create", "truncate", "replace", "grant", "revoke", "rename",
    "call", "execute", "prepare", "deallocate", "set", "load", "outfile", "dumpfile", "handler", "lock", "unlock",
    "kill", "shutdown", "install", "uninstall", "into", "sleep", "benchmark", "get_lock", "release_lock",
    "load_file", "for", "optimize", "analyze", "repair", "flush", "reset", "purge", "use", "show", "describe",
    "explain", "do", "with",
}
FORBIDDEN_SCHEMAS = ("information_schema", "mysql", "performance_schema", "sys")


class UnsafeSQL(ValueError):
    """Raised when a statement is rejected. The message is safe to show the user."""


def _strip_strings(sql: str) -> str:
    return re.sub(r"'(?:[^'\\]|\\.|'')*'|\"(?:[^\"\\]|\\.)*\"", "''", sql)


def validate_select(sql: str, allowed: tuple[str, ...] = SQL_ALLOWED_TABLES, max_rows: int = MAX_ROWS) -> str:
    """Return a safe, LIMIT-capped version of ``sql`` or raise UnsafeSQL."""
    if not isinstance(sql, str) or not sql.strip():
        raise UnsafeSQL("Empty SQL statement.")
    if len(sql) > MAX_LENGTH:
        raise UnsafeSQL("SQL statement too long.")
    s = sql.strip()
    if re.search(r"(--|#|/\*|\*/)", _strip_strings(s)):
        raise UnsafeSQL("SQL comments are not allowed.")
    body = s.rstrip(";").strip()
    stripped = _strip_strings(body)
    if ";" in stripped:
        raise UnsafeSQL("Only a single statement is allowed.")
    if not re.match(r"(?is)^\s*select\b", stripped):
        raise UnsafeSQL("Only SELECT statements are allowed.")
    if "`" in stripped or "@" in stripped:
        raise UnsafeSQL("Quoted identifiers and session variables are not allowed.")
    words = set(re.findall(r"[a-z_]+", stripped.lower()))
    bad = words & FORBIDDEN_KEYWORDS
    if bad:
        raise UnsafeSQL(f"Forbidden keyword(s): {', '.join(sorted(bad))}.")
    low = stripped.lower()
    if any(sch in low for sch in FORBIDDEN_SCHEMAS):
        raise UnsafeSQL("System schemas are not accessible.")
    refs = re.findall(r"(?is)\b(?:from|join)\s+([a-z0-9_\.]+)", stripped)
    if not refs:
        raise UnsafeSQL("Query must read from an approved table or view.")
    for r in refs:
        if "." in r:
            raise UnsafeSQL("Schema-qualified table names are not allowed.")
        if r.lower() not in allowed:
            raise UnsafeSQL(f"Table '{r}' is not approved. Allowed: {', '.join(allowed)}.")
    if re.search(r"(?i)\bunion\b", stripped):
        raise UnsafeSQL("UNION is not allowed.")
    m = re.search(r"(?i)\blimit\s+(\d+)\s*$", stripped)
    if m:
        if int(m.group(1)) > max_rows:
            body = re.sub(r"(?i)\blimit\s+\d+\s*$", f"LIMIT {max_rows}", body)
    elif re.search(r"(?i)\blimit\b", stripped):
        raise UnsafeSQL("LIMIT must be a plain trailing number.")
    else:
        body = f"{body} LIMIT {max_rows}"
    return body
