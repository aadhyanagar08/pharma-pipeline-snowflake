-- =============================================================================
-- mart_drug_safety.sql
-- Analytics mart: aggregates adverse-event counts per drug and outcome.
--
-- Metrics:
--   • event_count        – total reports for the drug/outcome combination
--   • serious_event_count – subset flagged as serious (is_serious = TRUE)
--   • serious_rate_pct   – serious_event_count / event_count × 100, rounded
--
-- Ordered by event_count DESC so the busiest drug-outcome pairs surface first.
-- =============================================================================

CREATE OR REPLACE VIEW PHARMA_DB.MARTS.MART_DRUG_SAFETY AS

SELECT
    drug_name,
    reaction_outcome_label,

    COUNT(*)                                                  AS event_count,

    COUNT(CASE WHEN is_serious = TRUE THEN 1 END)            AS serious_event_count,

    -- Round to 2 dp; NULLIF guards against division-by-zero on empty partitions
    ROUND(
        COUNT(CASE WHEN is_serious = TRUE THEN 1 END)
        / NULLIF(COUNT(*), 0)
        * 100,
        2
    )                                                         AS serious_rate_pct

FROM PHARMA_DB.STAGING.STG_ADVERSE_EVENTS

-- Exclude rows where the staging view could not decode a valid outcome
WHERE reaction_outcome_label IS NOT NULL

GROUP BY
    drug_name,
    reaction_outcome_label

ORDER BY
    event_count DESC;
