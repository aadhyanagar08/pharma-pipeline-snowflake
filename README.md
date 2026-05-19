# pharma-pipeline-snowflake

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?logo=snowflake&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI%2FCD-2088FF?logo=githubactions&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

ELT pipeline that ingests FDA adverse drug event data from the public FAERS API, loads it into Snowflake, and transforms it into analysis-ready marts — with built-in data quality checks and a GitHub Actions CI/CD workflow.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA FLOW                                │
│                                                                 │
│   FDA FAERS API          Snowflake                              │
│  ┌──────────────┐    ┌──────────────────────────────────────┐  │
│  │ /drug/event  │───▶│  RAW.ADVERSE_EVENTS                  │  │
│  │ .json?limit  │    │  (raw VARCHAR landing table)         │  │
│  │ =100         │    └───────────────┬──────────────────────┘  │
│  └──────────────┘                    │  stg_adverse_events.sql  │
│                                      ▼                          │
│                         ┌────────────────────────────────────┐ │
│                         │  STAGING.STG_ADVERSE_EVENTS        │ │
│                         │  (typed, cleaned, decoded view)    │ │
│                         └───────────────┬────────────────────┘ │
│                                         │  mart_drug_safety.sql │
│                                         ▼                       │
│                         ┌────────────────────────────────────┐ │
│                         │  MARTS.MART_DRUG_SAFETY            │ │
│                         │  (aggregated safety metrics view)  │ │
│                         └────────────────────────────────────┘ │
│                                                                 │
│   Quality log ──▶  RAW.PIPELINE_QUALITY_LOG                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
pharma-pipeline-snowflake/
├── .github/
│   └── workflows/
│       └── pipeline.yml          # CI/CD: runs on push to main
├── ingestion/
│   └── extract_load.py           # FDA API → Snowflake RAW
├── models/
│   ├── staging/
│   │   └── stg_adverse_events.sql   # RAW → STAGING view
│   └── marts/
│       └── mart_drug_safety.sql     # STAGING → MARTS view
├── quality/
│   ├── checks.sql                # Four named DQ checks
│   └── run_checks.py             # Runs checks, logs results, CI exit
├── setup/
│   └── init_snowflake.sql        # One-time DB/schema/table setup
├── requirements.txt
├── .env.example
└── README.md
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Snowflake account | `wxxgggx-kq66913` |
| Snowflake warehouse | `COMPUTE_WH` (or your own) |

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/<your-org>/pharma-pipeline-snowflake.git
cd pharma-pipeline-snowflake

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Fill in SNOWFLAKE_USER and SNOWFLAKE_PASSWORD in .env
```

| Variable | Description |
|----------|-------------|
| `SNOWFLAKE_ACCOUNT` | Account locator (e.g. `kq66913`) |
| `SNOWFLAKE_ORG` | Org name (e.g. `wxxgggx`) |
| `SNOWFLAKE_USER` | Your Snowflake username |
| `SNOWFLAKE_PASSWORD` | Your Snowflake password |
| `SNOWFLAKE_WAREHOUSE` | Virtual warehouse name |
| `SNOWFLAKE_DATABASE` | `PHARMA_DB` |
| `SNOWFLAKE_ROLE` | `SYSADMIN` or a custom role |
| `ETL_MONITOR_URL` | Base URL of the ETL Monitor API (e.g. `https://etl-monitor-api.onrender.com`) |
| `ETL_MONITOR_PIPELINE_ID` | Pipeline ID registered in the monitor (e.g. `1`) |

### 3. Initialise Snowflake (one-time)

Run the bootstrap SQL in Snowsight or SnowSQL:

```bash
snowsql -a wxxgggx-kq66913 -u <user> -f setup/init_snowflake.sql
```

Or paste `setup/init_snowflake.sql` directly into a Snowsight worksheet.

---

## Running the Pipeline

### Extract & Load

Pulls 100 records from the FDA FAERS API and inserts them into `RAW.ADVERSE_EVENTS`:

```bash
python ingestion/extract_load.py
```

Expected output:
```
2026-05-12 10:00:01  INFO      Fetching 100 records from https://api.fda.gov/drug/event.json
2026-05-12 10:00:02  INFO      Received 100 results from FDA API
2026-05-12 10:00:03  INFO      Inserted 100 rows into RAW.ADVERSE_EVENTS

Rows loaded into RAW.ADVERSE_EVENTS: 100
```

### Apply SQL Models

Run these in Snowsight/SnowSQL, or via the inline Python blocks in the CI workflow:

```sql
-- Staging view
<contents of models/staging/stg_adverse_events.sql>

-- Mart view
<contents of models/marts/mart_drug_safety.sql>
```

### Run Data Quality Checks

```bash
python quality/run_checks.py
```

Expected output (all passing):
```
| Check                    | Checked | Failed | Result |
|--------------------------|---------|--------|--------|
| null_drug_names          |     100 |      0 | PASS   |
| null_reaction_outcomes   |     100 |      0 | PASS   |
| row_count_gt_zero        |     100 |      0 | PASS   |
| serious_flag_valid_values|     100 |      0 | PASS   |

All checks PASSED.
```

Exits with code `1` if any check fails — safe for CI gates.

---

## Data Quality Checks

| Check | Description | Passes when |
|-------|-------------|-------------|
| `null_drug_names` | No blank/null `drug_name` in RAW | `records_failed = 0` |
| `null_reaction_outcomes` | No blank/null `reaction_outcome` in RAW | `records_failed = 0` |
| `row_count_gt_zero` | Table is not empty | `COUNT(*) > 0` |
| `serious_flag_valid_values` | `serious` is always `'1'` or `'2'` | `records_failed = 0` |

All check results are persisted to `RAW.PIPELINE_QUALITY_LOG` for historical trend analysis.

---

## CI/CD (GitHub Actions)

The workflow `.github/workflows/pipeline.yml` triggers on every push to `main` and runs:

1. **Checkout** — fetch the repo
2. **Python 3.11** — set up runtime + cache pip
3. **Install deps** — `pip install -r requirements.txt`
4. **Extract & Load** — `python ingestion/extract_load.py`
5. **Staging model** — applies `stg_adverse_events.sql` via inline Python
6. **Mart model** — applies `mart_drug_safety.sql` via inline Python
7. **Quality checks** — `python quality/run_checks.py` (fails the run if any check fails)

### GitHub Secrets required

Add these under **Settings → Secrets and variables → Actions**:

```
SNOWFLAKE_ACCOUNT
SNOWFLAKE_ORG
SNOWFLAKE_USER
SNOWFLAKE_PASSWORD
SNOWFLAKE_WAREHOUSE
SNOWFLAKE_DATABASE
SNOWFLAKE_ROLE
```

---

## Pipeline Health Monitoring

After every execution, this pipeline reports its run results to a live ETL Monitor API. The `monitoring/etl_reporter.py` module handles all reporting and silently skips if `ETL_MONITOR_URL` is not set.

- **Live health dashboard:** [https://etl-monitor-api.onrender.com/pipelines/1/health](https://etl-monitor-api.onrender.com/pipelines/1/health)
- **Run history:** [https://etl-monitor-api.onrender.com/pipelines/1/runs](https://etl-monitor-api.onrender.com/pipelines/1/runs)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Data source | FDA FAERS Public API |
| Ingestion | Python + `requests` |
| Warehouse | Snowflake |
| Transformation | SQL (CREATE OR REPLACE VIEW) |
| Quality | Python + `tabulate` |
| Orchestration | GitHub Actions |
| Credentials | `python-dotenv` / GitHub Secrets |

---

## Querying the Mart

Once the pipeline has run, query the safety mart directly in Snowsight:

```sql
-- Top 10 drugs by adverse event count
SELECT drug_name, reaction_outcome_label, event_count, serious_rate_pct
FROM PHARMA_DB.MARTS.MART_DRUG_SAFETY
LIMIT 10;

-- Drugs with a fatality rate above 10%
SELECT *
FROM PHARMA_DB.MARTS.MART_DRUG_SAFETY
WHERE reaction_outcome_label = 'Fatal'
  AND serious_rate_pct > 10
ORDER BY serious_rate_pct DESC;
```
