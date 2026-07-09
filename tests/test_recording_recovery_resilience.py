from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_state_persistence_process_exists_has_os_fallback() -> None:
    source = (ROOT / "app/services/core/state_persistence_service.py").read_text(
        encoding="utf-8"
    )

    assert "if not pid or pid <= 0:" in source
    assert "os.kill(pid, 0)" in source
    assert "except ProcessLookupError:" in source
    assert "except PermissionError:" in source


def test_startup_recovery_defers_when_live_status_cannot_be_verified() -> None:
    source = (ROOT / "app/services/init/startup_init.py").read_text(encoding="utf-8")

    api_error_block = source.split("except Exception as api_error:", 1)[1]
    api_error_block = api_error_block.split("if is_still_live:", 1)[0]

    assert "Deferring zombie recording cleanup" in api_error_block
    assert "continue" in api_error_block
    assert "is_still_live = False" not in api_error_block


def test_process_manager_psutil_flag_reflects_import_result() -> None:
    source = (ROOT / "app/services/recording/process_manager.py").read_text(
        encoding="utf-8"
    )

    assert "import psutil" in source
    assert "HAS_PSUTIL = True" in source
    assert "HAS_PSUTIL = False" in source
    assert "self.psutil_available = HAS_PSUTIL" in source
