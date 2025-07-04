#!/usr/bin/env python
"""
Lokales Testskript für StreamVault

Dieses Skript führt einfache Tests durch, um sicherzustellen, dass der Code funktioniert,
ohne einen vollständigen Docker-Build durchführen zu müssen.
"""

import os
import sys
import importlib
import logging
from pathlib import Path

# Logging einrichten
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("local_test")

# SQLAlchemy-Warnungen unterdrücken
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)

# Temporäre Testumgebung einrichten
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TESTING"] = "true"

# Temporäres Verzeichnis für Logs erstellen
temp_logs_dir = Path("./temp_logs")
temp_logs_dir.mkdir(exist_ok=True)
for subdir in ["streamlink", "ffmpeg", "app"]:
    (temp_logs_dir / subdir).mkdir(exist_ok=True)

os.environ["LOGS_DIR"] = str(temp_logs_dir)

def test_imports():
    """Testen ob Module korrekt importiert werden können"""
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
            logger.info(f"Teste Import von {module_name}")
            importlib.import_module(module_name)
            logger.info(f"✅ {module_name} erfolgreich importiert")
        except Exception as e:
            logger.error(f"❌ {module_name} konnte nicht importiert werden: {str(e)}")
            failed.append((module_name, str(e)))
    
    return failed

def run_basic_syntax_check():
    """Grundlegende Syntax-Prüfung mit Python's compile"""
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
            logger.info(f"✅ {file_path} - Syntaxprüfung bestanden")
        except SyntaxError as e:
            logger.error(f"❌ {file_path} - Syntaxfehler: {str(e)}")
            failed.append((file_path, str(e)))
    
    return failed

if __name__ == "__main__":
    logger.info("Starte lokale Tests für StreamVault...")
    
    # Import-Tests
    import_failures = test_imports()
    
    # Syntax-Checks
    syntax_failures = run_basic_syntax_check()
    
    # Ergebnisse
    if import_failures or syntax_failures:
        logger.error("❌ Tests fehlgeschlagen:")
        
        if import_failures:
            logger.error("Import-Fehler:")
            for module, error in import_failures:
                logger.error(f"  - {module}: {error}")
        
        if syntax_failures:
            logger.error("Syntax-Fehler:")
            for file_path, error in syntax_failures:
                logger.error(f"  - {file_path}: {error}")
        
        sys.exit(1)
    else:
        logger.info("✅ Alle Tests bestanden!")
        sys.exit(0)
