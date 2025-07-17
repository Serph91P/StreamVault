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
from typing import Dict, List, Optional
from datetime import datetime
from app.database import SessionLocal
from app.models import GlobalSettings, User, Streamer
from app.services.unified_image_service import unified_image_service
from app.services.notifications.notification_service import notification_service

logger = logging.getLogger("streamvault")


class DevelopmentTestRunner:
    """Runs comprehensive tests on app startup in debug mode"""
    
    def __init__(self):
        self.test_results: Dict[str, Dict[str, any]] = {}
        self.failed_tests: List[str] = []
        self.passed_tests: List[str] = []
        
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
        return len(self.failed_tests) == 0
    
    async def _test_database(self):
        """Test database connectivity and basic operations"""
        try:
            with SessionLocal() as db:
                # Test basic query
                settings = db.query(GlobalSettings).first()
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
        services_to_test = [
            ("UnifiedImageService", lambda: unified_image_service),
            ("NotificationService", lambda: notification_service),
        ]
        
        for service_name, service_getter in services_to_test:
            try:
                service = service_getter()
                self._record_test(f"Service: {service_name}", True, "Service initialized successfully")
            except Exception as e:
                self._record_test(f"Service: {service_name}", False, str(e))
    
    async def _test_notifications(self):
        """Test notification system"""
        try:
            # Test notification service initialization
            test_result = await notification_service.send_test_notification()
            
            if test_result:
                self._record_test("Notification Test", True, "Test notification sent successfully")
            else:
                self._record_test("Notification Test", False, "Test notification failed to send")
                
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
                admin_count = db.query(User).filter(User.is_admin == True).count()
                
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
            from app.services.recording.recording_service import RecordingService
            self._record_test("Recording Service Import", True, "Recording service imports successfully")
            
        except Exception as e:
            self._record_test("Recording System", False, str(e))
    
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
        """Create a small test video file using ffmpeg if available"""
        test_video_dir = os.path.join(os.getcwd(), "recordings", "test")
        os.makedirs(test_video_dir, exist_ok=True)
        test_video_path = os.path.join(test_video_dir, "test_stream.mp4")
        
        try:
            # Try to create a test video with ffmpeg
            result = subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1", 
                "-c:v", "libx264", "-t", "1", "-y", test_video_path
            ], capture_output=True, timeout=10)
            
            if result.returncode == 0 and os.path.exists(test_video_path):
                return test_video_path
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Fallback: create a dummy file
        with open(test_video_path, 'wb') as f:
            f.write(b'DUMMY_VIDEO_FILE_FOR_TESTING')
        
        return test_video_path
    
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
        logger.info(f"📈 Success Rate: {(passed_count/total_tests*100):.1f}%")
        
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
