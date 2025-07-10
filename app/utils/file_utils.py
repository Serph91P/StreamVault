"""File utility functions for StreamVault."""
import os
import re
import asyncio
import logging
import tempfile
from datetime import datetime
from typing import Dict, Optional, Any

# Import MP4Box utilities
from .mp4box_utils import (
    embed_metadata_with_mp4box,
    optimize_mp4_with_mp4box,
    validate_mp4_with_mp4box
)

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
        
        # Validate input file exists and has content
        if not os.path.exists(input_path):
            logger.error(f"Input file {input_path} does not exist")
            return {
                "success": False,
                "code": -1,
                "stdout": "",
                "stderr": "Input file does not exist"
            }
            
        input_size = os.path.getsize(input_path)
        if input_size == 0:
            logger.error(f"Input file {input_path} is empty")
            return {
                "success": False,
                "code": -1,
                "stdout": "",
                "stderr": "Input file is empty"
            }
        
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
            
        # Build comprehensive ffmpeg command with robust error handling
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-i", metadata_file,
            "-map_metadata", "1",
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-movflags", "faststart",
            output_path
        ]
        
        # Overwrite if specified
        if overwrite or empty_file:
            cmd.append("-y")
        
        # Generate a unique timestamp for this operation with more precision
        remux_timestamp = int(datetime.now().timestamp())
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        operation_id = f"remux_{streamer_name}_{timestamp_str}"
        
        # Make sure we have a valid streamer name
        if not streamer_name or streamer_name.lower() == "none":
            # Try to extract streamer name from input path
            input_filename = os.path.basename(input_path)
            name_parts = os.path.splitext(input_filename)[0].split('-')
            if name_parts:
                streamer_name = name_parts[0]
            else:
                streamer_name = "unknown"
        
        # Set up logging if the service is available
        ffmpeg_log_path = None
        
        # Add stats period for reporting
        cmd.extend(["-stats_period", "30"]) # Show stats every 30 seconds
        
        # Add output path
        cmd.append(output_path)
        if logging_service:
            # Create a unique log file for each remux operation with timestamp and streamer name
            log_prefix = "metadata" if metadata_file else "remux"
            ffmpeg_log_path = logging_service.get_ffmpeg_log_path(f"{log_prefix}_{timestamp_str}", streamer_name)
            
            # Configure logging level based on whether we have a log file
            if ffmpeg_log_path:
                # Silent in the container, everything goes to log files
                cmd.extend(["-loglevel", "quiet"])
            else:
                # If no log file, use info level for debugging
                cmd.extend(["-loglevel", "info"])
            
            # Log the command in different formats for better traceability
            logging_service.ffmpeg_logger.info(f"[FFMPEG_{log_prefix.upper()}_START] {streamer_name} - {input_path} -> {output_path}")
            logging_service.ffmpeg_logger.info(f"[FFMPEG_CMD] {streamer_name} - {' '.join(cmd)}")
            # The log_ffmpeg_start will return a log path, but we already have one
            logging_service.log_ffmpeg_start(f"{log_prefix}", cmd, streamer_name)
            
            operation_type = "METADATA_EMBED_START" if metadata_file else "REMUX_START"
            logging_service.log_file_operation(operation_type, input_path, True, 
                                             f"Starting {log_prefix} to {output_path} (Input size: {os.path.getsize(input_path)/1024/1024:.2f} MB)")
            
            # Log input file size and details
            if os.path.exists(input_path):
                input_size = os.path.getsize(input_path)
                logging_service.ffmpeg_logger.info(f"Input file: {input_path}, size: {input_size} bytes ({input_size/1024/1024:.2f} MB)")
        else:
            # No logging service, use info level for direct output
            cmd.extend(["-loglevel", "info"])
        
        logger.info(f"Starting FFmpeg {log_prefix if 'log_prefix' in locals() else 'remux'}: {operation_id}")
        logger.debug(f"Command: {' '.join(cmd)}")
        
        # Set environment variable for FFmpeg report - ensure the directory exists
        env = os.environ.copy()
        if ffmpeg_log_path:
            # Ensure the directory exists
            log_dir = os.path.dirname(ffmpeg_log_path)
            os.makedirs(log_dir, exist_ok=True)
            
            # Configure FFmpeg to create a detailed report - ensure higher log level and no console output
            # Remove 'append' parameter which causes warnings and ensure file path is properly formatted
            env["FFREPORT"] = f"file={ffmpeg_log_path}:level=40"
            
            # Add specific environment variables to redirect logs to file only
            env["AV_LOG_FORCE_NOCOLOR"] = "1"  # Disable ANSI color in logs
            env["AV_LOG_FORCE_STDERR"] = "0"   # Don't force stderr output
            
            logger.info(f"FFmpeg log will be written to: {ffmpeg_log_path}")
        
        # Create temporary files for stdout and stderr if needed to avoid logs in container
        stdout_file = None
        stderr_file = None
        if ffmpeg_log_path:
            # Create temporary files to capture stdout/stderr
            stdout_file = tempfile.NamedTemporaryFile(delete=False, prefix="ffmpeg_stdout_", suffix=".log")
            stderr_file = tempfile.NamedTemporaryFile(delete=False, prefix="ffmpeg_stderr_", suffix=".log")
            stdout_fd = stdout_file.fileno()
            stderr_fd = stderr_file.fileno()
            
            # Start the process with redirected output
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=stdout_fd,
                stderr=stderr_fd,
                env=env
            )
            
            # Close our file handles (subprocess still has them open)
            stdout_file.close()
            stderr_file.close()
        else:
            # Start the process with piped output if no log file is specified
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
        
        # Use a timeout to avoid hanging forever
        try:
            if stdout_file and stderr_file:
                # When using files, we still need to wait for the process to complete
                exit_code = await asyncio.wait_for(process.wait(), timeout=7200)  # 2 hours timeout
                
                # Read output from the temporary files
                with open(stdout_file.name, 'r', errors='ignore') as f:
                    stdout_str = f.read()
                with open(stderr_file.name, 'r', errors='ignore') as f:
                    stderr_str = f.read()
                    
                # Append the output to the FFmpeg log file
                if ffmpeg_log_path:
                    with open(ffmpeg_log_path, 'a', errors='ignore') as f:
                        f.write("\n\n--- STDOUT ---\n")
                        f.write(stdout_str)
                        f.write("\n\n--- STDERR ---\n")
                        f.write(stderr_str)
                        
                # Clean up temporary files
                try:
                    os.unlink(stdout_file.name)
                    os.unlink(stderr_file.name)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary stdout/stderr files: {e}")
            else:
                # Original method for piped output
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=7200)  # 2 hours timeout
                stdout_str = stdout.decode('utf-8', errors='ignore') if stdout else ""
                stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
                
            exit_code = process.returncode or 0
        except asyncio.TimeoutError:
            logger.error(f"FFmpeg remux timed out after 2 hours: {input_path} to {output_path}")
            if process:
                try:
                    process.kill()
                except:
                    pass
                    
            # Clean up temp files if they exist
            if stdout_file and os.path.exists(stdout_file.name):
                try:
                    os.unlink(stdout_file.name)
                except Exception:
                    pass
            if stderr_file and os.path.exists(stderr_file.name):
                try:
                    os.unlink(stderr_file.name)
                except Exception:
                    pass
                    
            stdout_str = ""
            stderr_str = "Process timed out after 2 hours"
            exit_code = -1
        
        # Log the process output if logging service available
        if logging_service:
            log_prefix = "metadata" if metadata_file else "remux"
            # Use the updated method that ensures streamer name is included
            logging_service.log_ffmpeg_output(f"{log_prefix}", stdout_str, stderr_str, exit_code, streamer_name)
        
        # Basic success check
        basic_success = exit_code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
        # Additional validation if success
        if basic_success:
            output_size = os.path.getsize(output_path)
            input_size = os.path.getsize(input_path) if os.path.exists(input_path) else 0
            
            # Log file sizes
            if logging_service:
                log_prefix = "Metadata embedding" if metadata_file else "Remux"
                logging_service.ffmpeg_logger.info(
                    f"{log_prefix} complete - Input: {input_size/1024/1024:.2f} MB, Output: {output_size/1024/1024:.2f} MB"
                )
            
            # Calculate ratio for reasonable size check
            size_ratio = output_size / input_size if input_size > 0 else 1
            
            if output_size < 1024 * 1024:  # Less than 1MB
                logger.error(f"Output file is too small: {output_size} bytes")
                if logging_service:
                    operation_type = "METADATA_EMBED_FAILED" if metadata_file else "REMUX_FAILED"
                    logging_service.log_file_operation(
                        operation_type, output_path, False, f"Output file too small: {output_size} bytes"
                    )
                basic_success = False
            elif input_size > 0 and size_ratio < 0.8:
                logger.warning(
                    f"Output file size ({output_size}) is significantly smaller than input ({input_size}), ratio: {size_ratio:.2f}"
                )
                if logging_service:
                    logging_service.ffmpeg_logger.warning(
                        f"Size ratio warning: {size_ratio:.2f} (input: {input_size}, output: {output_size})"
                    )
            
            # Check if ffmpeg produced warnings about audio/video sync
            if stderr_str and ("Non-monotonous DTS" in stderr_str or "Invalid timestamp" in stderr_str):
                logger.warning(f"FFmpeg reported timestamp issues: {stderr_str[:200]}...")
                if logging_service:
                    logging_service.ffmpeg_logger.warning(f"Timestamp issues detected: check the log file for details")
        
        if basic_success:
            log_prefix = "metadata embedding" if metadata_file else "remux"
            logger.info(f"Successfully completed {log_prefix} {input_path} to {output_path}")
            if logging_service:
                operation_type = "METADATA_EMBED_SUCCESS" if metadata_file else "REMUX_SUCCESS"
                logging_service.log_file_operation(
                    operation_type, 
                    output_path, 
                    True, 
                    f"Operation from {input_path}, output size: {os.path.getsize(output_path)/1024/1024:.2f} MB"
                )
        else:
            log_prefix = "metadata embedding" if metadata_file else "remux"
            error_message = f"Failed to complete {log_prefix} {input_path} to {output_path}: Exit code {exit_code}"
            logger.error(error_message)
            
            # Log more detailed error information
            if stderr_str:
                # Extract the most relevant error messages (last few lines)
                error_lines = stderr_str.splitlines()
                relevant_errors = error_lines[-10:] if len(error_lines) > 10 else error_lines
                error_summary = "\n".join(relevant_errors)
                logger.error(f"FFmpeg error details: {error_summary}")
            
            if logging_service:
                operation_type = "METADATA_EMBED_FAILED" if metadata_file else "REMUX_FAILED"
                logging_service.log_file_operation(operation_type, output_path, False, error_message)
        
        # Set the success flag for return value
        success = basic_success
        
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

async def embed_metadata_with_mp4box_wrapper(
    input_path: str,
    output_path: str, 
    metadata: Dict[str, Any],
    chapters: Optional[list] = None,
    streamer_name: str = "unknown",
    logging_service=None
) -> Dict[str, Any]:
    """
    Embed metadata into MP4 file using MP4Box instead of FFmpeg.
    This is more efficient and reliable for MP4 metadata operations.
    
    Args:
        input_path: Path to the input MP4 file
        output_path: Path to the output MP4 file
        metadata: Dictionary with metadata to embed
        chapters: Optional list of chapter information
        streamer_name: Name of the streamer for logging purposes
        logging_service: Optional logging service for more detailed logging
        
    Returns:
        Dict containing success status and details
    """
    operation_id = None
    try:
        logger.info(f"Starting MP4Box metadata embedding for {streamer_name}: {input_path} -> {output_path}")
        
        # Validate input file exists and has content
        if not os.path.exists(input_path):
            logger.error(f"Input file {input_path} does not exist")
            return {
                "success": False,
                "code": -1,
                "stdout": "",
                "stderr": "Input file does not exist"
            }
            
        input_size = os.path.getsize(input_path)
        if input_size == 0:
            logger.error(f"Input file {input_path} is empty")
            return {
                "success": False,
                "code": -1,
                "stdout": "",
                "stderr": "Input file is empty"
            }
        
        # Check if output file already exists
        if os.path.exists(output_path):
            if os.path.getsize(output_path) == 0:
                try:
                    os.remove(output_path)
                    logger.debug(f"Removed empty output file: {output_path}")
                except Exception as remove_e:
                    logger.warning(f"Could not remove empty output file: {remove_e}")
            else:
                logger.error(f"Output file {output_path} already exists and is not empty")
                return {
                    "success": False,
                    "code": -1,
                    "stdout": "",
                    "stderr": "Output file already exists"
                }
        
        # Generate operation ID for logging
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        operation_id = f"mp4box_metadata_{streamer_name}_{timestamp_str}"
        
        # Log the operation start
        if logging_service:
            logging_service.ffmpeg_logger.info(f"[MP4BOX_METADATA_START] {streamer_name} - {input_path} -> {output_path}")
        
        # Use MP4Box for metadata embedding with improved error handling
        success = await embed_metadata_with_mp4box(
            input_path, 
            output_path, 
            metadata, 
            chapters
        )
        
        if success:
            # Validate the output file
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                # Perform basic size check
                output_size = os.path.getsize(output_path)
                size_ratio = output_size / input_size if input_size > 0 else 0
                
                if size_ratio < 0.8:  # Output is significantly smaller than input
                    logger.warning(f"Output file size seems small (ratio: {size_ratio:.2f}), but continuing since MP4Box succeeded")
                
                # Additional validation with MP4Box (but don't fail if this fails)
                try:
                    is_valid = await validate_mp4_with_mp4box(output_path)
                    if not is_valid:
                        logger.warning(f"MP4Box validation failed, but file exists and has content: {output_path}")
                        # Don't fail - just log the warning
                except Exception as validation_e:
                    logger.warning(f"Could not perform MP4Box validation: {validation_e}")
                    # Continue anyway
                
                logger.info(f"MP4Box metadata embedding successful: {operation_id}")
                if logging_service:
                    logging_service.ffmpeg_logger.info(f"[MP4BOX_METADATA_SUCCESS] {streamer_name} - {output_path}")
                
                return {
                    "success": True,
                    "code": 0,
                    "stdout": f"Successfully embedded metadata using MP4Box",
                    "stderr": ""
                }
            else:
                logger.error(f"MP4Box metadata embedding failed - no valid output file: {operation_id}")
                return {
                    "success": False,
                    "code": 1,
                    "stdout": "",
                    "stderr": "No valid output file generated"
                }
        else:
            logger.warning(f"MP4Box metadata embedding failed: {operation_id}")
            if logging_service:
                logging_service.ffmpeg_logger.error(f"[MP4BOX_METADATA_FAILED] {streamer_name} - {input_path}")
            
            # Check if at least we have a partial output file
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"MP4Box failed but output file exists, checking if it's usable")
                try:
                    # Try basic validation
                    is_valid = await validate_mp4_with_mp4box(output_path)
                    if is_valid:
                        logger.info(f"Output file is valid despite MP4Box reporting failure - considering success")
                        return {
                            "success": True,
                            "code": 0,
                            "stdout": "MP4Box reported failure but output is valid",
                            "stderr": "MP4Box operation had issues but result is usable"
                        }
                except Exception as validation_e:
                    logger.debug(f"Failed to validate partial output: {validation_e}")
            
            return {
                "success": False,
                "code": 1,
                "stdout": "",
                "stderr": "MP4Box metadata embedding failed"
            }
            
    except Exception as e:
        logger.error(f"Error during MP4Box metadata embedding: {e}", exc_info=True)
        return {
            "success": False,
            "code": -1,
            "stdout": "",
            "stderr": str(e)
        }
