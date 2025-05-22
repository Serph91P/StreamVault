#!/usr/bin/env python
"""
Migration management utility

This script provides tools to:
1. List all migrations
2. Check migration status
3. Mark migrations as applied/unapplied
4. Run specific migrations
"""
import os
import sys
import argparse
import logging
from typing import List, Dict, Any

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(script_dir))

from app.services.migration_service import MigrationService
from app.database import SessionLocal, engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_migrations_table():
    """Ensure migrations table exists"""
    MigrationService.initialize_migrations_table()

def list_all_migrations() -> List[Dict[str, Any]]:
    """List all available migrations"""
    setup_migrations_table()
    
    migration_scripts = MigrationService.get_all_migration_scripts()
    applied_migrations = MigrationService.get_applied_migrations()
    
    results = []
    for script_path in migration_scripts:
        script_name = os.path.basename(script_path)
        status = "APPLIED" if script_name in applied_migrations else "PENDING"
        
        # Get file modification time
        mtime = os.path.getmtime(script_path)
        from datetime import datetime
        modified = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        results.append({
            "name": script_name,
            "status": status,
            "path": script_path,
            "modified": modified
        })
    
    return results

def check_migration_status() -> None:
    """Print status of all migrations"""
    migrations = list_all_migrations()
    
    print("\n=== Migration Status ===\n")
    print(f"Found {len(migrations)} migrations\n")
    
    for migration in migrations:
        status_color = "\033[32m" if migration["status"] == "APPLIED" else "\033[33m"
        reset_color = "\033[0m"
        print(f"{status_color}{migration['status']}{reset_color} - {migration['name']} (modified: {migration['modified']})")
    
    print("\n")

def mark_migration(script_name: str, status: bool) -> None:
    """Mark a migration as applied or unapplied"""
    setup_migrations_table()
    
    with SessionLocal() as session:
        if status:
            # Mark as applied
            exists = session.execute(
                text("SELECT 1 FROM migrations WHERE script_name = :name"),
                {"name": script_name}
            ).fetchone()
            
            if exists:
                print(f"Migration {script_name} is already marked as applied")
                return
                
            session.execute(
                text("INSERT INTO migrations (script_name, applied_at, success) VALUES (:name, NOW(), TRUE)"),
                {"name": script_name}
            )
            session.commit()
            print(f"Marked migration {script_name} as applied")
        else:
            # Mark as unapplied
            result = session.execute(
                text("DELETE FROM migrations WHERE script_name = :name"),
                {"name": script_name}
            )
            session.commit()
            
            if result.rowcount > 0:
                print(f"Marked migration {script_name} as unapplied")
            else:
                print(f"Migration {script_name} was not marked as applied")

def run_specific_migration(script_name: str, force: bool = False) -> None:
    """Run a specific migration"""
    setup_migrations_table()
    
    # Get all migration scripts
    migration_scripts = MigrationService.get_all_migration_scripts()
    script_path = None
    
    for path in migration_scripts:
        if os.path.basename(path) == script_name:
            script_path = path
            break
    
    if not script_path:
        print(f"Error: Migration {script_name} not found")
        return
    
    # Check if already applied
    applied_migrations = MigrationService.get_applied_migrations()
    if script_name in applied_migrations and not force:
        print(f"Migration {script_name} is already applied. Use --force to run it again.")
        return
    
    # Run the migration
    print(f"Running migration: {script_name}")
    success, message = MigrationService.run_migration_script(script_path)
    
    if success:
        print(f"Successfully ran migration: {script_name}")
        
        # Record in migrations table if not forced
        if not force:
            MigrationService.record_migration(script_name, True)
    else:
        print(f"Failed to run migration: {script_name}")
        print(f"Error: {message}")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="StreamVault Database Migration Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all migrations and their status")
    
    # Mark command
    mark_parser = subparsers.add_parser("mark", help="Mark a migration as applied/unapplied")
    mark_parser.add_argument("script", help="Migration script name")
    mark_parser.add_argument(
        "--status", 
        choices=["applied", "unapplied"], 
        required=True,
        help="Status to mark the migration as"
    )
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run a specific migration")
    run_parser.add_argument("script", help="Migration script name")
    run_parser.add_argument(
        "--force", 
        action="store_true",
        help="Force run even if already applied"
    )
    
    # Apply command
    apply_parser = subparsers.add_parser("apply", help="Apply all pending migrations")
    
    return parser.parse_args()

def main():
    """Main function"""
    args = parse_args()
    
    if args.command == "list":
        check_migration_status()
    elif args.command == "mark":
        mark_migration(args.script, args.status == "applied")
    elif args.command == "run":
        run_specific_migration(args.script, args.force)
    elif args.command == "apply":
        results = MigrationService.run_pending_migrations()
        if not results:
            print("No pending migrations to apply")
        else:
            print(f"Applied {len(results)} migrations:")
            for script, success, message in results:
                status = "SUCCESS" if success else "FAILED"
                print(f"  {status} - {script}")
    else:
        check_migration_status()  # Default action
    
if __name__ == "__main__":
    main()
