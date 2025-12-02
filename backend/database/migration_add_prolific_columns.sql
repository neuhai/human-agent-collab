-- Migration: Add Prolific columns to participants table
-- Date: 2025-12-02
-- Description: Adds prolific_pid, prolific_study_id, and prolific_session_id columns
--              to support Prolific auto-assignment similar to MTurk

-- Check if columns exist before adding them (idempotent)
DO $$
BEGIN
    -- Add prolific_pid column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'participants' AND column_name = 'prolific_pid'
    ) THEN
        ALTER TABLE participants ADD COLUMN prolific_pid character varying(255);
        RAISE NOTICE 'Added column prolific_pid';
    ELSE
        RAISE NOTICE 'Column prolific_pid already exists';
    END IF;

    -- Add prolific_study_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'participants' AND column_name = 'prolific_study_id'
    ) THEN
        ALTER TABLE participants ADD COLUMN prolific_study_id character varying(255);
        RAISE NOTICE 'Added column prolific_study_id';
    ELSE
        RAISE NOTICE 'Column prolific_study_id already exists';
    END IF;

    -- Add prolific_session_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'participants' AND column_name = 'prolific_session_id'
    ) THEN
        ALTER TABLE participants ADD COLUMN prolific_session_id character varying(255);
        RAISE NOTICE 'Added column prolific_session_id';
    ELSE
        RAISE NOTICE 'Column prolific_session_id already exists';
    END IF;
END $$;

