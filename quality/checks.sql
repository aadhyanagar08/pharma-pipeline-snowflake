-- =============================================================================
-- checks.sql
-- Data-quality checks for the pharma pipeline.
-- Each named query returns a single row with:
--   records_checked  – total rows in scope
--   records_failed   – rows that violated the rule
-- A check PASSES when records_failed = 0.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- check_null_drug_names
-- Ensures every raw adverse-event record carries a drug name.
-- ---------------------------------------------------------------------------
-- check_name: null_drug_names
SELECT
    COUNT(*)                                  AS records_checked,
    COUNT(CASE WHEN drug_name IS NULL
                 OR TRIM(drug_name) = ''
               THEN 1 END)                    AS records_failed
FROM PHARMA_DB.RAW.ADVERSE_EVENTS;

-- ---------------------------------------------------------------------------
-- check_null_reaction_outcomes
-- Ensures every raw record carries a reaction-outcome code.
-- ---------------------------------------------------------------------------
-- check_name: null_reaction_outcomes
SELECT
    COUNT(*)                                  AS records_checked,
    COUNT(CASE WHEN reaction_outcome IS NULL
                 OR TRIM(reaction_outcome) = ''
               THEN 1 END)                    AS records_failed
FROM PHARMA_DB.RAW.ADVERSE_EVENTS;

-- ---------------------------------------------------------------------------
-- check_row_count_gt_zero
-- Ensures the table is not empty (i.e., ingestion loaded at least one row).
-- ---------------------------------------------------------------------------
-- check_name: row_count_gt_zero
SELECT
    COUNT(*)                                  AS records_checked,
    CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS records_failed
FROM PHARMA_DB.RAW.ADVERSE_EVENTS;

-- ---------------------------------------------------------------------------
-- check_serious_flag_values
-- Ensures the seriousness flag only contains the expected values 1 or 2.
-- Any other value (including NULL) is treated as a failure.
-- ---------------------------------------------------------------------------
-- check_name: serious_flag_valid_values
SELECT
    COUNT(*)                                  AS records_checked,
    COUNT(CASE WHEN serious NOT IN ('1', '2')
                 OR serious IS NULL
               THEN 1 END)                    AS records_failed
FROM PHARMA_DB.RAW.ADVERSE_EVENTS;
