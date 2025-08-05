"""
Emergency Failed Recording Recovery Tool

Tool to recover failed recordings after segment files were accidentally cleaned.
"""

import asyncio
import traceback
from pathlib import Path
from app.database import SessionLocal
from app.models import Recording, Stream, Streamer
from app.services.recording.failed_recording_recovery_service import get_failed_recovery_service


async def emergency_recovery_check():
    """Check for failed recordings and attempt recovery"""
    print("🚨 EMERGENCY FAILED RECORDING RECOVERY CHECK")
    print("=" * 50)
    
    try:
        # Get the failed recovery service
        recovery_service = await get_failed_recovery_service()
        
        # First, let's see what failed recordings we have
        with SessionLocal() as db:
            failed_recordings = (
                db.query(Recording)
                .join(Stream)
                .join(Streamer)
                .filter(Recording.status == 'failed')
                .all()
            )
            
            print(f"Found {len(failed_recordings)} failed recordings:")
            
            for recording in failed_recordings:
                streamer_name = recording.stream.streamer.username if recording.stream and recording.stream.streamer else "Unknown"
                print(f"\n📹 Recording {recording.id}: {streamer_name}")
                print(f"   Path: {recording.path}")
                print(f"   Status: {recording.status}")
                print(f"   Created: {recording.created_at}")
                
                # Check if file exists
                if recording.path:
                    file_exists = Path(recording.path).exists()
                    print(f"   File exists: {file_exists}")
                    
                    # Check for segment directory
                    original_path = Path(recording.path)
                    segments_dir = original_path.parent / f"{original_path.stem}_segments"
                    segments_exist = segments_dir.exists()
                    print(f"   Segments dir exists: {segments_exist}")
                    
                    if segments_exist:
                        ts_files = list(segments_dir.glob("*.ts"))
                        print(f"   Segments found: {len(ts_files)}")
                        
                        if ts_files:
                            print("   ✅ RECOVERABLE - Has segment files!")
                            
                            # Attempt recovery
                            print(f"   🔧 Attempting recovery for recording {recording.id}...")
                            result = await recovery_service.recover_specific_recording(recording.id)
                            
                            if isinstance(result, dict) and "success" in result:
                                if result["success"]:
                                    print(f"   ✅ Recovery triggered successfully!")
                                    print(f"   📁 Segments found: {result.get('segments_found', 'N/A')}")
                                    print(f"   📂 Segments dir: {result.get('segments_dir', 'N/A')}")
                                else:
                                    print(f"   ❌ Recovery failed: {result.get('error', 'Unknown error')}")
                            else:
                                print(f"   ❌ Unexpected result structure from recovery service: {result}")
                        else:
                            print("   ❌ No segment files found")
                    else:
                        print("   ❌ No segments directory found")
                        
                        # Check if there are any leftover segment files in the parent directory
                        parent_dir = original_path.parent
                        if parent_dir.exists():
                            possible_segments = list(parent_dir.glob(f"{original_path.stem}*_segments"))
                            if possible_segments:
                                print(f"   🔍 Found possible segment dirs: {possible_segments}")
                else:
                    print("   ❌ No path set")
        
        print("\n🔧 Running general failed recording scan...")
        result = await recovery_service.scan_and_recover_failed_recordings(dry_run=True)
        
        print(f"\nScan Results:")
        print(f"  Failed recordings found: {result['failed_found']}")
        print(f"  Recoverable recordings: {result['recoverable_found']}")
        print(f"  Would trigger recovery: {result['recovery_triggered']}")
        print(f"  Skipped (no segments): {result['skipped_no_segments']}")
        
        if result['recoverable_found'] > 0:
            print(f"\n✅ Found {result['recoverable_found']} recoverable recordings!")
            answer = input("Do you want to trigger recovery? (y/N): ")
            if answer.lower() == 'y':
                print("🔧 Triggering recovery...")
                actual_result = await recovery_service.scan_and_recover_failed_recordings(dry_run=False)
                print(f"Recovery triggered: {actual_result['recovery_triggered']}")
                print(f"Recovery failed: {actual_result['recovery_failed']}")
        else:
            print("❌ No recoverable recordings found")
            
    except Exception as e:
        print(f"❌ Error during emergency recovery: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(emergency_recovery_check())
