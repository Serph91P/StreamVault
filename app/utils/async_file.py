"""
Async file operations utility functions.
Wraps blocking file operations in asyncio.to_thread for non-blocking execution.
"""
import asyncio
import os
import shutil
from pathlib import Path
from typing import Union, List


async def exists(path: Union[str, Path]) -> bool:
    """Check if file or directory exists asynchronously."""
    return await asyncio.to_thread(os.path.exists, str(path))


async def getsize(path: Union[str, Path]) -> int:
    """Get file size asynchronously."""
    return await asyncio.to_thread(os.path.getsize, str(path))


async def isfile(path: Union[str, Path]) -> bool:
    """Check if path is a file asynchronously."""
    return await asyncio.to_thread(os.path.isfile, str(path))


async def isdir(path: Union[str, Path]) -> bool:
    """Check if path is a directory asynchronously."""
    return await asyncio.to_thread(os.path.isdir, str(path))


async def mkdir(path: Union[str, Path], parents: bool = True, exist_ok: bool = True) -> None:
    """Create directory asynchronously."""
    def _mkdir():
        if isinstance(path, str):
            Path(path).mkdir(parents=parents, exist_ok=exist_ok)
        else:
            path.mkdir(parents=parents, exist_ok=exist_ok)

    await asyncio.to_thread(_mkdir)


async def makedirs(path: Union[str, Path], exist_ok: bool = True) -> None:
    """Create directories recursively asynchronously."""
    await asyncio.to_thread(os.makedirs, str(path), exist_ok=exist_ok)


async def remove(path: Union[str, Path]) -> None:
    """Remove file asynchronously."""
    await asyncio.to_thread(os.remove, str(path))


async def unlink(path: Union[str, Path]) -> None:
    """Remove file using pathlib unlink asynchronously."""
    def _unlink():
        if isinstance(path, str):
            Path(path).unlink()
        else:
            path.unlink()

    await asyncio.to_thread(_unlink)


async def rmdir(path: Union[str, Path]) -> None:
    """Remove directory asynchronously."""
    await asyncio.to_thread(os.rmdir, str(path))


async def listdir(path: Union[str, Path]) -> List[str]:
    """List directory contents asynchronously."""
    return await asyncio.to_thread(os.listdir, str(path))


async def copy2(src: Union[str, Path], dst: Union[str, Path]) -> None:
    """Copy file with metadata asynchronously."""
    await asyncio.to_thread(shutil.copy2, str(src), str(dst))


async def move(src: Union[str, Path], dst: Union[str, Path]) -> None:
    """Move file asynchronously."""
    await asyncio.to_thread(shutil.move, str(src), str(dst))


async def basename(path: Union[str, Path]) -> str:
    """Get basename asynchronously."""
    return await asyncio.to_thread(os.path.basename, str(path))


async def dirname(path: Union[str, Path]) -> str:
    """Get directory name asynchronously."""
    return await asyncio.to_thread(os.path.dirname, str(path))


async def splitext(path: Union[str, Path]) -> tuple:
    """Split extension asynchronously."""
    return await asyncio.to_thread(os.path.splitext, str(path))


async def join(*paths: Union[str, Path]) -> str:
    """Join paths asynchronously."""
    return await asyncio.to_thread(os.path.join, *[str(p) for p in paths])


async def abspath(path: Union[str, Path]) -> str:
    """Get absolute path asynchronously."""
    return await asyncio.to_thread(os.path.abspath, str(path))


async def normpath(path: Union[str, Path]) -> str:
    """Normalize path asynchronously."""
    return await asyncio.to_thread(os.path.normpath, str(path))


# Path object methods
async def path_exists(path: Path) -> bool:
    """Check if Path object exists asynchronously."""
    return await asyncio.to_thread(path.exists)


async def path_is_file(path: Path) -> bool:
    """Check if Path object is a file asynchronously."""
    return await asyncio.to_thread(path.is_file)


async def path_is_dir(path: Path) -> bool:
    """Check if Path object is a directory asynchronously."""
    return await asyncio.to_thread(path.is_dir)


async def path_stat(path: Path):
    """Get Path object stat asynchronously."""
    return await asyncio.to_thread(path.stat)


async def path_unlink(path: Path) -> None:
    """Remove Path object asynchronously."""
    await asyncio.to_thread(path.unlink)


async def path_mkdir(path: Path, parents: bool = True, exist_ok: bool = True) -> None:
    """Create directory from Path object asynchronously."""
    await asyncio.to_thread(path.mkdir, parents=parents, exist_ok=exist_ok)


async def glob_list(pattern: str) -> List[str]:
    """List files matching glob pattern asynchronously."""
    import glob
    return await asyncio.to_thread(glob.glob, pattern)


async def walk(path: Union[str, Path]):
    """Walk directory tree asynchronously."""
    return await asyncio.to_thread(list, os.walk(str(path)))
