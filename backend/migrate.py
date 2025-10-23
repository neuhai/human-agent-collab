#!/usr/bin/env python3
"""
Database migration script for ShapeFactory backend
Run this script manually when database schema changes are needed
"""

import psycopg2
import psycopg2.extras
import os
from datetime import datetime, timezone

def get_db_connection():
    """Get database connection"""
    database_url = f"postgresql://{os.getenv('DATABASE_USER', '')}:{os.getenv('DATABASE_PASSWORD', 'shapefactory')}@{os.getenv('DATABASE_HOST', 'localhost')}:{os.getenv('DATABASE_PORT', '5432')}/{os.getenv('DATABASE_NAME', 'shape_factory_research')}"
    return psycopg2.connect(database_url)

def run_migrations():
    """Run all database migrations"""
    print("🔄 Starting database migrations...")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Migration 1: Create session_templates table
        print("📋 Migration 1: Creating session_templates table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS session_templates (
                template_id SERIAL PRIMARY KEY,
                session_id VARCHAR(50) NOT NULL,
                researcher_id VARCHAR(50) NOT NULL DEFAULT 'researcher',
                template_config JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                is_default BOOLEAN DEFAULT FALSE,
                UNIQUE(session_id, researcher_id)
            )
        """)
        print("✅ session_templates table created/verified")
        
        # Migration 2: Disable problematic trigger
        print("📋 Migration 2: Checking for problematic trigger...")
        cur.execute("""
            SELECT trigger_name 
            FROM information_schema.triggers 
            WHERE trigger_name = 'trigger_complete_transaction'
        """)
        
        trigger_exists = cur.fetchone()
        
        if trigger_exists:
            print("🔧 Found problematic trigger_complete_transaction, disabling it...")
            
            # Drop the trigger
            cur.execute("DROP TRIGGER IF EXISTS trigger_complete_transaction ON transactions")
            
            # Add comment to the function
            cur.execute("""
                COMMENT ON FUNCTION complete_transaction() IS 'DISABLED: This function was causing duplicate inventory updates. Inventory updates are now handled directly in game_engine.py'
            """)
            
            print("✅ Successfully disabled trigger_complete_transaction")
        else:
            print("✅ trigger_complete_transaction already disabled")
        
        conn.commit()
        print("✅ All migrations completed successfully!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error running migrations: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False
    
    return True

if __name__ == "__main__":
    success = run_migrations()
    if success:
        print("🎉 Migration completed successfully!")
    else:
        print("💥 Migration failed!")
        exit(1)
