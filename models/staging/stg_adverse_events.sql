-- =============================================================================
-- stg_adverse_events.sql
-- Staging view: cleans and standardises RAW.ADVERSE_EVENTS.
--
-- Key transformations:
--   • receive_date cast from YYYYMMDD string to DATE
--   • report_country upper-cased for consistent joins
--   • reaction_outcome integer codes decoded to human-readable labels
--   • Rows with NULL drug_name or reaction_outcome excluded
-- =============================================================================

CREATE OR REPLACE VIEW PHARMA_DB.STAGING.STG_ADVERSE_EVENTS AS

SELECT
    event_id,

    -- Cast the raw YYYYMMDD string to a proper DATE
    TRY_TO_DATE(receive_date, 'YYYYMMDD')           AS receive_date,

    -- Normalise country codes to upper-case
    UPPER(TRIM(report_country))                      AS report_country,

    -- Trim whitespace from free-text drug fields
    TRIM(drug_name)                                  AS drug_name,
    TRIM(drug_indication)                            AS drug_indication,

    -- Keep the raw numeric code for filtering / joining
    reaction_outcome                                 AS reaction_outcome_code,

    -- Decode MedDRA outcome codes to labels
    CASE reaction_outcome
        WHEN '1' THEN 'Recovered'
        WHEN '2' THEN 'Recovering'
        WHEN '3' THEN 'Not Recovered'
        WHEN '4' THEN 'Recovered with Sequelae'
        WHEN '5' THEN 'Fatal'
        WHEN '6' THEN 'Unknown'
        ELSE           'Unknown'
    END                                              AS reaction_outcome_label,

    -- Cast seriousness flag to boolean for clarity downstream
    CASE serious
        WHEN '1' THEN TRUE
        WHEN '2' THEN FALSE
        ELSE           NULL
    END                                              AS is_serious,

    source_file,
    loaded_at

FROM PHARMA_DB.RAW.ADVERSE_EVENTS

-- Remove records that would make the safety mart meaningless
WHERE drug_name       IS NOT NULL
  AND TRIM(drug_name) <> ''
  AND reaction_outcome IS NOT NULL
  AND TRIM(reaction_outcome) <> '';
