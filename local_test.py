#!/usr/bin/env python
"""
Local test script for StreamVault

This script runs simple tests to ensure the code works
without having to do a full Docker build, and includes type checking.
"""

import os
import sys
import importlib
import logging
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("local_test")

# Suppress SQLAlchemy warnings
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)

# Set up temporary test environment
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TESTING"] = "true"

# Create temporary directory for logs
temp_logs_dir = Path("./temp_logs")
temp_logs_dir.mkdir(exist_ok=True)
for subdir in ["streamlink", "ffmpeg", "app"]:
    (temp_logs_dir / subdir).mkdir(exist_ok=True)

os.environ["LOGS_DIR"] = str(temp_logs_dir)

def test_imports() -> List[Tuple[str, str]]:
    """Test if modules can be imported correctly"""
    modules_to_test = [
        'app.database',
        'app.models',
        'app.config.settings',
        'app.config.logging_config',
        'app.utils.path_utils',
        'app.utils.file_utils',
        'app.utils.ffmpeg_utils',
        'app.utils.streamlink_utils',
        'app.services.logging_service',
        'app.services.recording_service',
        'app.services.metadata_service',
    ]
    
    failed = []
    for module_name in modules_to_test:
        try:
            logger.info(f"Testing import of {module_name}")
            importlib.import_module(module_name)
            logger.info(f"✅ {module_name} successfully imported")
        except Exception as e:
            logger.error(f"❌ {module_name} could not be imported: {str(e)}")
            failed.append((module_name, str(e)))
    
    return failed

def run_basic_syntax_check() -> List[Tuple[str, str]]:
    """Basic syntax check with Python's compile"""
    python_files = []
    for root, _, files in os.walk("app"):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    
    failed = []
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            compile(source, file_path, 'exec')
            logger.info(f"✅ {file_path} - Syntax check passed")
        except SyntaxError as e:
            logger.error(f"❌ {file_path} - Syntax error: {str(e)}")
            failed.append((file_path, str(e)))
    
    return failed

def run_mypy_check() -> List[Tuple[str, str]]:
    """Run mypy type checking"""
    try:
        # Check if mypy is installed
        subprocess.run(["mypy", "--version"], check=True, capture_output=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("⚠️ mypy is not installed, skipping type checks")
        return []

    logger.info("Running mypy type checking...")
    
    # Start with utils directory which should have clean types
    directories = [
        "app/utils",
        "app/services",
        "app/config"
    ]
    
    failed = []
    for directory in directories:
        cmd = [
            "mypy",
            "--ignore-missing-imports",
            "--disallow-untyped-defs",
            "--disallow-incomplete-defs",
            "--check-untyped-defs",
            "--no-implicit-optional",
            "--warn-redundant-casts",
            "--warn-unused-ignores",
            directory
        ]
        
        try:
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                logger.error(f"❌ Type check failed for {directory}")
                errors = process.stdout.strip().split("\n")
                for error in errors:
                    logger.error(f"  {error}")
                    if error and not error.isspace():  # Only add non-empty lines
                        failed.append((directory, error))
            else:
                logger.info(f"✅ {directory} - Type check passed")
        except Exception as e:
            logger.error(f"❌ Error running mypy for {directory}: {str(e)}")
            failed.append((directory, str(e)))
    
    return failed

def check_sqlalchemy_attribute_access() -> List[Tuple[str, str]]:
    """Check for common SQLAlchemy model attribute access errors"""
    logger.info("Checking for SQLAlchemy model attribute access patterns...")
    
    # Common patterns that cause mypy errors
    patterns = [
        r"model\.[A-Za-z_]+\.id",
        r"model\.[A-Za-z_]+\.column",
        r"model\.[A-Za-z_]+\s*=\s*value",
        r"getattr\(model, attr\)"
    ]
    
    issues = []
    
    # Use grep to find these patterns
    try:
        for pattern in patterns:
            cmd = ["grep", "-r", "-E", pattern, "--include=*.py", "app/"]
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.stdout:
                for line in process.stdout.strip().split("\n"):
                    if line:
                        file_path, match = line.split(':', 1)
                        issues.append((file_path, f"Potential SQLAlchemy attribute issue: {match.strip()}"))
    except:
        # If grep fails (e.g., on Windows), skip this check
        logger.warning("⚠️ Could not run grep search for SQLAlchemy patterns")
    
    return issues

if __name__ == "__main__":
    logger.info("Starting local tests for StreamVault...")
    
    # Import tests
    import_failures = test_imports()
    
    # Syntax checks
    syntax_failures = run_basic_syntax_check()
    
    # Type checks with mypy
    type_failures = run_mypy_check()
    
    # SQLAlchemy attribute access checks
    sqlalchemy_issues = check_sqlalchemy_attribute_access()
    
    # Results
    has_failures = False
    
    if import_failures:
        has_failures = True
        logger.error("❌ Import errors:")
        for module, error in import_failures:
            logger.error(f"  - {module}: {error}")
    
    if syntax_failures:
        has_failures = True
        logger.error("❌ Syntax errors:")
        for file_path, error in syntax_failures:
            logger.error(f"  - {file_path}: {error}")
    
    if type_failures:
        has_failures = True
        logger.error("❌ Type errors:")
        for path, error in type_failures:
            logger.error(f"  - {error}")
    
    if sqlalchemy_issues:
        logger.warning("⚠️ Potential SQLAlchemy attribute access issues:")
        for file_path, issue in sqlalchemy_issues:
            logger.warning(f"  - {file_path}: {issue}")
    
    if has_failures:
        logger.error("❌ Tests failed!")
        sys.exit(1)
    else:
        logger.info("✅ All tests passed!")
        sys.exit(0)
