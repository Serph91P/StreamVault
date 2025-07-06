"""File utility functions for StreamVault."""
import os
import re
import asyncio
import logging
import tempfile
from typing import Dict, Optional, Any

logger = logging.getLogger("streamvault")

async def remux_file(
    input_path: str, 
    output_path: str, 
    overwrite: bool = False, 
    metadata_file: Optional[str] = None, 
    streamer_name: str = "unknown",
    logging_service=None
) -> Dict[str, Any]:
    """
    Remux an input file to an output file without repair attempts.
    Similar to the TypeScript implementation, this method will not attempt repairs if remuxing fails.
    
    Args:
        input_path: Path to the input file
        output_path: Path to the output file
        overwrite: Whether to overwrite the output file if it exists
        metadata_file: Optional path to a metadata file to embed
        streamer_name: Name of the streamer for logging purposes
        logging_service: Optional logging service for more detailed logging
        
    Returns:
        Dict containing success status, return code, stdout, and stderr
    """
    try:
        # Import here to avoid circular imports
        from app.config.settings import settings
        
        logger.info(f"Starting remux of {input_path} to {output_path}")
        
        # Check if output file already exists
        empty_file = os.path.exists(output_path) and os.path.getsize(output_path) == 0
        
        if not overwrite and os.path.exists(output_path) and not empty_file:
            logger.error(f"Output file {output_path} already exists")
            return {
                "success": False,
                "code": -1,
                "stdout": "",
                "stderr": "Output file already exists"
            }
        
        if empty_file:
            os.remove(output_path)
            
        # Build ffmpeg command similar to the TypeScript implementation
        cmd = ["ffmpeg"]
        
        # Input file
        cmd.extend(["-i", input_path])
        
        # Add metadata file if provided
        if metadata_file and os.path.exists(metadata_file):
            cmd.extend(["-i", metadata_file, "-map_metadata", "1"])
        elif metadata_file:
            logger.warning(f"Metadata file {metadata_file} does not exist for remuxing {input_path}")
        
        # Copy streams without re-encoding
        cmd.extend(["-c", "copy"])
        
        # Add aac bitstream filter for non-audio containers
        if not output_path.endswith('.aac'):
            cmd.extend(["-bsf:a", "aac_adtstoasc"])
        
        # Optimize for mp4 files
        if output_path.endswith('.mp4'):
            cmd.extend(["-movflags", "faststart"])
        
        # Overwrite if specified
        if overwrite or empty_file:
            cmd.append("-y")
        
        # Add verbose logging if needed
        if hasattr(settings, 'verbose_logging') and settings.verbose_logging:
            cmd.extend(["-loglevel", "repeat+level+verbose"])
        
        # Add output path
        cmd.append(output_path)
        
        # Set up logging if the service is available
        ffmpeg_log_path = None
        if logging_service:
            ffmpeg_log_path = logging_service.get_ffmpeg_log_path("remux", streamer_name)
            logging_service.log_ffmpeg_start("remux", cmd, streamer_name)
            logging_service.log_file_operation("REMUX_START", input_path, True, f"Starting remux to {output_path}")
        
        logger.debug(f"Starting FFmpeg remux: {' '.join(cmd)}")
        
        # Set environment variable for FFmpeg report
        env = os.environ.copy()
        if ffmpeg_log_path:
            env["FFREPORT"] = f"file={ffmpeg_log_path}:level=32"
        
        # Start the process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await process.communicate()
        stdout_str = stdout.decode('utf-8', errors='ignore') if stdout else ""
        stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
        exit_code = process.returncode or 0
        
        # Log the process output if logging service available
        if logging_service:
            logging_service.log_ffmpeg_output("remux", stdout, stderr, exit_code, streamer_name)
        
        success = exit_code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
        if success:
            logger.info(f"Successfully remuxed {input_path} to {output_path}")
            if logging_service:
                logging_service.log_file_operation("REMUX_SUCCESS", output_path, True, f"Remuxed from {input_path}")
        else:
            error_message = f"Failed to remux {input_path} to {output_path}: Exit code {exit_code}"
            logger.error(error_message)
            if logging_service:
                logging_service.log_file_operation("REMUX_FAILED", output_path, False, error_message)
        
        return {
            "success": success,
            "code": exit_code,
            "stdout": stdout_str,
            "stderr": stderr_str
        }
            
    except Exception as e:
        logger.error(f"Error during remux: {e}", exc_info=True)
        return {
            "success": False,
            "code": -1,
            "stdout": "",
            "stderr": str(e)
        }

def sanitize_filename(name: str) -> str:
    """
    Remove illegal characters from filename.
    
    Args:
        name: The filename to sanitize
        
    Returns:
        A sanitized filename without illegal characters
    """
    if not name:
        return "unknown"
        
    # Replace problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", name)
    
    # Remove multiple spaces and trim
    sanitized = ' '.join(sanitized.split())
    
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:97] + "..."
    
    return sanitized or "unknown"

async def cleanup_temporary_files(mp4_path: str):
    """
    Clean up temporary files after successful metadata generation.
    
    Args:
        mp4_path: Path to the MP4 file
    """
    try:
        base_path = mp4_path.replace(".mp4", "")
        temp_extensions = [".ts", ".h264", ".aac", ".temp", ".processing"]
        
        cleaned_files = []
        for ext in temp_extensions:
            temp_file = base_path + ext
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    cleaned_files.append(temp_file)
                    logger.debug(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
        
        if cleaned_files:
            logger.info(f"Cleaned up {len(cleaned_files)} temporary files for {os.path.basename(mp4_path)}")
        else:
            logger.debug(f"No temporary files to clean up for {os.path.basename(mp4_path)}")
            
    except Exception as e:
        logger.error(f"Error cleaning up temporary files: {e}", exc_info=True)
