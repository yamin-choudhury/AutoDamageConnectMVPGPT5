#!/usr/bin/env python3
"""
Direct bucket-to-bucket transfer without downloading locally
Requires billing enabled on source account but transfers directly to new account
"""

import os
from google.cloud import storage
from dotenv import load_dotenv
from tqdm import tqdm

def direct_bucket_transfer():
    """Transfer files directly between buckets without local download"""
    
    print("🔄 Direct Bucket Transfer (No Local Download)")
    print("=" * 60)
    
    # Load environment for SOURCE account
    load_dotenv()
    
    # Source account details
    source_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    source_bucket_name = os.getenv("PARTS_CATALOG_BUCKET")
    
    if not source_project or not source_bucket_name:
        print("❌ Source account credentials missing")
        return False
    
    # Get destination account details
    dest_project = input("Enter DESTINATION Google Cloud Project ID: ")
    dest_bucket_name = input("Enter DESTINATION bucket name: ")
    dest_creds_path = input("Enter path to DESTINATION service account JSON: ")
    
    if not all([dest_project, dest_bucket_name, dest_creds_path]):
        print("❌ All destination details required")
        return False
    
    try:
        # Initialize source client (current account)
        source_client = storage.Client(project=source_project)
        source_bucket = source_client.bucket(source_bucket_name)
        
        # Initialize destination client (new account)
        dest_client = storage.Client.from_service_account_json(
            dest_creds_path, 
            project=dest_project
        )
        dest_bucket = dest_client.bucket(dest_bucket_name)
        
        # Create destination bucket if it doesn't exist
        if not dest_bucket.exists():
            dest_bucket = dest_client.create_bucket(dest_bucket_name)
            print(f"✅ Created destination bucket: {dest_bucket_name}")
        
        # Get all source files
        print("🔍 Discovering files in source bucket...")
        all_blobs = list(source_bucket.list_blobs())
        total_files = len(all_blobs)
        
        print(f"Found {total_files} files to transfer")
        
        # Transfer files directly
        print("🚀 Starting direct transfer...")
        
        transferred = 0
        errors = 0
        
        with tqdm(total=total_files, unit="files") as pbar:
            for source_blob in all_blobs:
                try:
                    # Copy blob directly to destination bucket
                    dest_blob = dest_bucket.blob(source_blob.name)
                    
                    # Copy the blob data
                    dest_blob.upload_from_string(
                        source_blob.download_as_bytes(),
                        content_type=source_blob.content_type
                    )
                    
                    transferred += 1
                    pbar.set_description(f"Transferred: {source_blob.name}")
                    
                except Exception as e:
                    errors += 1
                    print(f"\n❌ Error transferring {source_blob.name}: {e}")
                
                pbar.update(1)
        
        print(f"\n✅ Transfer complete!")
        print(f"   Transferred: {transferred} files")
        print(f"   Errors: {errors} files")
        
        print(f"\n🔧 Update your .env file:")
        print(f"GOOGLE_CLOUD_PROJECT={dest_project}")
        print(f"PARTS_CATALOG_BUCKET={dest_bucket_name}")
        print(f"GOOGLE_APPLICATION_CREDENTIALS={dest_creds_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Transfer failed: {e}")
        return False

if __name__ == "__main__":
    print("⚠️  IMPORTANT: This requires billing enabled on source account")
    print("   (but transfers directly to new account without local download)")
    print()
    
    confirm = input("Continue? (y/n): ")
    if confirm.lower() == 'y':
        direct_bucket_transfer()
    else:
        print("Transfer cancelled")
