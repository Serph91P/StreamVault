"""
Process management for recording service.

This module handles subprocess creation and management.
"""
import logging
import asyncio
from typing import Dict, Optional, List

logger = logging.getLogger("streamvault")

class ProcessManager:
    """Manages subprocess execution and cleanup"""

    def __init__(self):
        self.active_processes = {}
        self.lock = asyncio.Lock()

    async def start_process(
        self, cmd: List[str], process_id: str
    ) -> Optional[asyncio.subprocess.Process]:
        """Start a subprocess and track it"""
        async with self.lock:
            try:
                process = await asyncio.create_subprocess_exec(*cmd)
                self.active_processes[process_id] = process
                logger.info(f"Started process {process_id} with PID {process.pid}")
                return process
            except Exception as e:
                logger.error(f"Failed to start process {process_id}: {e}")
                return None

    async def terminate_process(self, process_id: str, timeout: int = 10) -> bool:
        """Gracefully terminate a process"""
        async with self.lock:
            if process_id not in self.active_processes:
                return False

            process = self.active_processes.pop(process_id)
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=timeout)
                logger.info(f"Process {process_id} terminated gracefully")
                return True
            except asyncio.TimeoutError:
                process.kill()
                logger.warning(f"Process {process_id} killed after timeout")
                return True
            except Exception as e:
                logger.error(f"Failed to terminate process {process_id}: {e}")
                return False

    async def cleanup_all(self):
        """Terminate all active processes"""
        process_ids = list(self.active_processes.keys())
        for process_id in process_ids:
            await self.terminate_process(process_id)
