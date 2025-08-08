#!/usr/bin/env python3
"""
Check download progress of bucket backup
"""

import os
from pathlib import Path

def check_progress():
    """Check how many files have been downloaded"""
    
    download_dir = Path(__file__).parent / "bucket_backup" / "car-parts-catalogue-yc"
    
    if not download_dir.exists():
        print("❌ Download directory doesn't exist yet")
        return
    
    # Count JSON files (the actual data files)
    json_files = list(download_dir.rglob("*.json"))
    total_expected = 32483
    
    progress = len(json_files) / total_expected * 100
    
    print(f"📊 Download Progress:")
    print(f"   Files downloaded: {len(json_files):,} / {total_expected:,}")
    print(f"   Progress: {progress:.1f}%")
    
    if len(json_files) > 0:
        # Show some sample files
        print(f"\n📁 Sample downloaded files:")
        for i, file in enumerate(json_files[:5]):
            relative_path = file.relative_to(download_dir)
            file_size = file.stat().st_size
            print(f"   {relative_path} ({file_size:,} bytes)")
        
        if len(json_files) > 5:
            print(f"   ... and {len(json_files) - 5:,} more files")
    
    # Check if summary file exists (indicates completion)
    summary_file = download_dir / "download_summary.json"
    if summary_file.exists():
        print(f"\n✅ Download completed! Summary available at: {summary_file}")
    else:
        print(f"\n⏳ Download still in progress...")

if __name__ == "__main__":
    check_progress()
