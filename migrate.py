#!/usr/bin/env python3
"""
Alembic Migration Script
========================

This script automates the entire Alembic migration process:
1. Generate new migration file
2. Apply migration to database
3. Handle both schema and data changes

Usage:
    python migrate.py "add new column to users"
    python migrate.py "change column type"
    python migrate.py "add new table"
"""

import sys
import subprocess
import argparse
from pathlib import Path
from typing import Optional

def run_command(command: str, description: str) -> bool:
    """
    Execute a command and handle errors
    
    Args:
        command (str): Command to execute
        description (str): Description of what the command does
        
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"\n{'='*50}")
    print(f"STEP: {description}")
    print(f"COMMAND: {command}")
    print(f"{'='*50}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            print(f"SUCCESS: {description}")
            if result.stdout:
                print(f"OUTPUT: {result.stdout}")
            return True
        else:
            print(f"ERROR: {description}")
            print(f"ERROR OUTPUT: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"EXCEPTION: {description}")
        print(f"ERROR: {str(e)}")
        return False

def generate_migration(message: str) -> bool:
    """
    Generate new Alembic migration file
    
    Args:
        message (str): Migration message/description
        
    Returns:
        bool: True if successful, False otherwise
    """
    command = f'.\\venv\\Scripts\\alembic revision --autogenerate -m "{message}"'
    return run_command(command, "Generating new migration file")
#apply migration to database
def apply_migration() -> bool:

    command = ".\\venv\\Scripts\\alembic upgrade head"
    return run_command(command, "Applying migration to database")

#define function to check migration status
def check_migration_status() -> bool:

    command = ".\\venv\\Scripts\\alembic current"
    return run_command(command, "Checking current migration status")

#define function to show migration history
def show_migration_history() -> bool:

    command = ".\\venv\\Scripts\\alembic history"
    return run_command(command, "Showing migration history")

#define function to validate environment
def validate_environment() -> bool:
    
    # Check if alembic.ini exists
    alembic_ini = Path(__file__).parent / "alembic.ini"
    if not alembic_ini.exists():
        print("ERROR: alembic.ini not found!")
        return False
    
    # Check if alembic directory exists
    alembic_dir = Path(__file__).parent / "alembic"
    if not alembic_dir.exists():
        print("ERROR: alembic directory not found!")
        return False
    
    # Check if env.py exists
    env_py = alembic_dir / "env.py"
    if not env_py.exists():
        print("ERROR: alembic/env.py not found!")
        return False
    
    print("SUCCESS: Alembic environment is valid!")
    return True

#define main function
def main():
    """
    Main function to handle the migration process
    """
    parser = argparse.ArgumentParser( # Parse command line arguments
        description="Automated Alembic Migration Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python migrate.py "add full_name column to users"
    python migrate.py "create cars table"
    python migrate.py "update user email field"
    
Options:
    --status-only    Only check migration status
    --history        Show migration history
    --no-generate    Skip migration generation, only apply
        """
    )
    
    parser.add_argument(
        "message",
        nargs="?",
        help="Migration message/description"
    )
    
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Only check migration status"
    )
    
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show migration history"
    )
    
    parser.add_argument(
        "--no-generate",
        action="store_true",
        help="Skip migration generation, only apply existing migrations"
    )
    
    args = parser.parse_args()
    
    print("ALEMBIC MIGRATION SCRIPT")
    print("=" * 50)
    
    # Validate environment first
    if not validate_environment():
        print("FATAL: Environment validation failed!")
        sys.exit(1)
    
    # Handle different modes
    if args.status_only:
        success = check_migration_status()
        sys.exit(0 if success else 1)
    
    if args.history:
        success = show_migration_history()
        sys.exit(0 if success else 1)
    
    # Check if message is provided when generating migration
    if not args.no_generate and not args.message:
        print("ERROR: Migration message is required!")
        print("Usage: python migrate.py \"your migration message\"")
        print("Or use --no-generate to skip migration generation")
        sys.exit(1)
    
    # Step 1: Check current status
    print("\n" + "="*50)
    print("CHECKING CURRENT STATUS")
    print("="*50)
    if not check_migration_status():
        print("WARNING: Could not check current status!")
    
    # Step 2: Generate migration (unless skipped)
    if not args.no_generate:
        if not generate_migration(args.message):
            print("FATAL: Failed to generate migration!")
            sys.exit(1)
    
    # Step 3: Apply migration
    if not apply_migration():
        print("FATAL: Failed to apply migration!")
        sys.exit(1)
    
    # Step 4: Final status check
    print("\n" + "="*50)
    print("FINAL STATUS CHECK")
    print("="*50)
    if not check_migration_status():
        print("WARNING: Could not check final status!")
    
    print("\n" + "="*50)
    print("MIGRATION COMPLETED SUCCESSFULLY!")
    print("="*50)

if __name__ == "__main__":
    main()
