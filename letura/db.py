"""Database engines and safe query helpers.

Two engines exist:
* the *admin* engine (credentials DB_USER/DB_PASSWORD) – used only by the
  pipeline to build derived tables;
* the *read-only* engine (AI_DB_USER/AI_DB_PASSWORD) – a dedicated MySQL
  account with SELECT on approved objects only. The dashboard and the AI
  analyst use this engine. If the read-only account is not provisioned yet,
  the dashboard falls back to the admin engine but every session is still
  forced into READ ONLY transaction mode.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Mapping

import pandas as pd
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL, Engine

from letura.config import PROJECT_ROOT, get_settings

log = logging.getLogger(__name__)

# Objects the read-only account and the AI may read. Raw tables are excluded.
APPROVED_OBJECTS: tuple[str, ...] = (
    "int_hamburg_listings",
    "v_ai_listings",
    "fact_mietenspiegel_benchmarks",
    "analytics_hamburg_rental_market",
    "analytics_hamburg_neighbourhoods",
    "analytics_hamburg_property_insights",
    "analytics_mietenspiegel_reference",
    "analytics_data_quality",
    "analytics_location_matching",
    "meta_pipeline_runs",
)


_RO_STATE: dict = {}


SNAPSHOT_PATH = PROJECT_ROOT / "data" / "snapshot" / "letura_snapshot.sqlite"


def backend() -> str:
    """'mysql' (local, live) or 'snapshot' (bundled read-only SQLite for cloud demos).

    DATA_BACKEND=mysql|snapshot|auto (default auto: MySQL if credentials exist, else snapshot).
    """
    mode = os.getenv("DATA_BACKEND", "auto").strip().lower()
    if mode in {"mysql", "snapshot"}:
        return mode
    s = get_settings().db
    if s.user and s.password.get_secret_value():
        return "mysql"
    return "snapshot" if SNAPSHOT_PATH.exists() else "mysql"


class DatabaseUnavailable(RuntimeError):
    """Raised with a user-safe message (never contains credentials)."""


def _url(user: str, password: str) -> URL:
    s = get_settings().db
    return URL.create(
        "mysql+pymysql",
        username=user,
        password=password,
        host=s.host,
        port=s.port,
        database=s.name,
        query={"charset": "utf8mb4"},
    )


@lru_cache(maxsize=1)
def admin_engine() -> Engine:
    s = get_settings().db
    return create_engine(
        _url(s.user, s.password.get_secret_value()),
        pool_pre_ping=True,
        pool_recycle=1800,
        hide_parameters=True,
    )


def _install_readonly_guards(engine: Engine, timeout_ms: int) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _record):  # pragma: no cover - driver level
        cur = dbapi_conn.cursor()
        cur.execute(f"SET SESSION MAX_EXECUTION_TIME={int(timeout_ms)}")
        cur.execute("SET SESSION TRANSACTION READ ONLY")
        cur.close()


@lru_cache(maxsize=1)
def readonly_engine() -> Engine:
    """Engine for dashboard + AI. Always READ ONLY with a statement timeout."""
    if backend() == "snapshot":
        if not SNAPSHOT_PATH.exists():
            raise DatabaseUnavailable("Data snapshot not found. Run `python scripts/export_snapshot.py` locally and commit data/snapshot/.")
        _RO_STATE["dedicated"] = False
        return create_engine(f"sqlite:///file:{SNAPSHOT_PATH.as_posix()}?mode=ro&uri=true")
    settings = get_settings()
    timeout_ms = settings.ai.query_timeout_seconds * 1000
    ro_pw = settings.ai.readonly_password.get_secret_value()
    candidates = []
    if settings.ai.readonly_user and ro_pw:
        candidates.append((settings.ai.readonly_user, ro_pw, True))
    candidates.append((settings.db.user, settings.db.password.get_secret_value(), False))

    last_error: Exception | None = None
    for user, pw, dedicated in candidates:
        eng = create_engine(
            _url(user, pw),
            pool_pre_ping=True,
            pool_recycle=1800,
            hide_parameters=True,
            connect_args={"read_timeout": settings.ai.query_timeout_seconds + 5, "connect_timeout": 5},
        )
        _install_readonly_guards(eng, timeout_ms)
        try:
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            _RO_STATE["dedicated"] = dedicated
            return eng
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            eng.dispose()
            log.warning("Read-only connection attempt failed (dedicated=%s): %s", dedicated, type(exc).__name__)
    raise DatabaseUnavailable(
        "Could not connect to MySQL. Check that the server is running on the configured host/port "
        f"and that .env credentials are valid ({type(last_error).__name__})."
    )


def is_dedicated_readonly() -> bool:
    try:
        readonly_engine()
        return bool(_RO_STATE.get("dedicated"))
    except DatabaseUnavailable:
        return False


def read_df(sql: str, params: Mapping[str, Any] | None = None, engine: Engine | None = None) -> pd.DataFrame:
    """Execute a parameterised SELECT and return a DataFrame."""
    eng = engine or readonly_engine()
    try:
        with eng.connect() as conn:
            return pd.read_sql(text(sql), conn, params=dict(params or {}))
    except DatabaseUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        msg = str(getattr(exc, "orig", exc))
        raise DatabaseUnavailable(f"Database query failed: {msg[:300]}") from exc


def scalar(sql: str, params: Mapping[str, Any] | None = None, engine: Engine | None = None) -> Any:
    eng = engine or readonly_engine()
    with eng.connect() as conn:
        return conn.execute(text(sql), dict(params or {})).scalar()


def table_exists(name: str, engine: Engine | None = None) -> bool:
    return bool(
        scalar(
            "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t",
            {"t": name},
            engine or admin_engine(),
        )
    )


def row_count(name: str, engine: Engine | None = None) -> int:
    if not name.replace("_", "").isalnum():
        raise ValueError("invalid identifier")
    return int(scalar(f"SELECT COUNT(*) FROM `{name}`", engine=engine or admin_engine()))


def data_source_label() -> str:
    if backend() == "snapshot":
        return "Bundled read-only data snapshot (demo)"
    return "Dedicated read-only MySQL account" if is_dedicated_readonly() else "MySQL (READ ONLY session)"
