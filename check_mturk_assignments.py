#!/usr/bin/env python3
"""
Script to check MTurk assignments and session status in Docker database.

Features:
1. View all assigned workers (MTurk assignments)
2. View all created but not started sessions
"""

import subprocess
import json
import argparse
from datetime import datetime

def query_docker_database(query, container_name='human-agent-postgres'):
    """Execute SQL query in Docker container and return JSON results"""
    # Build query with JSON output
    json_query = f"SELECT json_agg(row_to_json(t)) FROM ({query}) t"
    
    cmd = [
        'docker', 'exec', container_name,
        'psql', '-U', 'postgres', '-d', 'shape_factory_research',
        '-t', '-c', json_query
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        
        if not output or output == 'null' or output == '[null]':
            return []
        
        data = json.loads(output)
        if isinstance(data, list):
            return data
        return []
    except subprocess.CalledProcessError as e:
        print(f"❌ Error querying Docker container: {e}")
        if e.stderr:
            print(f"   Error: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return []

def format_date(date_str):
    """Format date string for display"""
    if not date_str:
        return 'N/A'
    try:
        # Try parsing ISO format
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return str(date_str)

def show_all_assignments(container_name='human-agent-postgres'):
    """Show all MTurk worker assignments"""
    print("="*80)
    print("📋 ALL MTURK WORKER ASSIGNMENTS")
    print("="*80)
    
    query = """
        SELECT 
            s.session_code,
            s.experiment_type,
            s.session_status,
            s.created_at as session_created_at,
            p.participant_code,
            p.participant_type,
            p.mturk_worker_id,
            p.mturk_assignment_id,
            p.mturk_hit_id,
            p.login_status,
            p.created_at as participant_created_at
        FROM participants p
        JOIN sessions s ON p.session_id = s.session_id
        WHERE (p.mturk_worker_id IS NOT NULL 
               OR p.mturk_assignment_id IS NOT NULL 
               OR p.mturk_hit_id IS NOT NULL)
        ORDER BY s.created_at DESC, p.created_at DESC
    """
    
    results = query_docker_database(query, container_name)
    
    if not results:
        print("❌ No MTurk assignments found.")
        return
    
    # Group by session
    sessions = {}
    for row in results:
        session_code = row.get('session_code', 'N/A')
        if session_code not in sessions:
            sessions[session_code] = []
        sessions[session_code].append(row)
    
    print(f"\nTotal Assignments: {len(results)}")
    print(f"Unique Sessions: {len(sessions)}\n")
    
    for session_code, assignments in sorted(sessions.items()):
        print(f"\n🔹 Session: {session_code}")
        print(f"   Experiment Type: {assignments[0].get('experiment_type', 'N/A')}")
        print(f"   Session Status: {assignments[0].get('session_status', 'N/A')}")
        print(f"   Created: {format_date(assignments[0].get('session_created_at'))}")
        
        for assignment in assignments:
            print(f"\n   👤 Participant: {assignment.get('participant_code', 'N/A')}")
            print(f"      Type: {assignment.get('participant_type', 'N/A')}")
            print(f"      Worker ID: {assignment.get('mturk_worker_id') or 'N/A'}")
            print(f"      Assignment ID: {assignment.get('mturk_assignment_id') or 'N/A'}")
            print(f"      HIT ID: {assignment.get('mturk_hit_id') or 'N/A'}")
            print(f"      Login Status: {assignment.get('login_status', 'N/A')}")
    
    print("\n" + "="*80)

def show_unstarted_sessions(container_name='human-agent-postgres'):
    """Show all created but not started sessions"""
    print("="*80)
    print("📋 ALL CREATED BUT NOT STARTED SESSIONS")
    print("="*80)
    
    query = """
        SELECT 
            s.session_code,
            s.experiment_type,
            s.session_status,
            s.created_at,
            COUNT(p.participant_id) as participant_count,
            COUNT(CASE WHEN p.mturk_worker_id IS NOT NULL THEN 1 END) as assigned_count,
            COUNT(CASE WHEN p.participant_type = 'human' AND p.is_agent = false THEN 1 END) as human_count
        FROM sessions s
        LEFT JOIN participants p ON s.session_id = p.session_id
        WHERE s.session_status = 'idle'
        GROUP BY s.session_id, s.session_code, s.experiment_type, s.session_status, s.created_at
        ORDER BY s.created_at DESC
    """
    
    results = query_docker_database(query, container_name)
    
    if not results:
        print("❌ No unstarted sessions found.")
        return
    
    print(f"\nTotal Unstarted Sessions: {len(results)}\n")
    
    for session in results:
        print(f"🔹 Session: {session.get('session_code', 'N/A')}")
        print(f"   Experiment Type: {session.get('experiment_type', 'N/A')}")
        print(f"   Status: {session.get('session_status', 'N/A')}")
        print(f"   Created: {format_date(session.get('created_at'))}")
        print(f"   Total Participants: {session.get('participant_count', 0)}")
        print(f"   Human Participants: {session.get('human_count', 0)}")
        print(f"   MTurk Assigned: {session.get('assigned_count', 0)}")
        print()

def main():
    parser = argparse.ArgumentParser(
        description='Check MTurk assignments and session status in Docker database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show all MTurk worker assignments
  python check_mturk_assignments.py --assignments
  
  # Show all unstarted sessions
  python check_mturk_assignments.py --sessions
  
  # Show both
  python check_mturk_assignments.py --assignments --sessions
        """
    )
    
    parser.add_argument('--assignments', '-a', action='store_true', 
                       help='Show all MTurk worker assignments')
    parser.add_argument('--sessions', '-s', action='store_true',
                       help='Show all created but not started sessions')
    parser.add_argument('--container', '-c', type=str, default='human-agent-postgres',
                       help='Docker container name (default: human-agent-postgres)')
    
    args = parser.parse_args()
    
    # If no arguments, show both by default
    if not args.assignments and not args.sessions:
        args.assignments = True
        args.sessions = True
    
    print("🐳 Querying Docker container database...")
    print(f"   Container: {args.container}\n")
    
    if args.assignments:
        show_all_assignments(args.container)
        print()
    
    if args.sessions:
        show_unstarted_sessions(args.container)

if __name__ == '__main__':
    main()
