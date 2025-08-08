#!/usr/bin/env python3
"""
Upload locally downloaded catalog data to new Google Cloud bucket
"""

import os
import json
import time
from pathlib import Path
from google.cloud import storage
from tqdm import tqdm
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('upload_to_new_bucket.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BucketUploader:
    def __init__(self):
        self.local_data_dir = Path(__file__).parent / "bucket_backup" / "car-parts-catalogue-yc"
        
        # Verify local data exists
        if not self.local_data_dir.exists():
            raise FileNotFoundError(f"Local data directory not found: {self.local_data_dir}")
        
        # New bucket details
        self.new_project_id = None
        self.new_bucket_name = "oem-parts-catalogue-yc"
        self.new_credentials_path = None
        
        logger.info(f"Local data directory: {self.local_data_dir}")
    
    def setup_new_account(self):
        """Get new account details from user"""
        print("🔧 Setting up new Google Cloud account...")
        print()
        
        # Get new project ID
        self.new_project_id = input("Enter your NEW Google Cloud Project ID: ").strip()
        if not self.new_project_id:
            raise ValueError("Project ID is required")
        
        # Get credentials path
        self.new_credentials_path = input("Enter path to NEW service account JSON file: ").strip()
        if not self.new_credentials_path or not Path(self.new_credentials_path).exists():
            raise FileNotFoundError("Valid credentials file path is required")
        
        print(f"✅ Project ID: {self.new_project_id}")
        print(f"✅ Credentials: {self.new_credentials_path}")
        print(f"✅ New bucket: {self.new_bucket_name}")
        print()
    
    def initialize_client(self):
        """Initialize Google Cloud Storage client with new credentials"""
        try:
            self.client = storage.Client.from_service_account_json(
                self.new_credentials_path,
                project=self.new_project_id
            )
            
            # Get or create the bucket
            self.bucket = self.client.bucket(self.new_bucket_name)
            
            if not self.bucket.exists():
                print(f"Creating new bucket: {self.new_bucket_name}")
                self.bucket = self.client.create_bucket(self.new_bucket_name)
                logger.info(f"Created bucket: {self.new_bucket_name}")
            else:
                logger.info(f"Using existing bucket: {self.new_bucket_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            return False
    
    def get_local_files(self):
        """Get list of all local files to upload"""
        local_files = list(self.local_data_dir.rglob("*.json"))
        logger.info(f"Found {len(local_files)} local files to upload")
        return local_files
    
    def upload_file_with_retry(self, local_file, max_retries=3):
        """Upload a single file with retry logic"""
        # Calculate the blob name (relative path from data directory)
        relative_path = local_file.relative_to(self.local_data_dir)
        blob_name = str(relative_path)
        
        for attempt in range(max_retries):
            try:
                # Upload the file
                blob = self.bucket.blob(blob_name)
                blob.upload_from_filename(str(local_file))
                
                return True
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {blob_name}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait 2 seconds before retry
                else:
                    logger.error(f"Failed to upload {blob_name} after {max_retries} attempts")
                    return False
        
        return False
    
    def upload_all_files(self):
        """Upload all local files to the new bucket"""
        local_files = self.get_local_files()
        
        if not local_files:
            logger.error("No local files found to upload")
            return False
        
        print(f"📤 Starting upload of {len(local_files)} files...")
        print(f"   Source: {self.local_data_dir}")
        print(f"   Destination: gs://{self.new_bucket_name}/")
        print()
        
        successful = 0
        failed = 0
        
        with tqdm(total=len(local_files), unit="files") as pbar:
            for local_file in local_files:
                if self.upload_file_with_retry(local_file):
                    successful += 1
                else:
                    failed += 1
                
                pbar.update(1)
                pbar.set_description(f"Uploaded: {successful}, Failed: {failed}")
                
                # Small delay to be nice to the API
                time.sleep(0.1)
        
        logger.info(f"📊 Upload complete!")
        logger.info(f"   Successful: {successful}")
        logger.info(f"   Failed: {failed}")
        
        return failed == 0
    
    def verify_upload(self):
        """Verify all files were uploaded correctly"""
        logger.info("🔍 Verifying upload completeness...")
        
        try:
            # Count files in bucket
            bucket_files = list(self.bucket.list_blobs())
            json_files = [b for b in bucket_files if b.name.endswith('.json')]
            
            # Count local files
            local_files = self.get_local_files()
            
            logger.info(f"Local files: {len(local_files)}")
            logger.info(f"Bucket files: {len(json_files)}")
            
            if len(json_files) >= len(local_files):
                logger.info("✅ Upload verification successful!")
                return True
            else:
                logger.warning(f"❌ Upload incomplete - missing {len(local_files) - len(json_files)} files")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying upload: {e}")
            return False
    
    def create_new_env_file(self):
        """Create new .env file with updated credentials"""
        new_env_content = f"""# Updated environment for new Google Cloud account
GOOGLE_APPLICATION_CREDENTIALS={self.new_credentials_path}
GOOGLE_CLOUD_PROJECT={self.new_project_id}
PARTS_CATALOG_BUCKET={self.new_bucket_name}

# Keep your existing OpenAI key
OPENAI_API_KEY=your_openai_key_here
"""
        
        env_file = Path(__file__).parent.parent / ".env.new"
        with open(env_file, 'w') as f:
            f.write(new_env_content)
        
        print(f"📝 Created new environment file: {env_file}")
        print("   Update OPENAI_API_KEY and rename to .env when ready")

def main():
    """Main upload function"""
    print("🚀 Starting upload to new Google Cloud bucket...")
    print()
    
    try:
        uploader = BucketUploader()
        
        # Setup new account details
        uploader.setup_new_account()
        
        # Initialize client
        if not uploader.initialize_client():
            print("❌ Failed to initialize Google Cloud client")
            return False
        
        # Upload all files
        success = uploader.upload_all_files()
        
        if success:
            print("✅ Upload completed successfully!")
        else:
            print("⚠️  Upload completed with some failures - check logs")
        
        # Verify upload
        uploader.verify_upload()
        
        # Create new env file
        uploader.create_new_env_file()
        
        print("\n" + "=" * 60)
        print("🎉 Migration complete!")
        print(f"📊 All files uploaded to: gs://{uploader.new_bucket_name}/")
        print("\n📋 Next steps:")
        print("1. Update your .env file with new credentials")
        print("2. Test bucket access with: python test_bucket_access.py")
        print("3. Continue with your AutoDamageConnect development")
        
        return success
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        print(f"❌ Upload failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
