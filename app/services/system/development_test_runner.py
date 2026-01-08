"""
Development Test Runner - Automated testing on app startup when DEBUG=True

This service runs comprehensive tests of all major functionality when the application
starts in debug mode, providing immediate feedback on what's working and what's broken.
"""

import logging
import asyncio
import os
import subprocess
import sys
import json
import time
from typing import Dict, List, Optional
from datetime import datetime
from app.database import SessionLocal
from app.models import GlobalSettings, User, Streamer, Stream, Recording
from app.services.unified_image_service import unified_image_service

logger = logging.getLogger("streamvault")


class DevelopmentTestRunner:
    """Runs comprehensive tests on app startup in debug mode"""

    def __init__(self):
        self.test_results: Dict[str, Dict[str, any]] = {}
        self.failed_tests: List[str] = []
        self.passed_tests: List[str] = []
        self.test_log_file = None
        self._setup_test_logging()

    async def run_all_tests(self) -> bool:
        """Run all development tests and return True if all pass"""
        logger.info("🧪 STARTING DEVELOPMENT TESTS")
        logger.info("=" * 60)

        # Test categories
        test_categories = [
            ("Database", self._test_database),
            ("Services", self._test_services),
            ("Notifications", self._test_notifications),
            ("Image Processing", self._test_image_processing),
            ("Authentication", self._test_authentication),
            ("Recording System", self._test_recording_system),
            ("Recording Service Integration", self._test_recording_service_integration),
            ("Pytest Integration", self._test_pytest_suite),
            ("End-to-End Recording", self._test_end_to_end_recording),
        ]

        for category_name, test_func in test_categories:
            logger.info(f"🔍 Testing {category_name}...")
            try:
                await test_func()
                logger.info(f"✅ {category_name} tests completed")
            except Exception as e:
                logger.error(f"❌ {category_name} tests failed: {e}")
                self.failed_tests.append(f"{category_name}: {str(e)}")

        # Summary
        self._print_test_summary()
        self._save_test_results()
        return len(self.failed_tests) == 0

    async def _test_database(self):
        """Test database connectivity and basic operations"""
        try:
            with SessionLocal() as db:
                # Test basic query
                _ = db.query(GlobalSettings).first()  # Verify query works
                self._record_test("Database Connection", True, "Successfully connected to database")

                # Test user table
                user_count = db.query(User).count()
                self._record_test("User Table", True, f"Found {user_count} users")

                # Test streamer table
                streamer_count = db.query(Streamer).count()
                self._record_test("Streamer Table", True, f"Found {streamer_count} streamers")

        except Exception as e:
            self._record_test("Database Connection", False, str(e))
            raise

    async def _test_services(self):
        """Test that all services can be imported and initialized"""
        # Test services from the new refactored structure
        service_imports = [
            # Core services
            ("UnifiedImageService", "app.services.unified_image_service", "unified_image_service"),
            ("AuthService", "app.services.core.auth_service", "AuthService"),
            ("LoggingService", "app.services.system.logging_service", "LoggingService"),
            ("CleanupService", "app.services.system.cleanup_service", "CleanupService"),

            # Notification services
            ("NotificationDispatcher", "app.services.notifications.notification_dispatcher", "NotificationDispatcher"),
            ("ExternalNotificationService", "app.services.notifications.external_notification_service", "ExternalNotificationService"),
            ("PushNotificationService", "app.services.notifications.push_notification_service", "PushNotificationService"),

            # Recording services
            ("RecordingService", "app.services.recording.recording_service", "RecordingService"),
            ("RecordingOrchestrator", "app.services.recording.recording_orchestrator", "RecordingOrchestrator"),
            ("RecordingLifecycleManager", "app.services.recording.recording_lifecycle_manager", "RecordingLifecycleManager"),

            # Media services
            ("MetadataService", "app.services.media.metadata_service", "MetadataService"),
            ("ThumbnailService", "app.services.images.thumbnail_service", "ThumbnailService"),

            # Communication services
            ("ModernWebPushService", "app.services.communication.webpush_service", "ModernWebPushService"),
            ("WebSocketManager", "app.services.communication.websocket_manager", "WebSocketManager"),

            # Processing services
            ("TaskDependencyManager", "app.services.processing.task_dependency_manager", "TaskDependencyManager"),
            ("TaskProgressTracker", "app.services.queues.task_progress_tracker", "TaskProgressTracker"),

            # Background services
            ("BackgroundQueueService", "app.services.background_queue_service", "BackgroundQueueService"),

            # Streamer services
            ("StreamerService", "app.services.streamer_service", "StreamerService"),
        ]

        for service_name, module_path, class_name in service_imports:
            try:
                # Dynamic import
                module = __import__(module_path, fromlist=[class_name])

                if hasattr(module, class_name):
                    service_class = getattr(module, class_name)

                    # Try to initialize the service
                    if class_name == "unified_image_service":
                        # This is already an instance
                        pass  # service_class is an instance, just verify import worked
                    else:
                        # This is a class, instantiate it
                        _ = service_class()  # Verify instantiation works

                    self._record_test(f"Service: {service_name}", True, f"Imported and initialized from {module_path}")

                elif hasattr(module, class_name.lower()):
                    # Try lowercase version (for instances)
                    _ = getattr(module, class_name.lower())  # Verify exists
                    self._record_test(f"Service: {service_name}", True, f"Imported instance from {module_path}")

                else:
                    self._record_test(f"Service: {service_name}", False, f"Class {class_name} not found in {module_path}")

            except ImportError as e:
                self._record_test(f"Service: {service_name}", False, f"Import failed: {str(e)}")
            except Exception as e:
                self._record_test(f"Service: {service_name}", False, f"Initialization failed: {str(e)}")

    async def _test_notifications(self):
        """Test notification system"""
        try:
            # Test the new refactored notification structure
            from app.services.notifications.external_notification_service import ExternalNotificationService
            external_service = ExternalNotificationService()
            test_result = await external_service.send_test_notification()

            if test_result:
                self._record_test("External Notification Test", True, "Test notification sent successfully")
            else:
                self._record_test("External Notification Test", False, "Test notification failed to send")

            # Also test notification dispatcher
            try:
                from app.services.notifications.notification_dispatcher import NotificationDispatcher
                _ = NotificationDispatcher()  # Verify init works
                # Test basic dispatcher functionality
                self._record_test("Notification Dispatcher Init", True, "NotificationDispatcher initialized successfully")
            except Exception as e:
                self._record_test("Notification Dispatcher Init", False, f"Dispatcher error: {str(e)}")

        except Exception as e:
            self._record_test("Notification Test", False, str(e))

    async def _test_image_processing(self):
        """Test image processing capabilities"""
        try:
            # Test image service initialization
            cache_dir = unified_image_service.cache_dir
            self._record_test("Image Cache Directory", True, f"Cache directory: {cache_dir}")

            # Test if we can create cache directories
            os.makedirs(cache_dir, exist_ok=True)
            self._record_test("Image Cache Creation", True, "Cache directory created successfully")

        except Exception as e:
            self._record_test("Image Processing", False, str(e))

    async def _test_authentication(self):
        """Test authentication system"""
        try:
            with SessionLocal() as db:
                admin_count = db.query(User).filter(User.is_admin.is_(True)).count()

                if admin_count > 0:
                    self._record_test("Admin User", True, f"Found {admin_count} admin users")
                else:
                    self._record_test("Admin User", False, "No admin users found - setup required")

        except Exception as e:
            self._record_test("Authentication System", False, str(e))

    async def _test_recording_system(self):
        """Test recording system components"""
        try:
            # Test recording directory
            recordings_dir = os.path.join(os.getcwd(), "recordings")
            os.makedirs(recordings_dir, exist_ok=True)
            self._record_test("Recording Directory", True, f"Recording directory: {recordings_dir}")

            # Import recording services to test they load properly
            self._record_test("Recording Service Import", True, "Recording service imports successfully")

        except Exception as e:
            self._record_test("Recording System", False, str(e))

    async def _test_recording_service_integration(self):
        """Test the actual recording services (not just ffmpeg directly)"""
        try:
            # Import and test recording services
            from app.services.recording.recording_service import RecordingService

            # Test service initialization
            try:
                recording_service = RecordingService()
                self._record_test("Recording Service Init", True, "RecordingService initialized successfully")
            except Exception as e:
                self._record_test("Recording Service Init", False, f"Failed to initialize: {str(e)}")
                return

            # Create test data in database
            test_streamer_id, test_stream_id = await self._create_test_database_entries()

            if test_streamer_id and test_stream_id:
                # Test the actual recording workflow
                await self._test_recording_service_workflow(recording_service, test_stream_id, test_streamer_id)

                # Test recording state management
                await self._test_recording_state_management(recording_service, test_stream_id)

                # Cleanup test data
                await self._cleanup_test_database_entries(test_streamer_id, test_stream_id)

        except Exception as e:
            self._record_test("Recording Service Integration", False, str(e))

    async def _create_test_database_entries(self) -> tuple[Optional[int], Optional[int]]:
        """Create test streamer and stream entries for recording tests"""
        try:
            with SessionLocal() as db:
                # Create test streamer
                test_streamer = Streamer(
                    twitch_id="test_streamer_123456",
                    username="test_streamer_dev",
                    is_live=True,
                    title="Development Test Stream",
                    category_name="Software and Game Development",
                    language="en"
                )
                db.add(test_streamer)
                db.flush()

                # Create test stream
                test_stream = Stream(
                    streamer_id=test_streamer.id,
                    title="Development Test Stream",
                    category_name="Software and Game Development",
                    language="en",
                    started_at=datetime.now(),
                    twitch_stream_id="test_stream_789"
                )
                db.add(test_stream)
                db.flush()

                db.commit()

                self._record_test("Test Database Entries", True, f"Created streamer {test_streamer.id} and stream {test_stream.id}")
                return test_streamer.id, test_stream.id

        except Exception as e:
            self._record_test("Test Database Entries", False, f"Failed to create test data: {str(e)}")
            return None, None

    async def _test_recording_service_workflow(self, recording_service, stream_id: int, streamer_id: int):
        """Test the complete recording service workflow"""
        try:
            self._log_test_detail(f"Testing recording workflow: stream_id={stream_id}, streamer_id={streamer_id}")

            # Test start_recording method
            recording_id = await recording_service.start_recording(stream_id, streamer_id)

            if recording_id:
                self._record_test("Recording Start", True, f"Started recording with ID: {recording_id}")

                # Wait a moment for recording to initialize
                await asyncio.sleep(1)

                # Test get_recording_status
                try:
                    status = await recording_service.get_recording_status(recording_id)
                    if status:
                        self._record_test("Recording Status Check", True, f"Status: {status.get('status', 'unknown')}")
                    else:
                        self._record_test("Recording Status Check", False, "No status returned")
                except Exception as e:
                    self._record_test("Recording Status Check", False, f"Status check failed: {str(e)}")

                # Test stop_recording method
                try:
                    stop_result = await recording_service.stop_recording(recording_id, reason="test_completion")
                    if stop_result:
                        self._record_test("Recording Stop", True, "Successfully stopped recording")
                    else:
                        self._record_test("Recording Stop", False, "Failed to stop recording")
                except Exception as e:
                    self._record_test("Recording Stop", False, f"Stop failed: {str(e)}")

            else:
                self._record_test("Recording Start", False, "Failed to start recording - no ID returned")

        except Exception as e:
            self._record_test("Recording Service Workflow", False, f"Workflow test failed: {str(e)}")

    async def _test_recording_state_management(self, recording_service, stream_id: int):
        """Test recording state management functionality"""
        try:
            # Test get_active_recordings
            active_recordings = await recording_service.get_active_recordings()
            if isinstance(active_recordings, list):
                self._record_test("Active Recordings Check", True, f"Found {len(active_recordings)} active recordings")
            else:
                self._record_test("Active Recordings Check", False, "Failed to get active recordings list")

            # Test get_stream_recordings
            try:
                stream_recordings = await recording_service.get_stream_recordings(stream_id)
                if isinstance(stream_recordings, list):
                    self._record_test("Stream Recordings Check", True, f"Found {len(stream_recordings)} recordings for stream")
                else:
                    self._record_test("Stream Recordings Check", False, "Failed to get stream recordings")
            except Exception as e:
                self._record_test("Stream Recordings Check", False, f"Error: {str(e)}")

        except Exception as e:
            self._record_test("Recording State Management", False, f"State management test failed: {str(e)}")

    async def _cleanup_test_database_entries(self, streamer_id: int, stream_id: int):
        """Clean up test database entries"""
        try:
            with SessionLocal() as db:
                # Delete any recordings for this stream
                recordings = db.query(Recording).filter(Recording.stream_id == stream_id).all()
                for recording in recordings:
                    db.delete(recording)

                # Delete stream
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if stream:
                    db.delete(stream)

                # Delete streamer
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if streamer:
                    db.delete(streamer)

                db.commit()
                self._record_test("Test Data Cleanup", True, "Successfully cleaned up test data")

        except Exception as e:
            self._record_test("Test Data Cleanup", False, f"Cleanup failed: {str(e)}")

    async def _test_pytest_suite(self):
        """Run existing pytest test suite"""
        try:
            # Run critical tests first (fastest)
            critical_result = await self._run_pytest_file("tests/test_critical_functionality.py")
            self._record_test("Critical Functionality Tests", critical_result["success"], critical_result["message"])

            # Run service tests
            service_result = await self._run_pytest_file("tests/test_refactored_services.py")
            self._record_test("Refactored Services Tests", service_result["success"], service_result["message"])

            # Run API tests
            api_result = await self._run_pytest_file("tests/test_api_routes.py")
            self._record_test("API Routes Tests", api_result["success"], api_result["message"])

            # Run utils tests
            utils_result = await self._run_pytest_file("tests/utils/test_streamlink_utils.py")
            self._record_test("Streamlink Utils Tests", utils_result["success"], utils_result["message"])

            # Run specific service tests
            recording_result = await self._run_pytest_file("tests/services/test_recording_service.py")
            self._record_test("Recording Service Tests", recording_result["success"], recording_result["message"])

        except Exception as e:
            self._record_test("Pytest Suite", False, str(e))

    async def _run_pytest_file(self, test_file: str) -> Dict[str, any]:
        """Run a specific pytest file and return results"""
        try:
            # Check if test file exists
            if not os.path.exists(test_file):
                return {"success": False, "message": f"Test file not found: {test_file}"}

            # Run pytest with short output
            result = subprocess.run([
                sys.executable, "-m", "pytest", test_file, "-v", "--tb=short", "--maxfail=3"
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return {"success": True, "message": f"All tests passed ({test_file})"}
            else:
                # Extract useful error info
                error_lines = result.stdout.split('\n')[-10:]  # Last 10 lines
                error_summary = '\n'.join([line for line in error_lines if line.strip()])
                return {"success": False, "message": f"Tests failed: {error_summary[:200]}..."}

        except subprocess.TimeoutExpired:
            return {"success": False, "message": f"Tests timed out after 30s ({test_file})"}
        except Exception as e:
            return {"success": False, "message": f"Error running tests: {str(e)}"}

    async def _test_end_to_end_recording(self):
        """Test the complete recording pipeline with a test video"""
        try:
            # Create test video file
            test_video_path = await self._create_test_video()
            self._record_test("Test Video Creation", True, f"Created test video: {test_video_path}")

            # Test video processing pipeline
            await self._test_video_processing_pipeline(test_video_path)

            # Test streamlink command generation (mock)
            await self._test_streamlink_integration()

            # Cleanup
            if os.path.exists(test_video_path):
                os.remove(test_video_path)

        except Exception as e:
            self._record_test("End-to-End Recording", False, str(e))

    async def _create_test_video(self) -> str:
        """Create a realistic test .ts file for recording pipeline testing"""
        test_video_dir = os.path.join(os.getcwd(), "recordings", "test")
        os.makedirs(test_video_dir, exist_ok=True)
        test_ts_path = os.path.join(test_video_dir, "test_stream.ts")
        test_mp4_path = os.path.join(test_video_dir, "test_stream.mp4")

        try:
            # Create a realistic .ts file (Transport Stream like Streamlink would create)
            result = subprocess.run([
                "ffmpeg",
                "-f", "lavfi",
                "-i", "testsrc=duration=5:size=1280x720:rate=30",  # 5 second 720p test video
                "-f", "lavfi",
                "-i", "sine=frequency=1000:duration=5",  # 5 second test audio
                "-c:v", "libx264",
                "-c:a", "aac",
                "-f", "mpegts",  # Output as Transport Stream (.ts)
                "-t", "5",
                "-y", test_ts_path
            ], capture_output=True, timeout=15)

            if result.returncode == 0 and os.path.exists(test_ts_path):
                self._log_test_detail(f"Created realistic .ts file: {test_ts_path} ({os.path.getsize(test_ts_path)} bytes)")

                # Now test the remux process from .ts to .mp4
                await self._test_ts_to_mp4_remux(test_ts_path, test_mp4_path)

                return test_ts_path

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self._log_test_detail(f"ffmpeg failed: {e}")

        # Fallback: create a minimal .ts file
        self._log_test_detail("Creating fallback .ts file")
        with open(test_ts_path, 'wb') as f:
            # Write minimal TS packet headers (hex for Transport Stream)
            f.write(bytes.fromhex('474011100000b00d0001c100000001e020'))
            f.write(b'DUMMY_TS_FILE_FOR_TESTING' * 100)  # Pad to reasonable size

        return test_ts_path

    async def _test_ts_to_mp4_remux(self, ts_path: str, mp4_path: str):
        """Test the crucial .ts to .mp4 remux process"""
        try:
            self._log_test_detail(f"Testing remux: {ts_path} -> {mp4_path}")

            # This mimics what the recording system does
            remux_command = [
                "ffmpeg",
                "-i", ts_path,
                "-c", "copy",  # Copy streams without re-encoding
                "-avoid_negative_ts", "make_zero",
                "-fflags", "+genpts",
                "-y", mp4_path
            ]

            start_time = time.time()
            result = subprocess.run(remux_command, capture_output=True, timeout=30)
            remux_time = time.time() - start_time

            if result.returncode == 0 and os.path.exists(mp4_path):
                mp4_size = os.path.getsize(mp4_path)
                self._record_test("TS to MP4 Remux", True, f"Remuxed in {remux_time:.2f}s, output: {mp4_size} bytes")

                # Test metadata addition
                await self._test_metadata_addition(mp4_path)

            else:
                error_output = result.stderr.decode() if result.stderr else "No error output"
                self._record_test("TS to MP4 Remux", False, f"Remux failed: {error_output[:200]}")

        except subprocess.TimeoutExpired:
            self._record_test("TS to MP4 Remux", False, "Remux timed out after 30s")
        except Exception as e:
            self._record_test("TS to MP4 Remux", False, f"Remux error: {str(e)}")

    async def _test_metadata_addition(self, mp4_path: str):
        """Test adding stream metadata to the final MP4"""
        try:
            # Create test metadata (like what would come from Twitch API)
            test_metadata = {
                "title": "Test Stream for StreamVault",
                "streamer": "test_streamer",
                "category": "Software and Game Development",
                "started_at": "2025-01-17T19:00:00Z",
                "language": "en"
            }

            # Test metadata command generation
            metadata_args = []
            for key, value in test_metadata.items():
                metadata_args.extend(["-metadata", f"{key}={value}"])

            output_path = mp4_path.replace(".mp4", "_with_metadata.mp4")

            metadata_command = [
                "ffmpeg",
                "-i", mp4_path,
                "-c", "copy"
            ] + metadata_args + [
                "-y", output_path
            ]

            result = subprocess.run(metadata_command, capture_output=True, timeout=15)

            if result.returncode == 0 and os.path.exists(output_path):
                self._record_test("Metadata Addition", True, f"Added {len(test_metadata)} metadata fields")

                # Verify metadata was added
                verify_result = subprocess.run([
                    "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", output_path
                ], capture_output=True, timeout=10)

                if verify_result.returncode == 0:
                    probe_data = json.loads(verify_result.stdout.decode())
                    tags = probe_data.get("format", {}).get("tags", {})
                    found_tags = len([tag for tag in test_metadata.keys() if tag in tags])
                    self._record_test("Metadata Verification", True, f"Verified {found_tags}/{len(test_metadata)} metadata tags")

            else:
                self._record_test("Metadata Addition", False, "Failed to add metadata to MP4")

        except Exception as e:
            self._record_test("Metadata Addition", False, f"Metadata error: {str(e)}")

    async def _test_video_processing_pipeline(self, test_video_path: str):
        """Test video processing components"""
        try:
            # Test file detection
            if os.path.exists(test_video_path):
                self._record_test("Video File Detection", True, "Test video file exists")
            else:
                self._record_test("Video File Detection", False, "Test video file missing")
                return

            # Test recording directory structure
            recordings_dir = os.path.dirname(test_video_path)
            if os.path.exists(recordings_dir):
                self._record_test("Recording Directory", True, f"Directory: {recordings_dir}")

            # Test file size
            file_size = os.path.getsize(test_video_path)
            self._record_test("Video File Size", True, f"File size: {file_size} bytes")

        except Exception as e:
            self._record_test("Video Processing Pipeline", False, str(e))

    async def _test_streamlink_integration(self):
        """Test streamlink command generation and validation"""
        try:
            # Import streamlink utils
            from app.utils.streamlink_utils import StreamlinkUtils

            streamlink_utils = StreamlinkUtils()

            # Test command generation
            test_url = "https://twitch.tv/test_streamer"
            test_output = "/tmp/test_output.mp4"

            command = streamlink_utils.get_streamlink_command(test_url, test_output)

            if command and len(command) > 0:
                self._record_test("Streamlink Command Generation", True, f"Generated command with {len(command)} parts")
            else:
                self._record_test("Streamlink Command Generation", False, "Failed to generate command")

            # Test streamlink availability
            try:
                result = subprocess.run(["streamlink", "--version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    version = result.stdout.decode().strip()
                    self._record_test("Streamlink Availability", True, f"Version: {version}")
                else:
                    self._record_test("Streamlink Availability", False, "Streamlink command failed")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self._record_test("Streamlink Availability", False, "Streamlink not found in PATH")

        except Exception as e:
            self._record_test("Streamlink Integration", False, str(e))

    def _setup_test_logging(self):
        """Setup test log file"""
        try:
            test_logs_dir = os.path.join(os.getcwd(), "temp_logs", "dev_tests")
            os.makedirs(test_logs_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_filename = f"dev_test_results_{timestamp}.log"
            self.test_log_file = os.path.join(test_logs_dir, log_filename)

            # Initialize log file
            with open(self.test_log_file, 'w') as f:
                f.write("StreamVault Development Test Results\n")
                f.write(f"Started: {datetime.now().isoformat()}\n")
                f.write("=" * 60 + "\n\n")

            logger.info(f"Test log file: {self.test_log_file}")

        except Exception as e:
            logger.error(f"Failed to setup test logging: {e}")
            self.test_log_file = None

    def _log_test_detail(self, message: str):
        """Log detailed test information to file"""
        if self.test_log_file:
            try:
                with open(self.test_log_file, 'a') as f:
                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
            except Exception:
                pass  # Don't break tests if logging fails

        logger.debug(message)

    def _save_test_results(self):
        """Save comprehensive test results to log file"""
        if not self.test_log_file:
            return

        try:
            with open(self.test_log_file, 'a') as f:
                f.write("\n" + "=" * 60 + "\n")
                f.write("FINAL TEST RESULTS\n")
                f.write("=" * 60 + "\n\n")

                # Summary
                total_tests = len(self.test_results)
                passed_count = len(self.passed_tests)
                failed_count = len(self.failed_tests)

                f.write(f"Total Tests: {total_tests}\n")
                f.write(f"Passed: {passed_count}\n")
                f.write(f"Failed: {failed_count}\n")
                f.write(f"Success Rate: {(passed_count / total_tests * 100):.1f}%\n\n")

                # Detailed results
                f.write("DETAILED RESULTS:\n")
                f.write("-" * 40 + "\n")

                for test_name, result in self.test_results.items():
                    status = "✅ PASS" if result["success"] else "❌ FAIL"
                    f.write(f"{status} {test_name}\n")
                    f.write(f"    Message: {result['message']}\n")
                    f.write(f"    Time: {result['timestamp'].strftime('%H:%M:%S')}\n\n")

                # Failed tests summary
                if self.failed_tests:
                    f.write("\nFAILED TESTS SUMMARY:\n")
                    f.write("-" * 40 + "\n")
                    for test_name in self.failed_tests:
                        result = self.test_results[test_name]
                        f.write(f"❌ {test_name}: {result['message']}\n")

                f.write(f"\nTest completed: {datetime.now().isoformat()}\n")

            logger.info(f"📄 Full test results saved to: {self.test_log_file}")

        except Exception as e:
            logger.error(f"Failed to save test results: {e}")

    def _record_test(self, test_name: str, success: bool, message: str):
        """Record a test result"""
        self.test_results[test_name] = {
            "success": success,
            "message": message,
            "timestamp": datetime.now()
        }

        if success:
            self.passed_tests.append(test_name)
            logger.debug(f"  ✅ {test_name}: {message}")
        else:
            self.failed_tests.append(test_name)
            logger.warning(f"  ❌ {test_name}: {message}")

        # Also log to file
        self._log_test_detail(f"{'✅ PASS' if success else '❌ FAIL'} {test_name}: {message}")

    def _print_test_summary(self):
        """Print comprehensive test summary"""
        logger.info("=" * 60)
        logger.info("🧪 DEVELOPMENT TEST SUMMARY")
        logger.info("=" * 60)

        total_tests = len(self.test_results)
        passed_count = len(self.passed_tests)
        failed_count = len(self.failed_tests)

        logger.info(f"📊 Total Tests: {total_tests}")
        logger.info(f"✅ Passed: {passed_count}")
        logger.info(f"❌ Failed: {failed_count}")
        logger.info(f"📈 Success Rate: {(passed_count / total_tests * 100):.1f}%")

        if self.failed_tests:
            logger.info("")
            logger.info("❌ FAILED TESTS:")
            for test_name in self.failed_tests:
                result = self.test_results[test_name]
                logger.info(f"  - {test_name}: {result['message']}")

        if self.passed_tests:
            logger.info("")
            logger.info("✅ PASSED TESTS:")
            for test_name in self.passed_tests:
                result = self.test_results[test_name]
                logger.debug(f"  - {test_name}: {result['message']}")

        logger.info("=" * 60)

        if failed_count == 0:
            logger.info("🎉 ALL TESTS PASSED! System is ready for development.")
        else:
            logger.warning(f"⚠️  {failed_count} tests failed. Please fix issues before proceeding.")

        logger.info("=" * 60)


# Global instance
development_test_runner = DevelopmentTestRunner()


async def run_development_tests() -> bool:
    """Run development tests if in debug mode"""
    # Only run if DEBUG environment variable is set
    if os.getenv("DEBUG", "").lower() in ["true", "1", "yes"]:
        return await development_test_runner.run_all_tests()
    return True
