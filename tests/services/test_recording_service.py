import asyncio
import os
# Set a test database URL before other app imports
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
# Ensure other potentially needed settings are also set to avoid import errors from app.config.settings
os.environ["OUTPUT_DIRECTORY"] = "/tmp/sv_tests_output" # Dummy output dir
os.environ["STREAMLINK_PATH"] = "streamlink" # Dummy streamlink path
os.environ["FFMPEG_PATH"] = "ffmpeg" # Dummy ffmpeg path
os.environ["DEFAULT_QUALITY"] = "best"

import unittest
from unittest.mock import patch, AsyncMock
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy.orm import Session
# Now import app modules after setting env vars
from app.database import SessionLocal, Base, engine
from app.models import Stream, Streamer
from app.services.recording.recording_service import RecordingService
import os
import tempfile
import shutil

# Ensure the test database is clean before running tests

class TestRecordingServiceDelayedMetadata(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create all tables in the in-memory SQLite database
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        # Drop all tables after tests are done
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        self.db: Session = SessionLocal()
        # Ensure RecordingService uses a fresh ConfigManager for each test
        # to pick up any environment variable changes if they were test-specific.
        self.recording_service = RecordingService(config_manager=None, metadata_service=None, subprocess_manager=None)

        # Create dummy streamer
        self.test_streamer = Streamer(
            username="test_streamer",
            twitch_id="12345",
            # display_name="TestStreamer", # This field does not exist on the model
            is_live=False
        )
        self.db.add(self.test_streamer)
        self.db.commit()
        self.db.refresh(self.test_streamer)

        # Create dummy stream
        self.test_stream = Stream(
            streamer_id=self.test_streamer.id,
            twitch_stream_id="fake_twitch_stream_id",
            title="Test Stream Title",
            started_at=datetime.now(timezone.utc),
            # recording_path initially None
        )
        self.db.add(self.test_stream)
        self.db.commit()
        self.db.refresh(self.test_stream)

        self.stream_id = self.test_stream.id
        # Ensure the mock path is unique per test run if tests run in parallel (though not currently)
        self.mock_mp4_path = f"/tmp/test_video_{self.stream_id}_{os.getpid()}.mp4"

        # Create a dummy mp4 file
        Path(self.mock_mp4_path).touch()
        # Also ensure the directory for the dummy file exists, if it implies a path
        os.makedirs(os.path.dirname(self.mock_mp4_path), exist_ok=True)


    def tearDown(self):
        # Clean up dummy mp4 file
        if os.path.exists(self.mock_mp4_path):
            os.remove(self.mock_mp4_path)

        # Clean up database records by deleting them
        # It's often better to clear all data or use transactions and rollback for tests,
        # but explicit delete is also fine for simple cases.
        # For in-memory DB, tables are dropped in tearDownClass, so individual deletes might be redundant
        # if each test method gets a fresh DB state. However, SessionLocal might carry state.
        # Let's try to be more explicit with cleanup or ensure test isolation.

        # Rolling back the session can discard pending changes and help isolate tests
        try:
            self.db.rollback() # Rollback any uncommitted changes
            # Query and delete to ensure objects are detached from the session before closing
            stream = self.db.get(Stream, self.stream_id)
            if stream:
                self.db.delete(stream)
            streamer = self.db.get(Streamer, self.test_streamer.id)
            if streamer:
                self.db.delete(streamer)
            self.db.commit()
        except Exception as e:
            # Log error during cleanup if necessary
            print(f"Error during DB cleanup: {e}")
        finally:
            self.db.close()

        # Invalidate cache for config manager to avoid interference between tests
        if hasattr(self.recording_service, 'config_manager') and self.recording_service.config_manager:
            self.recording_service.config_manager.invalidate_cache()


    @patch('app.services.recording.recording_service.RecordingService._generate_stream_metadata', new_callable=AsyncMock)
    @patch('app.services.recording.recording_service.RecordingService._ensure_stream_ended', new_callable=AsyncMock)
    @patch('app.services.recording.recording_service.RecordingService._find_and_validate_mp4', new_callable=AsyncMock)
    def test_updates_stream_recording_path(self, mock_find_mp4, mock_ensure_ended, mock_generate_metadata):
        # Configure mocks
        mock_find_mp4.return_value = self.mock_mp4_path
        mock_ensure_ended.return_value = None
        mock_generate_metadata.return_value = None

        # Run the method under test
        asyncio.run(self.recording_service._delayed_metadata_generation(
            stream_id=self.stream_id,
            output_path=self.mock_mp4_path, # Original output path before potential .ts -> .mp4 conversion
            force_started=False,
            delay=0
        ))

        # Refresh the stream object from the database within the test's session
        # to see changes committed by other sessions.
        # self.test_stream is the instance created in setUp and added to self.db
        self.db.refresh(self.test_stream)

        # Assert that recording_path is updated on the refreshed object
        self.assertIsNotNone(self.test_stream) # Should still exist
        self.assertEqual(self.test_stream.recording_path, self.mock_mp4_path)

        # Assert that mocks were called (optional, but good for confirming flow)
        mock_find_mp4.assert_called_once()
        mock_ensure_ended.assert_called_once_with(self.stream_id, False)
        mock_generate_metadata.assert_called_once_with(self.stream_id, self.mock_mp4_path)
        class TestRemuxToMp4WithLogging(unittest.TestCase):
            
            def setUp(self):
                # Create a fresh recording service instance for each test
                self.recording_service = RecordingService(config_manager=None, metadata_service=None, subprocess_manager=None)
                
                # Create temporary directory for test files
                self.temp_dir = tempfile.mkdtemp()
                # Create test TS file
                self.test_ts_path = os.path.join(self.temp_dir, "test_stream.ts")
                with open(self.test_ts_path, 'wb') as f:
                    # Create a 2MB dummy file
                    f.write(b'0' * (2 * 1024 * 1024))
                
                self.test_mp4_path = os.path.join(self.temp_dir, "test_stream.mp4")

            def tearDown(self):
                # Clean up temporary directory after tests
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            
            @patch('app.services.recording.recording_service.RecordingService.remux_file', new_callable=AsyncMock)
            @patch('app.services.recording.recording_service.os.remove')
            async def test_successful_remux_removes_original_ts(self, mock_remove, mock_remux_file):
                # Setup mock for successful remux
                mock_remux_file.return_value = {"success": True, "exit_code": 0, "stderr": ""}
                
                # Create MP4 file with reasonable size (90% of TS size)
                mp4_size = os.path.getsize(self.test_ts_path) * 0.9
                with open(self.test_mp4_path, 'wb') as f:
                    f.write(b'0' * int(mp4_size))
                    
                # Run the method
                result = await self.recording_service._remux_to_mp4_with_logging(
                    ts_path=self.test_ts_path,
                    mp4_path=self.test_mp4_path,
                    streamer_name="test_streamer"
                )
                
                # Verify result
                self.assertTrue(result)
                mock_remux_file.assert_called_once()
                mock_remove.assert_called_once_with(self.test_ts_path)
            
            @patch('app.services.recording.recording_service.RecordingService.remux_file', new_callable=AsyncMock)
            @patch('app.services.recording.recording_service.os.remove')
            async def test_truncated_mp4_preserves_original_ts(self, mock_remove, mock_remux_file):
                # Setup mock for successful remux but small output file
                mock_remux_file.return_value = {"success": True, "exit_code": 0, "stderr": ""}
                
                # Create MP4 file with too small size (only 20% of TS)
                mp4_size = os.path.getsize(self.test_ts_path) * 0.2
                with open(self.test_mp4_path, 'wb') as f:
                    f.write(b'0' * int(mp4_size))
                    
                # Run the method
                result = await self.recording_service._remux_to_mp4_with_logging(
                    ts_path=self.test_ts_path,
                    mp4_path=self.test_mp4_path,
                    streamer_name="test_streamer"
                )
                
                # Verify result - should return False and not delete TS
                self.assertFalse(result)
                mock_remux_file.assert_called_once()
                mock_remove.assert_not_called()
            
            @patch('app.services.recording.recording_service.RecordingService.remux_file', new_callable=AsyncMock)
            @patch('app.services.recording.recording_service.os.remove')
            async def test_failed_remux_preserves_original_ts(self, mock_remove, mock_remux_file):
                # Setup mock for failed remux
                mock_remux_file.return_value = {
                    "success": False, 
                    "exit_code": 1, 
                    "stderr": "Error: Malformed AAC bitstream detected"
                }
                
                # Run the method
                result = await self.recording_service._remux_to_mp4_with_logging(
                    ts_path=self.test_ts_path,
                    mp4_path=self.test_mp4_path,
                    streamer_name="test_streamer"
                )
                
                # Verify result - should return False and not delete TS
                self.assertFalse(result)
                mock_remux_file.assert_called_once()
                mock_remove.assert_not_called()
            
            @patch('app.services.recording.recording_service.RecordingService.remux_file', new_callable=AsyncMock)
            @patch('app.services.recording.recording_service.logger.error')
            async def test_exception_during_remux_handled_properly(self, mock_logger, mock_remux_file):
                # Setup mock to raise exception
                mock_remux_file.side_effect = Exception("Unexpected error during remux")
                
                # Run the method
                result = await self.recording_service._remux_to_mp4_with_logging(
                    ts_path=self.test_ts_path,
                    mp4_path=self.test_mp4_path,
                    streamer_name="test_streamer"
                )
                
                # Verify result - should return False
                self.assertFalse(result)
                mock_remux_file.assert_called_once()
                mock_logger.assert_called_once()
                self.assertIn("Error during remux", mock_logger.call_args[0][0])
            
            @patch('app.services.recording.recording_service.RecordingService.subprocess_manager.terminate_process', new_callable=AsyncMock)
            async def test_subprocess_cleanup_after_remux(self, mock_terminate):
                # Setup mock for terminate_process
                mock_terminate.return_value = True
                
                # Patch remux_file to return success
                with patch('app.services.recording.recording_service.RecordingService.remux_file', new_callable=AsyncMock) as mock_remux:
                    mock_remux.return_value = {"success": True, "exit_code": 0, "stderr": ""}
                    
                    # Create MP4 file with reasonable size
                    mp4_size = os.path.getsize(self.test_ts_path) * 0.9
                    with open(self.test_mp4_path, 'wb') as f:
                        f.write(b'0' * int(mp4_size))
                        
                    # Run the method
                    await self.recording_service._remux_to_mp4_with_logging(
                        ts_path=self.test_ts_path,
                        mp4_path=self.test_mp4_path,
                        streamer_name="test_streamer"
                    )
                    
                    # Verify subprocess termination was called
                    self.assertTrue(mock_terminate.called)
                    # Check that the process_id starts with ffmpeg_remux
                    self.assertTrue(mock_terminate.call_args[0][0].startswith("ffmpeg_remux_"))

if __name__ == "__main__":
    # This is to ensure that asyncio event loop is managed correctly if tests are run directly
    # For more complex scenarios or CI, using a test runner like pytest with pytest-asyncio is recommended.

    # Discover and run tests
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestRecordingServiceDelayedMetadata))
    runner = unittest.TextTestRunner()
    result = runner.run(suite)

    # Optionally, exit with a status code indicating success/failure
    # if not result.wasSuccessful():
    #     exit(1)
    pass # Keep it simple for now
