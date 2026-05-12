"""
run_checks.py
~~~~~~~~~~~~~
Execute each data-quality check defined in checks.sql against Snowflake,
log results to RAW.PIPELINE_QUALITY_LOG, print a summary table, and exit
with a non-zero code if any check fails (CI-friendly).

Usage:
    python quality/run_checks.py

Environment variables (see .env.example):
    SNOWFLAKE_ACCOUNT, SNOWFLAKE_ORG, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
    SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_ROLE
"""

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import snowflake.connector
from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

CHECKS_SQL_PATH = Path(__file__).parent / "checks.sql"
LOG_TABLE = "PHARMA_DB.RAW.PIPELINE_QUALITY_LOG"
TARGET_TABLE = "PHARMA_DB.RAW.ADVERSE_EVENTS"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
class CheckResult(NamedTuple):
    check_name: str
    records_checked: int
    records_failed: int
    pass_fail: str


# ---------------------------------------------------------------------------
# SQL parsing
# ---------------------------------------------------------------------------
def parse_checks(sql_text: str) -> list[tuple[str, str]]:
    """
    Return a list of (check_name, sql) tuples parsed from checks.sql.

    Each check is identified by a comment line of the form:
        -- check_name: <name>
    followed by the SELECT statement that runs it.
    """
    checks: list[tuple[str, str]] = []
    # Split on the sentinel comment; keep the name in group 1
    pattern = re.compile(
        r"--\s*check_name:\s*(\S+)\s*\n(SELECT[\s\S]+?)(?=--\s*check_name:|\Z)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(sql_text):
        name = match.group(1).strip()
        sql = match.group(2).strip().rstrip(";")
        checks.append((name, sql))

    if not checks:
        raise ValueError(f"No check_name markers found in {CHECKS_SQL_PATH}")
    return checks


# ---------------------------------------------------------------------------
# Snowflake helpers
# ---------------------------------------------------------------------------
def get_snowflake_connection() -> snowflake.connector.SnowflakeConnection:
    """Build a Snowflake connection from environment variables."""
    account = os.environ["SNOWFLAKE_ACCOUNT"]
    org = os.environ.get("SNOWFLAKE_ORG", "")
    full_account = f"{org}-{account}" if org else account

    return snowflake.connector.connect(
        account=full_account,
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "PHARMA_DB"),
        role=os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
        session_parameters={"QUERY_TAG": "pharma-pipeline-quality"},
    )


def run_check(
    cur: snowflake.connector.cursor.SnowflakeCursor,
    check_name: str,
    sql: str,
) -> CheckResult:
    """Execute a single DQ check and return a CheckResult."""
    log.info("Running check: %s", check_name)
    cur.execute(sql)
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"Check '{check_name}' returned no rows")

    records_checked = int(row[0])
    records_failed = int(row[1])
    pass_fail = "PASS" if records_failed == 0 else "FAIL"
    return CheckResult(check_name, records_checked, records_failed, pass_fail)


INSERT_LOG_SQL = f"""
INSERT INTO {LOG_TABLE}
    (check_name, table_name, records_checked, records_failed, pass_fail, run_at)
VALUES (%s, %s, %s, %s, %s, %s)
"""


def log_results(
    conn: snowflake.connector.SnowflakeConnection,
    results: list[CheckResult],
) -> None:
    """Persist check results to the quality-log table."""
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        (r.check_name, TARGET_TABLE, r.records_checked, r.records_failed, r.pass_fail, run_at)
        for r in results
    ]
    with conn.cursor() as cur:
        cur.executemany(INSERT_LOG_SQL, rows)
    conn.commit()
    log.info("Logged %d check results to %s", len(rows), LOG_TABLE)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    # --- Parse checks ---
    if not CHECKS_SQL_PATH.exists():
        log.error("checks.sql not found at %s", CHECKS_SQL_PATH)
        sys.exit(1)

    sql_text = CHECKS_SQL_PATH.read_text()
    checks = parse_checks(sql_text)
    log.info("Loaded %d checks from %s", len(checks), CHECKS_SQL_PATH)

    # --- Connect ---
    log.info("Connecting to Snowflake…")
    try:
        conn = get_snowflake_connection()
    except KeyError as exc:
        log.error("Missing required environment variable: %s", exc)
        sys.exit(1)
    except snowflake.connector.errors.DatabaseError as exc:
        log.error("Snowflake connection failed: %s", exc)
        sys.exit(1)

    # --- Run checks ---
    results: list[CheckResult] = []
    try:
        with conn.cursor() as cur:
            for check_name, sql in checks:
                try:
                    result = run_check(cur, check_name, sql)
                    results.append(result)
                except Exception as exc:  # noqa: BLE001
                    log.error("Check '%s' raised an error: %s", check_name, exc)
                    results.append(CheckResult(check_name, 0, 0, "ERROR"))

        # --- Persist results ---
        log_results(conn, [r for r in results if r.pass_fail != "ERROR"])
    finally:
        conn.close()

    # --- Print summary table ---
    table_rows = [
        [r.check_name, r.records_checked, r.records_failed, r.pass_fail]
        for r in results
    ]
    print("\n" + tabulate(
        table_rows,
        headers=["Check", "Checked", "Failed", "Result"],
        tablefmt="github",
    ))

    # --- CI exit code ---
    failed = [r for r in results if r.pass_fail != "PASS"]
    if failed:
        print(f"\n{len(failed)} check(s) FAILED.")
        sys.exit(1)
    else:
        print("\nAll checks PASSED.")


if __name__ == "__main__":
    main()
