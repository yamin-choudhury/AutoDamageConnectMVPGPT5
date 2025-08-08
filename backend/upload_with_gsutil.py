#!/usr/bin/env python3
"""
Simple upload using gsutil CLI (after gcloud auth login)
"""

import os
import subprocess
from pathlib import Path

def upload_with_gsutil():
    """Upload using gsutil for maximum speed and reliability"""
    
    print("🚀 Starting gsutil upload to new bucket...")
    print("=" * 60)
    
    # Configuration
    local_data_dir = Path(__file__).parent / "bucket_backup" / "car-parts-catalogue-yc"
    new_bucket_name = "oem-parts-catalogue-yc"
    
    # Verify local data exists
    if not local_data_dir.exists():
        print(f"❌ Local data directory not found: {local_data_dir}")
        return False
    
    # Count local files
    local_files = list(local_data_dir.rglob("*.json"))
    print(f"📁 Found {len(local_files)} local files to upload")
    print(f"📁 Source: {local_data_dir}")
    print(f"📁 Destination: gs://{new_bucket_name}/")
    print()
    
    try:
        # Step 1: Create the bucket (if it doesn't exist)
        print("1. Creating bucket (if needed)...")
        create_cmd = ["gsutil", "mb", f"gs://{new_bucket_name}"]
        result = subprocess.run(create_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Bucket created: {new_bucket_name}")
        elif "already exists" in result.stderr.lower():
            print(f"✅ Bucket already exists: {new_bucket_name}")
        else:
            print(f"⚠️  Bucket creation result: {result.stderr}")
        
        # Step 2: Upload all files with gsutil rsync
        print("2. Starting bulk upload...")
        upload_cmd = [
            "gsutil", 
            "-m",  # Multi-threading for faster upload
            "rsync", 
            "-r",  # Recursive
            "-d",  # Delete extra files in destination
            str(local_data_dir),
            f"gs://{new_bucket_name}/"
        ]
        
        print(f"Running: {' '.join(upload_cmd)}")
        print("This may take several minutes for 32,482 files...")
        print()
        
        result = subprocess.run(upload_cmd, text=True)
        
        if result.returncode == 0:
            print("✅ Upload completed successfully!")
        else:
            print(f"❌ Upload failed with exit code: {result.returncode}")
            return False
        
        # Step 3: Verify upload
        print("3. Verifying upload...")
        verify_cmd = ["gsutil", "ls", "-l", f"gs://{new_bucket_name}/**/*.json"]
        result = subprocess.run(verify_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            uploaded_count = len(result.stdout.strip().split('\n')) - 1  # Subtract summary line
            print(f"✅ Verification: {uploaded_count} files in bucket")
            
            if uploaded_count >= len(local_files) * 0.95:  # Allow 5% tolerance
                print("✅ Upload verification successful!")
                
                # Create updated .env example
                create_env_example(new_bucket_name)
                
                return True
            else:
                print(f"⚠️  Upload may be incomplete: {uploaded_count} vs {len(local_files)} expected")
                return False
        else:
            print("⚠️  Could not verify upload (but may have succeeded)")
            return True
        
    except Exception as e:
        print(f"❌ Error during upload: {e}")
        return False

def create_env_example(bucket_name):
    """Create example .env file for new account"""
    
    # Get current project from gcloud
    try:
        result = subprocess.run(["gcloud", "config", "get-value", "project"], 
                              capture_output=True, text=True)
        current_project = result.stdout.strip() if result.returncode == 0 else "your-new-project-id"
    except:
        current_project = "your-new-project-id"
    
    env_content = f"""# Updated environment for new Google Cloud account
# After 'gcloud auth login' and 'gcloud config set project {current_project}'

GOOGLE_CLOUD_PROJECT={current_project}
PARTS_CATALOG_BUCKET={bucket_name}

# Note: GOOGLE_APPLICATION_CREDENTIALS not needed when using gcloud auth
# Keep your existing OpenAI key
OPENAI_API_KEY=your_openai_key_here
"""
    
    env_file = Path(__file__).parent.parent / ".env.new"
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print(f"📝 Created: {env_file}")
    print("   Update OPENAI_API_KEY and rename to .env when ready")

def main():
    """Main function"""
    print("⚠️  Make sure you've run 'gcloud auth login' with your NEW account first!")
    print()
    
    confirm = input("Have you authenticated with your new Google Cloud account? (y/n): ")
    if confirm.lower() != 'y':
        print("Please run: gcloud auth login")
        print("Then run this script again")
        return False
    
    # Ask for project ID to set
    project_id = input("Enter your new Google Cloud Project ID: ").strip()
    if project_id:
        print(f"Setting project to: {project_id}")
        subprocess.run(["gcloud", "config", "set", "project", project_id])
    
    return upload_with_gsutil()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
