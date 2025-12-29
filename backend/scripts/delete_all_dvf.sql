-- Delete all DVF records (fast truncate)
BEGIN;

-- Disable triggers during delete
SET session_replication_role = 'replica';

-- Truncate is fastest - removes all rows instantly
TRUNCATE TABLE dvf_records RESTART IDENTITY CASCADE;

-- Re-enable triggers
SET session_replication_role = 'origin';

COMMIT;

-- Verify deletion
SELECT 'DVF records after deletion: ' || COUNT(*)::text FROM dvf_records;
