-- =============================================================================
-- init_snowflake.sql
-- Bootstrap script: creates the PHARMA_DB database, schemas, and base tables.
-- Run once as SYSADMIN (or a role with CREATE DATABASE privilege).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Database & schemas
-- ---------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS PHARMA_DB;
USE DATABASE PHARMA_DB;

CREATE SCHEMA IF NOT EXISTS PHARMA_DB.RAW;
CREATE SCHEMA IF NOT EXISTS PHARMA_DB.STAGING;
CREATE SCHEMA IF NOT EXISTS PHARMA_DB.MARTS;

-- ---------------------------------------------------------------------------
-- RAW.ADVERSE_EVENTS
-- Landing table for FDA FAERS API payloads. All values stored as VARCHAR
-- so ingestion never fails on type mismatches; transformations happen
-- downstream in STAGING.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS PHARMA_DB.RAW.ADVERSE_EVENTS (
    event_id          VARCHAR(64)    NOT NULL COMMENT 'FDA safetyreportid — unique per safety report',
    receive_date      VARCHAR(8)               COMMENT 'Date FDA received the report (YYYYMMDD string from API)',
    report_country    VARCHAR(4)               COMMENT 'ISO country code where event was reported',
    drug_name         VARCHAR(512)             COMMENT 'Medicinal product name (first drug in the report)',
    drug_indication   VARCHAR(512)             COMMENT 'Indication for which the drug was used',
    reaction_outcome  VARCHAR(8)               COMMENT 'Outcome code: 1–6 per MedDRA spec',
    serious           VARCHAR(4)               COMMENT '1 = serious, 2 = not serious',
    source_file       VARCHAR(256)             COMMENT 'Identifier of the API call / batch that loaded this row',
    loaded_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP() COMMENT 'Row insertion timestamp (UTC)'
);

-- ---------------------------------------------------------------------------
-- RAW.PIPELINE_QUALITY_LOG
-- Audit log written by quality/run_checks.py after every pipeline run.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS PHARMA_DB.RAW.PIPELINE_QUALITY_LOG (
    check_name        VARCHAR(128)   NOT NULL COMMENT 'Human-readable name of the DQ check',
    table_name        VARCHAR(256)            COMMENT 'Fully-qualified table the check ran against',
    records_checked   NUMBER(18, 0)           COMMENT 'Total rows evaluated by the check',
    records_failed    NUMBER(18, 0)           COMMENT 'Rows that did not pass the check',
    pass_fail         VARCHAR(4)     NOT NULL COMMENT 'PASS or FAIL',
    run_at            TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP() COMMENT 'When the check was executed (UTC)'
);
