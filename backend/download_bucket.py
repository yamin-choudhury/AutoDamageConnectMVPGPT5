#!/usr/bin/env python3
"""
Download entire car-parts-catalogue-yc bucket locally for backup/transfer
"""

import os
import json
import shutil
from pathlib import Path
from google.cloud import storage
from dotenv import load_dotenv
from tqdm import tqdm

def download_bucket():
    """Download all files from the car-parts-catalogue-yc bucket"""
    
    print("🔄 Starting bucket download...")
    print("=" * 60)
    
    # Load environment variables
    env_paths = [
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env"
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loading env from: {env_path}")
            break
    
    # Check required environment variables
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    bucket_name = os.getenv("PARTS_CATALOG_BUCKET")
    
    if not project_id or not bucket_name:
        print("❌ Missing environment variables:")
        print("   - GOOGLE_CLOUD_PROJECT")
        print("   - PARTS_CATALOG_BUCKET")
        return False
    
    print(f"Project: {project_id}")
    print(f"Bucket: {bucket_name}")
    
    # Create local download directory
    download_dir = Path(__file__).parent / "bucket_backup" / bucket_name
    download_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Download directory: {download_dir}")
    
    try:
        # Initialize Google Cloud Storage client
        client = storage.Client(project=project_id)
        bucket = client.bucket(bucket_name)
        
        # Get list of all blobs in bucket
        print("\n🔍 Discovering all files in bucket...")
        all_blobs = list(bucket.list_blobs())
        total_files = len(all_blobs)
        
        if total_files == 0:
            print("❌ Bucket appears to be empty")
            return False
        
        print(f"Found {total_files} files to download")
        
        # Download all files with progress bar
        print("\n⬇️  Downloading files...")
        downloaded = 0
        skipped = 0
        errors = 0
        
        with tqdm(total=total_files, unit="files") as pbar:
            for blob in all_blobs:
                try:
                    # Create local file path
                    local_file_path = download_dir / blob.name
                    
                    # Create parent directories if they don't exist
                    local_file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Skip if file already exists and has same size
                    if local_file_path.exists() and local_file_path.stat().st_size == blob.size:
                        skipped += 1
                        pbar.set_description(f"Skipped: {blob.name}")
                    else:
                        # Download the file
                        blob.download_to_filename(str(local_file_path))
                        downloaded += 1
                        pbar.set_description(f"Downloaded: {blob.name}")
                    
                    pbar.update(1)
                    
                except Exception as e:
                    errors += 1
                    print(f"\n❌ Error downloading {blob.name}: {e}")
                    pbar.update(1)
        
        print(f"\n✅ Download complete!")
        print(f"   Downloaded: {downloaded} files")
        print(f"   Skipped: {skipped} files (already exist)")
        print(f"   Errors: {errors} files")
        
        # Generate summary report
        summary_file = download_dir / "download_summary.json"
        summary = {
            "bucket_name": bucket_name,
            "project_id": project_id,
            "total_files": total_files,
            "downloaded": downloaded,
            "skipped": skipped,
            "errors": errors,
            "download_directory": str(download_dir.absolute())
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"📊 Summary saved to: {summary_file}")
        
        # Analyze bucket structure
        print("\n📁 Analyzing bucket structure...")
        analyze_structure(download_dir)
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to download bucket: {e}")
        return False

def analyze_structure(download_dir: Path):
    """Analyze the downloaded bucket structure"""
    
    structure = {}
    total_size = 0
    file_count = 0
    
    for item in download_dir.rglob('*'):
        if item.is_file():
            file_count += 1
            size = item.stat().st_size
            total_size += size
            
            # Track directory structure
            relative_path = item.relative_to(download_dir)
            parts = relative_path.parts
            
            if len(parts) >= 2 and parts[0] == "manufacturers":
                manufacturer_id = parts[1]
                if manufacturer_id not in structure:
                    structure[manufacturer_id] = {
                        "files": 0,
                        "size_mb": 0,
                        "types": set()
                    }
                
                structure[manufacturer_id]["files"] += 1
                structure[manufacturer_id]["size_mb"] += size / (1024 * 1024)
                
                if item.name.endswith('.json'):
                    if item.name == 'models.json':
                        structure[manufacturer_id]["types"].add("models")
                    elif item.name.startswith('articles_'):
                        structure[manufacturer_id]["types"].add("articles")
    
    print(f"Total files: {file_count}")
    print(f"Total size: {total_size / (1024 * 1024):.2f} MB")
    print(f"Manufacturers found: {len(structure)}")
    
    # Show top 10 manufacturers by file count
    sorted_manufacturers = sorted(
        structure.items(), 
        key=lambda x: x[1]["files"], 
        reverse=True
    )[:10]
    
    print("\n🏭 Top manufacturers by file count:")
    for manufacturer_id, info in sorted_manufacturers:
        types_str = ", ".join(info["types"])
        print(f"   {manufacturer_id}: {info['files']} files, {info['size_mb']:.1f}MB ({types_str})")
    
    # Save structure analysis
    structure_file = download_dir / "structure_analysis.json"
    
    # Convert sets to lists for JSON serialization
    structure_serializable = {}
    for key, value in structure.items():
        structure_serializable[key] = {
            "files": value["files"],
            "size_mb": round(value["size_mb"], 2),
            "types": list(value["types"])
        }
    
    analysis = {
        "total_files": file_count,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "manufacturers": structure_serializable
    }
    
    with open(structure_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"📊 Structure analysis saved to: {structure_file}")

def create_upload_script(download_dir: Path):
    """Create a script to upload the data to a new bucket"""
    
    upload_script = download_dir / "upload_to_new_bucket.py"
    
    script_content = f'''#!/usr/bin/env python3
"""
Upload downloaded bucket data to a new Google Cloud bucket
"""

import os
from pathlib import Path
from google.cloud import storage
from dotenv import load_dotenv
from tqdm import tqdm

def upload_to_new_bucket():
    """Upload all files to a new bucket"""
    
    # Load environment variables for NEW account
    load_dotenv()
    
    # Get new bucket details
    new_project_id = input("Enter your new Google Cloud Project ID: ")
    new_bucket_name = input("Enter your new bucket name (e.g., car-parts-catalogue-new): ")
    
    if not new_project_id or not new_bucket_name:
        print("❌ Project ID and bucket name are required")
        return False
    
    # Initialize client with new project
    client = storage.Client(project=new_project_id)
    
    # Create or get bucket
    try:
        bucket = client.bucket(new_bucket_name)
        if not bucket.exists():
            bucket = client.create_bucket(new_bucket_name)
            print(f"✅ Created new bucket: {{new_bucket_name}}")
        else:
            print(f"✅ Using existing bucket: {{new_bucket_name}}")
    except Exception as e:
        print(f"❌ Failed to create/access bucket: {{e}}")
        return False
    
    # Upload all files
    data_dir = Path("{str(download_dir.absolute())}")
    all_files = list(data_dir.rglob('*.json'))
    
    print(f"Found {{len(all_files)}} files to upload")
    
    uploaded = 0
    with tqdm(total=len(all_files), unit="files") as pbar:
        for local_file in all_files:
            try:
                # Calculate relative path from data directory
                relative_path = local_file.relative_to(data_dir)
                blob_name = str(relative_path)
                
                # Upload file
                blob = bucket.blob(blob_name)
                blob.upload_from_filename(str(local_file))
                
                uploaded += 1
                pbar.set_description(f"Uploaded: {{blob_name}}")
                pbar.update(1)
                
            except Exception as e:
                print(f"\\n❌ Error uploading {{local_file}}: {{e}}")
                pbar.update(1)
    
    print(f"\\n✅ Upload complete! Uploaded {{uploaded}} files to {{new_bucket_name}}")
    print(f"\\nUpdate your .env file with:")
    print(f"GOOGLE_CLOUD_PROJECT={{new_project_id}}")
    print(f"PARTS_CATALOG_BUCKET={{new_bucket_name}}")
    
    return True

if __name__ == "__main__":
    upload_to_new_bucket()
'''
    
    with open(upload_script, 'w') as f:
        f.write(script_content)
    
    # Make script executable
    upload_script.chmod(0o755)
    
    print(f"📤 Upload script created: {upload_script}")

if __name__ == "__main__":
    success = download_bucket()
    
    if success:
        download_dir = Path(__file__).parent / "bucket_backup" / os.getenv("PARTS_CATALOG_BUCKET", "car-parts-catalogue-yc")
        create_upload_script(download_dir)
        
        print("\n" + "=" * 60)
        print("🎉 Bucket download complete!")
        print(f"📁 Data saved to: {download_dir.absolute()}")
        print("\n📋 Next steps:")
        print("1. Create a new Google Cloud account/project")
        print("2. Create a new bucket in the new project")
        print("3. Run the generated upload script to transfer data")
        print("4. Update your .env file with new credentials")
        print("\n💡 The upload script will guide you through the transfer process.")
    
    exit(0 if success else 1)
