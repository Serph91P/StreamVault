#!/usr/bin/env python3
"""
Check Queue Service Status in Running App
This script checks if the queue service is running in the actual FastAPI app
"""

import asyncio
import logging
import sys
import requests
import json

# Configure logging for detailed debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("check_queue_api")

def check_queue_via_api():
    """Check queue status via the FastAPI endpoints"""
    try:
        logger.info("🔍 Checking queue status via API...")
        
        # Check queue stats endpoint
        response = requests.get("http://localhost:7000/api/background-queue/stats")
        
        if response.status_code == 200:
            stats = response.json()
            logger.info(f"📊 Queue stats from API: {json.dumps(stats, indent=2)}")
            
            if stats.get('is_running'):
                logger.info("✅ Queue service is running in the FastAPI app!")
            else:
                logger.error("❌ Queue service is NOT running in the FastAPI app!")
                
            return stats
        else:
            logger.error(f"❌ Failed to get queue stats: HTTP {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to check queue via API: {e}", exc_info=True)
        return None

def trigger_test_task():
    """Trigger a test post-processing task via API"""
    try:
        logger.info("🧪 Triggering test recovery via API...")
        
        # Check if there's a recovery endpoint
        response = requests.post("http://localhost:7000/api/admin/recovery/manual", json={})
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Recovery triggered: {result}")
            return result
        else:
            logger.warning(f"⚠️ Recovery endpoint returned: HTTP {response.status_code}")
            logger.warning(f"Response: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to trigger recovery: {e}", exc_info=True)
        return None

if __name__ == "__main__":
    print("🔍 Checking queue service status in running FastAPI app...")
    
    # Check queue status
    stats = check_queue_via_api()
    
    if stats and stats.get('is_running'):
        print("✅ Queue service is running - trying to trigger a test task...")
        trigger_test_task()
    else:
        print("❌ Queue service is not running in the FastAPI app!")
        print("This means the background queue initialization failed during startup.")
        
    print("🏁 Check completed")
