#!/usr/bin/env python3
"""
Test script to verify metadata generation for the most recent stream
"""
import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, '/home/maxe/Dokumente/private_projects/StreamVault')

from app.services.metadata_service import MetadataService
from app.database import SessionLocal
from app.models import Stream, Streamer, StreamEvent, StreamMetadata
from datetime import datetime

async def test_metadata_generation():
    """Test metadata generation for the most recent stream"""
    
    print("=== StreamVault Metadata Generation Test ===\n")
    
    # Create metadata service
    service = MetadataService()
    
    try:
        with SessionLocal() as db:
            # Find the most recent stream
            stream = db.query(Stream).order_by(Stream.id.desc()).first()
            
            if not stream:
                print("❌ No streams found in database")
                return False
            
            print(f"📺 Testing stream: {stream.id}")
            print(f"   Title: {stream.title}")
            print(f"   Started: {stream.started_at}")
            print(f"   Ended: {stream.ended_at}")
            print(f"   Recording path: {stream.recording_path}")
            
            if not stream.recording_path:
                print("❌ No recording path found for stream")
                return False
            
            if not os.path.exists(stream.recording_path):
                print(f"❌ Recording file does not exist: {stream.recording_path}")
                return False
            
            print(f"✅ Recording file exists: {os.path.getsize(stream.recording_path)} bytes\n")
            
            # Check events
            events = db.query(StreamEvent).filter(StreamEvent.stream_id == stream.id).all()
            print(f"📅 Found {len(events)} events for stream:")
            for event in events:
                print(f"   - {event.event_type}: {event.title} ({event.category_name}) at {event.timestamp}")
            
            if not events:
                print("⚠️  No events found, will create minimal event")
            
            print("\n🔄 Generating metadata...")
            
            # Generate metadata
            result = await service.generate_metadata_for_stream(stream.id, stream.recording_path)
            
            print(f"📊 Metadata generation result: {result}\n")
            
            # Check what files were created
            base_path = Path(stream.recording_path).parent
            base_filename = Path(stream.recording_path).stem
            
            expected_files = {
                "JSON": base_path / f"{base_filename}.info.json",
                "NFO": base_path / f"{base_filename}.nfo", 
                "VTT": base_path / f"{base_filename}.vtt",
                "SRT": base_path / f"{base_filename}.srt",
                "FFmpeg Chapters": base_path / f"{base_filename}-ffmpeg-chapters.txt",
                "XML": base_path / f"{base_filename}.xml",
                "Thumbnail": base_path / f"{base_filename}_thumbnail.jpg"
            }
            
            print("📁 Checking generated files:")
            for file_type, file_path in expected_files.items():
                if file_path.exists():
                    size = file_path.stat().st_size
                    print(f"   ✅ {file_type}: {file_path.name} ({size} bytes)")
                    
                    # Show content preview for small text files
                    if file_type in ["VTT", "SRT", "FFmpeg Chapters", "XML"] and size < 1000:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                print(f"      Content: {content[:100]}...")
                        except Exception as e:
                            print(f"      Error reading content: {e}")
                else:
                    print(f"   ❌ {file_type}: {file_path.name} (missing)")
            
            # Check metadata in database
            print("\n💾 Checking database metadata:")
            metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream.id).first()
            if metadata:
                print(f"   ✅ StreamMetadata entry exists")
                print(f"      JSON path: {metadata.json_path}")
                print(f"      NFO path: {metadata.nfo_path}")
                print(f"      Thumbnail path: {metadata.thumbnail_path}")
                print(f"      VTT chapters: {metadata.chapters_vtt_path}")
                print(f"      SRT chapters: {metadata.chapters_srt_path}")
                print(f"      FFmpeg chapters: {metadata.chapters_ffmpeg_path}")
            else:
                print("   ❌ No StreamMetadata entry found")
            
            return result
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await service.close()

if __name__ == "__main__":
    result = asyncio.run(test_metadata_generation())
    print(f"\n🏁 Test completed with result: {result}")
    sys.exit(0 if result else 1)
