"""
Security Tests - Path Traversal Prevention

Tests for security utilities to ensure path traversal attacks are blocked.
"""

import pytest
import tempfile
import os
from pathlib import Path
from fastapi import HTTPException

from app.utils.security import (
    validate_path_security,
    validate_filename,
    validate_streamer_name,
    validate_file_type
)


class TestPathTraversalPrevention:
    """
    Test suite for path traversal attack prevention
    """
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.safe_base = os.path.realpath(self.temp_dir)
        
        # Mock settings
        import app.config.settings as settings_module
        self.original_get_settings = settings_module.get_settings
        
        class MockSettings:
            RECORDING_DIRECTORY = self.temp_dir
        
        settings_module.get_settings = lambda: MockSettings()
        
    def teardown_method(self):
        """Clean up test environment"""
        import shutil
        import app.config.settings as settings_module
        
        # Restore original settings
        settings_module.get_settings = self.original_get_settings
        
        # Remove temp directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_path_traversal_with_relative_paths_blocked(self):
        """Test that ../../../ path traversal is blocked"""
        with pytest.raises(HTTPException) as exc_info:
            validate_path_security("../../../etc/passwd", "read")
        assert exc_info.value.status_code == 403
        assert "Path outside allowed directory" in exc_info.value.detail
        
    def test_path_traversal_with_absolute_paths_blocked(self):
        """Test that absolute paths outside base are blocked"""
        with pytest.raises(HTTPException) as exc_info:
            validate_path_security("/etc/passwd", "read")
        assert exc_info.value.status_code == 403
        assert "Path outside allowed directory" in exc_info.value.detail
    
    def test_path_traversal_with_encoded_paths_blocked(self):
        """Test that encoded path traversal attempts are blocked"""
        # URL-encoded ../ is %2e%2e%2f
        evil_paths = [
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "....//....//....//etc/passwd",
            "..;/..;/..;/etc/passwd"
        ]
        
        for evil_path in evil_paths:
            # Note: os.path.realpath will normalize these, so they should be blocked
            try:
                result = validate_path_security(evil_path, "access")
                # If it doesn't raise an exception, verify it's still in safe directory
                assert result.startswith(self.safe_base)
            except HTTPException as e:
                # Expected: path blocked
                assert e.status_code in [403, 404, 400]
    
    def test_valid_subdirectory_allowed(self):
        """Test that valid subdirectories are allowed"""
        # Create a subdirectory
        subdir = os.path.join(self.temp_dir, "recordings", "streamer1")
        os.makedirs(subdir, exist_ok=True)
        
        # Create a test file
        test_file = os.path.join(subdir, "test.mp4")
        Path(test_file).touch()
        
        # Should succeed
        result = validate_path_security(test_file, "read")
        assert result == os.path.realpath(test_file)
        assert result.startswith(self.safe_base)
    
    def test_symlink_traversal_blocked(self):
        """Test that symlinks cannot bypass security"""
        # Create a directory outside safe base
        outside_dir = tempfile.mkdtemp()
        
        try:
            # Create symlink inside safe base pointing outside
            evil_link = os.path.join(self.temp_dir, "evil_link")
            os.symlink(outside_dir, evil_link)
            
            # Attempt to access - should be blocked
            with pytest.raises(HTTPException) as exc_info:
                validate_path_security(evil_link, "read")
            
            assert exc_info.value.status_code == 403
            assert "Path outside allowed directory" in exc_info.value.detail
            
        finally:
            # Cleanup
            if os.path.exists(evil_link):
                os.unlink(evil_link)
            if os.path.exists(outside_dir):
                os.rmdir(outside_dir)
    
    def test_nonexistent_path_with_read_operation(self):
        """Test that non-existent paths fail for read operations"""
        nonexistent = os.path.join(self.temp_dir, "does_not_exist.mp4")
        
        with pytest.raises(HTTPException) as exc_info:
            validate_path_security(nonexistent, "read")
        
        assert exc_info.value.status_code == 404
        assert "Path not found" in exc_info.value.detail
    
    def test_valid_base_directory_allowed(self):
        """Test that the base directory itself is allowed"""
        result = validate_path_security(self.temp_dir, "access")
        assert result == self.safe_base
    
    def test_empty_path_blocked(self):
        """Test that empty paths are blocked"""
        with pytest.raises(HTTPException) as exc_info:
            validate_path_security("", "read")
        
        assert exc_info.value.status_code == 400
        assert "Path cannot be empty" in exc_info.value.detail
    
    def test_null_path_blocked(self):
        """Test that null paths are blocked"""
        with pytest.raises(HTTPException) as exc_info:
            validate_path_security(None, "read")  # type: ignore
        
        assert exc_info.value.status_code == 400


class TestFilenameValidation:
    """
    Test suite for filename validation and sanitization
    """
    
    def test_valid_filename(self):
        """Test that valid filenames pass"""
        assert validate_filename("test.mp4") == "test.mp4"
        assert validate_filename("stream_2024_01_15.mkv") == "stream_2024_01_15.mkv"
        assert validate_filename("my video.ts") == "my_video.ts"
    
    def test_path_traversal_in_filename(self):
        """Test that path traversal attempts are neutralized"""
        # ../ should be converted to safe characters
        result = validate_filename("../evil.mp4")
        assert ".." not in result or result == "..evil.mp4"  # Dots allowed but not as directory reference
        
    def test_dangerous_characters_removed(self):
        """Test that dangerous characters are removed or replaced"""
        result = validate_filename("test<>:\"|?*.mp4")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "?" not in result
        assert "*" not in result
    
    def test_hidden_files_blocked(self):
        """Test that hidden files are blocked"""
        with pytest.raises(ValueError):
            validate_filename(".hidden")
            
        with pytest.raises(ValueError):
            validate_filename("..")
            
        with pytest.raises(ValueError):
            validate_filename(".")
    
    def test_empty_filename_blocked(self):
        """Test that empty filenames are blocked"""
        with pytest.raises(ValueError):
            validate_filename("")
            
        with pytest.raises(ValueError):
            validate_filename("   ")
    
    def test_filename_length_limit(self):
        """Test that excessively long filenames are blocked"""
        long_filename = "a" * 300 + ".mp4"
        with pytest.raises(ValueError) as exc_info:
            validate_filename(long_filename)
        assert "too long" in str(exc_info.value).lower()


class TestStreamerNameValidation:
    """
    Test suite for Twitch streamer name validation
    """
    
    def test_valid_streamer_names(self):
        """Test that valid Twitch usernames pass"""
        assert validate_streamer_name("validname") == "validname"
        assert validate_streamer_name("Test_User_123") == "test_user_123"
        assert validate_streamer_name("a1b2c3d4") == "a1b2c3d4"
    
    def test_invalid_characters_blocked(self):
        """Test that invalid characters are blocked"""
        with pytest.raises(ValueError):
            validate_streamer_name("invalid-name!")  # Exclamation mark not allowed
            
        with pytest.raises(ValueError):
            validate_streamer_name("name with spaces")
    
    def test_length_requirements(self):
        """Test Twitch username length requirements (4-25 chars)"""
        with pytest.raises(ValueError):
            validate_streamer_name("abc")  # Too short
            
        with pytest.raises(ValueError):
            validate_streamer_name("a" * 26)  # Too long
    
    def test_must_start_with_alphanumeric(self):
        """Test that username must start with letter or number"""
        with pytest.raises(ValueError):
            validate_streamer_name("_underscore")  # Cannot start with underscore


class TestFileTypeValidation:
    """
    Test suite for file type validation
    """
    
    def test_valid_video_extensions(self):
        """Test that valid video extensions pass"""
        assert validate_file_type("video.mp4") == ".mp4"
        assert validate_file_type("stream.mkv") == ".mkv"
        assert validate_file_type("recording.ts") == ".ts"
    
    def test_invalid_extensions_blocked(self):
        """Test that invalid file types are blocked"""
        with pytest.raises(ValueError):
            validate_file_type("malware.exe")
            
        with pytest.raises(ValueError):
            validate_file_type("script.sh")
            
        with pytest.raises(ValueError):
            validate_file_type("document.pdf")
    
    def test_no_extension_blocked(self):
        """Test that files without extensions are blocked"""
        with pytest.raises(ValueError):
            validate_file_type("noextension")
    
    def test_case_insensitive(self):
        """Test that extension checking is case-insensitive"""
        assert validate_file_type("VIDEO.MP4") == ".mp4"
        assert validate_file_type("Stream.MKV") == ".mkv"


class TestSecurityIntegration:
    """
    Integration tests for security functions working together
    """
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock settings
        import app.config.settings as settings_module
        self.original_get_settings = settings_module.get_settings
        
        class MockSettings:
            RECORDING_DIRECTORY = self.temp_dir
        
        settings_module.get_settings = lambda: MockSettings()
    
    def teardown_method(self):
        """Clean up"""
        import shutil
        import app.config.settings as settings_module
        
        settings_module.get_settings = self.original_get_settings
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_complete_file_validation_workflow(self):
        """Test complete workflow of validating user input for file operations"""
        # User provides inputs
        streamer_name = "TestStreamer123"
        filename = "../../../etc/passwd"
        
        # Validate streamer name
        clean_streamer = validate_streamer_name(streamer_name)
        assert clean_streamer == "teststreamer123"
        
        # Validate filename (neutralizes path traversal)
        clean_filename = validate_filename(filename)
        assert ".." not in clean_filename or clean_filename.startswith(".")
        
        # Construct path
        file_path = os.path.join(self.temp_dir, clean_streamer, clean_filename)
        
        # Final validation - should fail because file doesn't exist
        with pytest.raises(HTTPException):
            validate_path_security(file_path, "read")
    
    def test_attack_chain_blocked(self):
        """Test that a chain of attack attempts is blocked"""
        attack_vectors = [
            ("../../../etc/passwd", "Path traversal with relative paths"),
            ("/etc/shadow", "Absolute path outside base"),
            ("..\\..\\..\\windows\\system32", "Windows path traversal"),
            (".htaccess", "Hidden file access"),
            ("file<>:\"|.mp4", "Command injection characters in filename")
        ]
        
        for attack_input, description in attack_vectors:
            try:
                # Try to sanitize filename
                try:
                    clean_filename = validate_filename(attack_input)
                except ValueError:
                    # Filename validation blocked it
                    continue
                
                # Try to validate path
                file_path = os.path.join(self.temp_dir, clean_filename)
                validate_path_security(file_path, "access")
                
                # If we get here, verify result is still safe
                resolved = os.path.realpath(file_path)
                assert resolved.startswith(os.path.realpath(self.temp_dir)), \
                    f"Attack vector '{description}' bypassed security!"
                    
            except (HTTPException, ValueError):
                # Expected: attack blocked
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
