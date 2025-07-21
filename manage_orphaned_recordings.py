#!/usr/bin/env python3
"""
StreamVault Orphaned Recovery CLI Tool

This tool helps manage orphaned .ts recordings that need post-processing.
Database-driven approach with event-based recovery triggering.
"""

import asyncio
import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service


async def show_statistics(max_age_hours: int = 168):
    """Show statistics about orphaned recordings"""
    print(f"🔍 Scanning for orphaned recordings (max age: {max_age_hours} hours)...")
    
    recovery_service = await get_orphaned_recovery_service()
    stats = await recovery_service.get_orphaned_statistics(max_age_hours)
    
    print("\n📊 ORPHANED RECORDINGS STATISTICS")
    print("=" * 50)
    print(f"Total orphaned recordings: {stats.get('total_orphaned', 0)}")
    print(f"Total size: {stats.get('total_size_gb', 0):.2f} GB ({stats.get('total_size_bytes', 0):,} bytes)")
    
    # Show segment statistics if available
    total_segments = stats.get('total_orphaned_segments', 0)
    if total_segments > 0:
        segments_size_gb = stats.get('total_segments_size_gb', 0)
        segments_size_bytes = stats.get('total_segments_size_bytes', 0)
        print(f"Orphaned segment directories: {total_segments}")
        print(f"Segments size: {segments_size_gb:.2f} GB ({segments_size_bytes:,} bytes)")
        print(f"Total combined size: {(stats.get('total_size_gb', 0) + segments_size_gb):.2f} GB")
    
    if stats.get('oldest_recording'):
        print(f"Oldest recording: {stats['oldest_recording']}")
    if stats.get('newest_recording'):
        print(f"Newest recording: {stats['newest_recording']}")
    
    by_streamer = stats.get('by_streamer', {})
    if by_streamer:
        print("\n📺 BY STREAMER:")
        print("-" * 50)
        for streamer, data in sorted(by_streamer.items(), key=lambda x: x[1]['count'], reverse=True):
            size_gb = data['size'] / (1024**3)
            line = f"  {streamer}: {data['count']} recordings, {size_gb:.2f} GB"
            
            # Add segment info if available
            if data.get('segments', 0) > 0:
                segments_size_gb = data.get('segments_size', 0) / (1024**3)
                line += f" + {data['segments']} segment dirs ({segments_size_gb:.2f} GB)"
            
            print(line)
    
    if stats.get('error'):
        print(f"\n❌ Error: {stats['error']}")


async def scan_recordings(max_age_hours: int = 48, dry_run: bool = False, segments_only: bool = False):
    """Scan and optionally recover orphaned recordings"""
    if segments_only:
        action = "Scanning segment directories" if dry_run else "Cleaning segment directories"
        print(f"🧹 {action} (max age: {max_age_hours} hours)...")
        
        recovery_service = await get_orphaned_recovery_service()
        result = await recovery_service.scan_and_recover_orphaned_recordings(
            max_age_hours=max_age_hours,
            dry_run=dry_run,
            cleanup_segments=True
        )
        
        # Only show segment cleanup results
        segments_cleaned = result.get('segments_cleaned', 0)
        segments_failed = result.get('segments_cleanup_failed', 0)
        segments_list = result.get('segments_cleaned_list', [])
        
        print(f"\n🧹 SEGMENT CLEANUP RESULTS")
        print("=" * 40)
        print(f"Segment directories found: {len(segments_list)}")
        print(f"Segment directories cleaned: {segments_cleaned}")
        if segments_failed > 0:
            print(f"Cleanup failed: {segments_failed}")
        
        if segments_list:
            print(f"\n🗂️  SEGMENT DIRECTORIES ({len(segments_list)}):")
            print("-" * 50)
            for segment in segments_list:
                status = "✅ Cleaned" if segment['cleanup_triggered'] else "🔍 Found"
                if segment.get('error'):
                    status = f"❌ Error: {segment['error']}"
                
                size_key = 'size_cleaned' if segment.get('cleanup_triggered') else 'size_would_clean'
                size_mb = segment.get(size_key, 0) / (1024**2) if segment.get(size_key) else 0
                
                print(f"  {status}")
                print(f"    Streamer: {segment['streamer_name']}")
                print(f"    Directory: {segment['segments_dir']}")
                print(f"    Size: {size_mb:.1f} MB | Recording ID: {segment['recording_id']}")
                print()
        
        return
    
    # Regular orphaned recordings scan
    action = "Scanning" if dry_run else "Recovering"
    print(f"🔍 {action} orphaned recordings (max age: {max_age_hours} hours)...")
    
    recovery_service = await get_orphaned_recovery_service()
    result = await recovery_service.scan_and_recover_orphaned_recordings(
        max_age_hours=max_age_hours,
        dry_run=dry_run
    )
    
    print("\n📋 SCAN RESULTS")
    print("=" * 40)
    print(f"Scanned recordings: {result['scanned_recordings']}")
    print(f"Orphaned found: {result['orphaned_found']}")
    print(f"Recovery triggered: {result['recovery_triggered']}")
    print(f"Recovery failed: {result['recovery_failed']}")
    print(f"Skipped (missing files): {result['skipped_missing_files']}")
    print(f"Skipped (too recent): {result['skipped_recent']}")
    
    # Show segment cleanup results if available
    segments_cleaned = result.get('segments_cleaned', 0)
    segments_failed = result.get('segments_cleanup_failed', 0)
    if segments_cleaned > 0 or segments_failed > 0 or result.get('segments_cleaned_list'):
        print(f"Segment directories cleaned: {segments_cleaned}")
        if segments_failed > 0:
            print(f"Segment cleanup failed: {segments_failed}")
        
        # Show cleaned segments
        if result.get('segments_cleaned_list'):
            print(f"\n🧹 SEGMENT CLEANUP ({len(result['segments_cleaned_list'])}):")
            print("-" * 50)
            for segment in result['segments_cleaned_list']:
                status = "✅ Cleaned" if segment['cleanup_triggered'] else "🔍 Found"
                if segment.get('error'):
                    status = f"❌ Error: {segment['error']}"
                
                size_key = 'size_cleaned' if segment.get('cleanup_triggered') else 'size_would_clean'
                size_mb = segment.get(size_key, 0) / (1024**2) if segment.get(size_key) else 0
                
                print(f"  {status}")
                print(f"    Streamer: {segment['streamer_name']}")
                print(f"    Directory: {segment['segments_dir']}")
                print(f"    Size: {size_mb:.1f} MB | Recording ID: {segment['recording_id']}")
                print()
    
    if result['errors']:
        print(f"\n❌ ERRORS ({len(result['errors'])}):")
        for error in result['errors']:
            print(f"  - {error}")
    
    if result['orphaned_recordings']:
        print(f"\n📁 ORPHANED RECORDINGS ({len(result['orphaned_recordings'])}):")
        print("-" * 50)
        for orphaned in result['orphaned_recordings']:
            status = "✅ Recovered" if orphaned['recovery_triggered'] else "⏸️  Found"
            if orphaned.get('error'):
                status = f"❌ Error: {orphaned['error']}"
            
            size_mb = orphaned.get('file_size', 0) / (1024**2) if orphaned.get('file_size') else 0
            created = orphaned.get('created_at', 'Unknown')
            
            print(f"  {status}")
            print(f"    ID: {orphaned['recording_id']} | Streamer: {orphaned['streamer_name']}")
            print(f"    File: {orphaned['file_path']}")
            print(f"    Size: {size_mb:.1f} MB | Created: {created}")
            print()


async def recover_specific(recording_id: int):
    """Recover a specific recording by ID"""
    print(f"🎯 Recovering specific recording: {recording_id}")
    
    try:
        recovery_service = await get_orphaned_recovery_service()
        
        # Get recording details
        from app.database import SessionLocal
        from app.models import Recording
        
        with SessionLocal() as db:
            recording = db.query(Recording).filter(Recording.id == recording_id).first()
            if not recording:
                print(f"❌ Recording {recording_id} not found")
                return False
            
            print(f"📁 Found recording: {recording.path}")
            
            # Validate it's orphaned
            validation = await recovery_service._validate_orphaned_recording(recording)
            if not validation["valid"]:
                print(f"❌ Recording is not suitable for recovery: {validation['reason']}")
                return False
            
            print(f"✅ Recording is valid for recovery")
            print(f"   File size: {validation.get('file_size', 0) / (1024**2):.1f} MB")
            print(f"   File age: {validation.get('file_age_seconds', 0) / 3600:.1f} hours")
            
            # Trigger recovery
            success = await recovery_service._trigger_orphaned_recovery(recording, db)
            
            if success:
                print(f"✅ Recovery triggered successfully for recording {recording_id}")
                return True
            else:
                print(f"❌ Failed to trigger recovery for recording {recording_id}")
                return False
                
    except Exception as e:
        print(f"❌ Error recovering recording {recording_id}: {e}")
        return False


async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="StreamVault Orphaned Recording Recovery Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s stats                    # Show statistics about orphaned recordings
  %(prog)s stats --max-age 72       # Show stats for recordings up to 72 hours old
  %(prog)s scan --dry-run           # Scan without recovering
  %(prog)s scan --max-age 24        # Scan and recover recordings up to 24 hours old
  %(prog)s recover --id 123         # Recover specific recording ID 123
  %(prog)s cleanup-segments         # Clean up orphaned segment directories
  %(prog)s cleanup-segments --dry-run  # Show what segment dirs would be cleaned
        """
    )
    
    parser.add_argument('action', choices=['stats', 'scan', 'recover', 'cleanup-segments'], 
                       help='Action to perform')
    parser.add_argument('--max-age', type=int, default=48,
                       help='Maximum age in hours for recordings to process (default: 48)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without actually doing it')
    parser.add_argument('--id', type=int,
                       help='Specific recording ID to recover')
    parser.add_argument('--interactive', action='store_true',
                       help='Interactive mode with prompts')
    parser.add_argument('--json', action='store_true',
                       help='Output results in JSON format')
    
    args = parser.parse_args()
    
    if not args.json:
        print("🎬 StreamVault Orphaned Recovery Tool")
        print("=" * 50)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()
    
    try:
        if args.action == 'stats':
            if args.json:
                recovery_service = await get_orphaned_recovery_service()
                stats = await recovery_service.get_orphaned_statistics(args.max_age)
                print(json.dumps(stats, indent=2, default=str))
            else:
                await show_statistics(args.max_age)
                
        elif args.action == 'scan':
            if args.json:
                recovery_service = await get_orphaned_recovery_service()
                result = await recovery_service.scan_and_recover_orphaned_recordings(
                    max_age_hours=args.max_age,
                    dry_run=args.dry_run
                )
                print(json.dumps(result, indent=2, default=str))
            else:
                await scan_recordings(args.max_age, args.dry_run)
                
        elif args.action == 'cleanup-segments':
            if args.json:
                recovery_service = await get_orphaned_recovery_service()
                result = await recovery_service.scan_and_recover_orphaned_recordings(
                    max_age_hours=args.max_age,
                    dry_run=args.dry_run,
                    cleanup_segments=True
                )
                print(json.dumps(result, indent=2, default=str))
            else:
                await scan_recordings(args.max_age, args.dry_run, segments_only=True)
                
        elif args.action == 'recover':
            if not args.id:
                print("❌ Error: --id is required for recover action")
                sys.exit(1)
            
            success = await recover_specific(args.id)
            if not success:
                sys.exit(1)
        
        if not args.json:
            print("\n✅ Operation completed successfully")
        
    except KeyboardInterrupt:
        print("\n⏸️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
