"""Target-local remux scratch; released queue locks are the only cleanup proof."""

from itertools import islice
from pathlib import Path
from uuid import UUID, uuid4


def _uuid(value):
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def prepare_remux_stage(output, owner):
    root = Path(output).parent / f".{Path(output).name}.processing"
    if root.is_symlink():
        raise OSError("Remux scratch root must not be a symlink")
    root.mkdir(mode=0o700, exist_ok=True)
    # Bounded, target-local cleanup, never a global scan or expiry-based steal.
    for directory in islice(root.iterdir(), 32):
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or not _uuid(directory.name)
        ):
            continue
        if directory.name == owner.token:
            continue
        with owner.dead_owner(directory.name) as dead:
            if not dead:
                continue
            for file in islice(directory.iterdir(), 32):
                if file.suffix in {".mp4", ".ffmeta"} and _uuid(file.stem):
                    file.unlink(missing_ok=True)
            try:
                directory.rmdir()
            except OSError:
                pass  # Unknown files or a bounded remainder stay untouched.
    directory = root / owner.token
    if directory.is_symlink():
        raise OSError("Remux owner scratch must not be a symlink")
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / f"{uuid4()}.mp4"
    with path.open("xb"):
        pass
    return str(path)
