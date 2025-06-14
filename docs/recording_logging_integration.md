"""
Integration Guide for Recording Service Logging

This file shows how the enhanced logging can be integrated into the Recording Service.
The integration can be done incrementally without affecting existing functionality.
"""

# Example Integration for the most important Recording Service methods:

"""
1. In the start_recording method:

from app.services.recording_logger import recording_activity_logger

async def start_recording(self, streamer_id: int, stream_data: Dict[str, Any]) -> bool:
    # Start session
    session_id = recording_activity_logger.start_recording_session(
        streamer_id, 
        streamer.username,
        {
            "quality": quality,
            "output_path": output_path,
            "stream_data": stream_data,
            "force_started": False
        }
    )
    
    try:
        # Existing code...
        
        # Log successful events
        recording_activity_logger.log_session_event(
            session_id, 
            "STREAMLINK_STARTED", 
            f"Quality: {quality}, Output: {output_path}"
        )
        
        return True
        
    except Exception as e:
        # Log errors
        recording_activity_logger.log_error_with_context(
            "START_FAILED",
            streamer.username,
            str(e),
            {"session_id": session_id, "streamer_id": streamer_id}
        )
        # End session
        recording_activity_logger.end_recording_session(session_id, "error")
        raise


2. In the stop_recording method:

async def stop_recording(self, streamer_id: int) -> bool:
    try:
        recording_info = self.active_recordings.pop(streamer_id)
        
        # Calculate duration
        duration = (datetime.now() - recording_info["started_at"]).total_seconds()
        
        # Log performance metrics
        recording_activity_logger.log_performance_metrics(
            "RECORDING_STOP",
            recording_info["streamer_name"],
            {
                "duration_seconds": duration,
                "output_file_size_mb": os.path.getsize(recording_info["output_path"]) / (1024*1024) if os.path.exists(recording_info["output_path"]) else 0,
                "reason": "manual_stop"
            }
        )
        
        # End session if available
        if "session_id" in recording_info:
            recording_activity_logger.end_recording_session(recording_info["session_id"], "manual_stop")


3. In the _monitor_process method:

async def _monitor_process(self, process, process_id, streamer_name, ts_path, mp4_path):
    # Log process monitoring
    recording_activity_logger.log_process_lifecycle(
        "STREAMLINK", 
        streamer_name, 
        "MONITORING", 
        {"process_id": process_id, "ts_path": ts_path}
    )
    
    try:
        stdout, stderr = await process.communicate()
        exit_code = process.returncode or 0
        
        # Detailed process metrics
        process_metrics = {
            "exit_code": exit_code,
            "stdout_length": len(stdout) if stdout else 0,
            "stderr_length": len(stderr) if stderr else 0,
            "ts_file_size_mb": os.path.getsize(ts_path) / (1024*1024) if os.path.exists(ts_path) else 0
        }
        
        recording_activity_logger.log_performance_metrics(
            "STREAMLINK_PROCESS",
            streamer_name,
            process_metrics
        )
        
        if exit_code == 0:
            # Log successful conversion
            recording_activity_logger.log_file_operation_detailed(
                "TS_RECORDING_COMPLETED",
                ts_path,
                True,
                {"exit_code": exit_code},
                process_metrics
            )


4. FFmpeg Remux Logging (simplified):

async def _remux_to_mp4_with_logging(self, ts_path: str, mp4_path: str, streamer_name: str) -> bool:
    start_time = time.time()
    
    try:
        # Existing FFmpeg code...
        success = await self._actual_remux_process(ts_path, mp4_path)
        
        # Performance metrics
        duration = time.time() - start_time
        input_size = os.path.getsize(ts_path) / (1024*1024) if os.path.exists(ts_path) else 0
        output_size = os.path.getsize(mp4_path) / (1024*1024) if os.path.exists(mp4_path) else 0
        
        performance_metrics = {
            "duration_seconds": duration,
            "input_size_mb": input_size,
            "output_size_mb": output_size,
            "compression_ratio": (input_size - output_size) / input_size if input_size > 0 else 0,
            "processing_speed_mbps": input_size / duration if duration > 0 else 0
        }
        
        recording_activity_logger.log_file_operation_detailed(
            "FFMPEG_REMUX",
            mp4_path,
            success,
            {"input_file": ts_path, "codec": "copy"},
            performance_metrics
        )
        
        # Log quality metrics (if available)
        if success and os.path.exists(mp4_path):
            # Video quality checks could be inserted here
            quality_metrics = {
                "file_size_mb": output_size,
                "duration_estimated": duration,
                "format": "mp4"
            }
            
            recording_activity_logger.log_quality_metrics(
                streamer_name,
                mp4_path,
                quality_metrics
            )
        
        return success
        
    except Exception as e:
        recording_activity_logger.log_error_with_context(
            "FFMPEG_REMUX_FAILED",
            streamer_name,
            str(e),
            {"ts_path": ts_path, "mp4_path": mp4_path}
        )
        return False


5. Log configuration changes:

def update_recording_settings(self, settings):
    # Remember old values
    old_settings = self.get_current_settings()
    
    # Set new values
    self.apply_settings(settings)
    
    # Log changes
    for key, new_value in settings.items():
        old_value = old_settings.get(key)
        if old_value != new_value:
            impact_analysis = self._analyze_setting_impact(key, old_value, new_value)
            recording_activity_logger.log_configuration_impact(
                key, 
                old_value, 
                new_value, 
                impact_analysis=impact_analysis
            )
"""

# Usage in routes (already implemented):
"""
The recording routes already use enhanced logging:
- All API calls are logged
- Success/error status is documented
- Configuration changes are tracked
"""

# Log structure examples:
EXAMPLE_LOGS = """
# Example log outputs:

[2025-06-14 15:30:25][INFO] [SESSION_START:123_20250614_153025] TestStreamer (ID: 123)
[2025-06-14 15:30:25][INFO] [SESSION_START:123_20250614_153025] Context: {
  "quality": "best",
  "output_path": "/recordings/TestStreamer/TestStreamer_2025-06-14_15-30_Stream.mp4",
  "stream_data": {"title": "Gaming Stream", "category_name": "Just Chatting"},
  "force_started": false
}

[2025-06-14 15:30:26][INFO] [STREAMLINK_STARTED:123_20250614_153025] TestStreamer - Quality: best, Output: /recordings/TestStreamer/TestStreamer_2025-06-14_15-30_Stream.mp4

[2025-06-14 15:30:27][INFO] [PROCESS_MONITORING] STREAMLINK for TestStreamer - {"process_id": "streamlink_123_1718370625", "ts_path": "/recordings/TestStreamer/TestStreamer_2025-06-14_15-30_Stream.ts"}

[2025-06-14 16:45:30][INFO] [FILE_OP_SUCCESS] TS_RECORDING_COMPLETED: /recordings/TestStreamer/TestStreamer_2025-06-14_15-30_Stream.ts (Size: 1024.50 MB) - Details: {"exit_code": 0} - Performance: {"exit_code": 0, "stdout_length": 2048, "stderr_length": 512, "ts_file_size_mb": 1024.5}

[2025-06-14 16:45:35][INFO] [FILE_OP_SUCCESS] FFMPEG_REMUX: /recordings/TestStreamer/TestStreamer_2025-06-14_15-30_Stream.mp4 (Size: 1020.25 MB) - Details: {"input_file": "/recordings/TestStreamer/TestStreamer_2025-06-14_15-30_Stream.ts", "codec": "copy"} - Performance: {"duration_seconds": 4.2, "input_size_mb": 1024.5, "output_size_mb": 1020.25, "compression_ratio": 0.004, "processing_speed_mbps": 243.93}

[2025-06-14 16:45:35][INFO] [QUALITY_METRICS] TestStreamer (/recordings/TestStreamer/TestStreamer_2025-06-14_15-30_Stream.mp4): {"file_size_mb": 1020.25, "duration_estimated": 4.2, "format": "mp4"}

[2025-06-14 16:45:36][INFO] [SESSION_END:123_20250614_153025] TestStreamer - Duration: 4506.0s, Reason: completed
"""
