#!/usr/bin/env python3
"""
StreamVault Background Queue Fix Script

Fixes production issues:
1. Recording jobs stuck at 100% running
2. Orphaned recovery check running continuously  
3. Task names showing as "Unknown"

Usage:
  python fix_background_queue.py                # Run all fixes
  python fix_background_queue.py --stuck        # Fix only stuck recordings
  python fix_background_queue.py --orphaned     # Fix only orphaned recovery
  python fix_background_queue.py --names        # Fix only unknown task names
  python fix_background_queue.py --status       # Show current status
"""

import asyncio
import argparse
import sys
import json
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.background_queue_cleanup_service import get_cleanup_service
import logging

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fix_background_queue")


async def show_status():
    """Show current background queue status"""
    try:
        from app.services.background_queue_service import background_queue_service
        
        external_tasks = getattr(background_queue_service, 'external_tasks', {})
        active_tasks = getattr(background_queue_service, 'active_tasks', {})
        
        print(f"\n📊 BACKGROUND QUEUE STATUS")
        print(f"=" * 50)
        print(f"External tasks: {len(external_tasks)}")
        print(f"Active tasks: {len(active_tasks)}")
        
        # Check for issues
        stuck_recordings = []
        continuous_orphaned = []
        unknown_tasks = []
        
        # Check external tasks
        for task_id, task in external_tasks.items():
            if task_id.startswith('recording_') and task.progress >= 100 and task.status.value == 'running':
                stuck_recordings.append(task_id)
            
            if not task.task_type or task.task_type in ['unknown', '']:
                unknown_tasks.append(task_id)
        
        # Check active tasks
        for task_id, task in active_tasks.items():
            if task.task_type == 'orphaned_recovery_check':
                continuous_orphaned.append(task_id)
            
            if not task.task_type or task.task_type in ['unknown', '']:
                unknown_tasks.append(task_id)
        
        print(f"\n⚠️  ISSUES DETECTED:")
        print(f"Stuck recordings: {len(stuck_recordings)}")
        if stuck_recordings:
            for task_id in stuck_recordings[:5]:  # Show first 5
                print(f"  - {task_id}")
            if len(stuck_recordings) > 5:
                print(f"  ... and {len(stuck_recordings) - 5} more")
        
        print(f"Continuous orphaned recovery: {len(continuous_orphaned)}")
        if continuous_orphaned:
            for task_id in continuous_orphaned:
                print(f"  - {task_id}")
        
        print(f"Unknown task names: {len(unknown_tasks)}")
        if unknown_tasks:
            for task_id in unknown_tasks[:5]:  # Show first 5
                print(f"  - {task_id}")
            if len(unknown_tasks) > 5:
                print(f"  ... and {len(unknown_tasks) - 5} more")
        
        total_issues = len(stuck_recordings) + len(continuous_orphaned) + len(unknown_tasks)
        
        if total_issues == 0:
            print(f"\n✅ No issues detected!")
        else:
            print(f"\n🔧 Total issues: {total_issues}")
            print(f"   Run 'python fix_background_queue.py' to fix all issues")
        
        return total_issues
        
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return -1


async def main():
    parser = argparse.ArgumentParser(description="Fix StreamVault background queue issues")
    parser.add_argument("--stuck", action="store_true", help="Fix only stuck recording tasks")
    parser.add_argument("--orphaned", action="store_true", help="Fix only orphaned recovery checks")
    parser.add_argument("--names", action="store_true", help="Fix only unknown task names")
    parser.add_argument("--status", action="store_true", help="Show current status")
    
    args = parser.parse_args()
    
    print("🔧 StreamVault Background Queue Fix Tool")
    print("=" * 50)
    
    if args.status:
        await show_status()
        return
    
    cleanup_service = get_cleanup_service()
    
    if args.stuck:
        print("🧹 Fixing stuck recording tasks...")
        result = await cleanup_service.cleanup_stuck_recording_tasks()
        print(f"✅ Fixed {result.get('cleaned', 0)} stuck recording tasks")
        if result.get('errors'):
            print(f"❌ Errors: {result['errors']}")
    
    elif args.orphaned:
        print("🛑 Stopping continuous orphaned recovery...")
        result = await cleanup_service.stop_continuous_orphaned_recovery()
        print(f"✅ Stopped {result.get('stopped', 0)} orphaned recovery checks")
        if result.get('errors'):
            print(f"❌ Errors: {result['errors']}")
    
    elif args.names:
        print("🏷️  Fixing unknown task names...")
        result = await cleanup_service.fix_unknown_task_names()
        print(f"✅ Fixed {result.get('fixed', 0)} unknown task names")
        if result.get('errors'):
            print(f"❌ Errors: {result['errors']}")
    
    else:
        # Run comprehensive cleanup
        print("🧹 Running comprehensive background queue cleanup...")
        
        results = await cleanup_service.comprehensive_cleanup()
        
        print(f"\n📋 CLEANUP RESULTS:")
        print(f"=" * 30)
        
        if 'stuck_recordings' in results:
            sr = results['stuck_recordings']
            print(f"Stuck recordings fixed: {sr.get('cleaned', 0)}")
            if sr.get('errors'):
                print(f"  Errors: {sr['errors']}")
        
        if 'orphaned_recovery' in results:
            or_result = results['orphaned_recovery']
            print(f"Orphaned recovery stopped: {or_result.get('stopped', 0)}")
            if or_result.get('errors'):
                print(f"  Errors: {or_result['errors']}")
        
        if 'task_names' in results:
            tn = results['task_names']
            print(f"Task names fixed: {tn.get('fixed', 0)}")
            if tn.get('errors'):
                print(f"  Errors: {tn['errors']}")
        
        if 'summary' in results:
            summary = results['summary']
            total_fixed = summary.get('total_issues_fixed', 0)
            print(f"\n✅ TOTAL ISSUES FIXED: {total_fixed}")
        
        if results.get('error'):
            print(f"❌ Cleanup error: {results['error']}")
    
    print(f"\n🏁 Background queue fix completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n⏹️  Fix interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Fix failed: {e}")
        sys.exit(1)
