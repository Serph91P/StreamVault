#!/usr/bin/env python3
"""
Development Test System Runner

Standalone script to run the development test system without starting the full app.
Useful for quick testing during development.

Usage:
    python test_dev_system.py
"""

import asyncio
import os
import sys
import logging

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set DEBUG mode for testing
os.environ["DEBUG"] = "true"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """Run development tests"""
    try:
        from app.services.system.development_test_runner import development_test_runner
        
        print("🧪 Running StreamVault Development Test Suite")
        print("=" * 60)
        
        success = await development_test_runner.run_all_tests()
        
        if success:
            print("\n🎉 All tests passed! System is ready.")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed. Check output above.")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
