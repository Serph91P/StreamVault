#!/usr/bin/env python
"""
Code Quality Check Script

This script runs the same checks as the GitHub Actions workflow
to ensure code quality before pushing changes.
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(command, description, continue_on_error=False):
    """Run a command and print its output"""
    print(f"\n=== {description} ===")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
        
    if result.returncode != 0:
        print(f"❌ {description} failed with exit code {result.returncode}")
        if not continue_on_error:
            sys.exit(result.returncode)
    else:
        print(f"✅ {description} succeeded")
        
    return result.returncode == 0

def main():
    """Run all code quality checks"""
    # Ensure we're in the project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    print("Running code quality checks...")
    
    # Import test
    run_command("python ci_import_test.py", "Import Test")
    
    # Flake8 syntax check
    run_command(
        "flake8 app migrations --count --select=E9,F63,F7,F82 --show-source --statistics", 
        "Critical Syntax Check"
    )
    
    # Flake8 undefined names
    run_command(
        "flake8 app migrations --count --select=F821,F822,E999,F401 --show-source --statistics",
        "Undefined Variables Check"
    )
    
    # isort check
    run_command(
        "isort app/. --check --diff --verbose",
        "Import Order Check",
        continue_on_error=True
    )
    
    # black check
    run_command(
        "black app --check --diff --verbose --line-length 120",
        "Code Formatting Check",
        continue_on_error=True
    )
    
    # mypy check (utils directory)
    run_command(
        "mypy --config-file mypy.ini app/utils/",
        "Type Check - Utils",
        continue_on_error=True
    )
    
    print("\n=== All checks completed ===")
    
if __name__ == "__main__":
    main()
