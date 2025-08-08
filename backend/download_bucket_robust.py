#!/usr/bin/env python3
"""
Robust bucket download with retry logic, error handling, and resume capability
"""

import os
import json
import time
import shutil
from pathlib import Path
from google.cloud import storage
from dotenv import load_dotenv
from tqdm import tqdm
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('download_robust.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RobustDownloader:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.bucket_name = os.getenv("PARTS_CATALOG_BUCKET")
        self.download_dir = Path(__file__).parent / "bucket_backup" / self.bucket_name
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize GCS client
        self.client = storage.Client(project=self.project_id)
        self.bucket = self.client.bucket(self.bucket_name)
        
        # Retry settings
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        self.batch_size = 100  # files per batch
        
        logger.info(f"Initialized - Project: {self.project_id}, Bucket: {self.bucket_name}")
    
    def get_missing_files(self):
        """Get list of files that still need to be downloaded"""
        logger.info("🔍 Finding missing files...")
        
        # Get all files in bucket
        try:
            all_bucket_files = []
            for blob in self.bucket.list_blobs():
                if blob.name.endswith('.json'):
                    all_bucket_files.append(blob.name)
            
            logger.info(f"Found {len(all_bucket_files)} JSON files in bucket")
            
            # Get already downloaded files
            downloaded_files = set()
            for local_file in self.download_dir.rglob("*.json"):
                if local_file.stat().st_size > 0:  # Only count non-empty files
                    relative_path = local_file.relative_to(self.download_dir)
                    downloaded_files.add(str(relative_path))
            
            logger.info(f"Found {len(downloaded_files)} already downloaded")
            
            # Calculate missing files
            missing_files = []
            for bucket_file in all_bucket_files:
                if bucket_file not in downloaded_files:
                    missing_files.append(bucket_file)
            
            logger.info(f"Need to download {len(missing_files)} missing files")
            return missing_files
            
        except Exception as e:
            logger.error(f"Error getting missing files: {e}")
            return []
    
    def download_file_with_retry(self, blob_name):
        """Download a single file with retry logic"""
        for attempt in range(self.max_retries):
            try:
                # Create local file path
                local_file_path = self.download_dir / blob_name
                local_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Download the file
                blob = self.bucket.blob(blob_name)
                blob.download_to_filename(str(local_file_path))
                
                # Verify file was downloaded and is not empty
                if local_file_path.exists() and local_file_path.stat().st_size > 0:
                    return True
                else:
                    logger.warning(f"Downloaded file {blob_name} is empty, retrying...")
                    if local_file_path.exists():
                        local_file_path.unlink()
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {blob_name}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed to download {blob_name} after {self.max_retries} attempts")
                    return False
        
        return False
    
    def download_batch(self, file_batch):
        """Download a batch of files"""
        successful = 0
        failed = 0
        
        for blob_name in file_batch:
            if self.download_file_with_retry(blob_name):
                successful += 1
            else:
                failed += 1
        
        return successful, failed
    
    def download_missing_files(self):
        """Download all missing files in batches"""
        missing_files = self.get_missing_files()
        
        if not missing_files:
            logger.info("🎉 All files already downloaded!")
            return True
        
        logger.info(f"📥 Starting download of {len(missing_files)} missing files...")
        
        # Split into batches
        total_successful = 0
        total_failed = 0
        
        with tqdm(total=len(missing_files), unit="files") as pbar:
            for i in range(0, len(missing_files), self.batch_size):
                batch = missing_files[i:i + self.batch_size]
                
                logger.info(f"Processing batch {i//self.batch_size + 1}/{(len(missing_files) - 1)//self.batch_size + 1}")
                
                successful, failed = self.download_batch(batch)
                total_successful += successful
                total_failed += failed
                
                pbar.update(len(batch))
                pbar.set_description(f"Downloaded: {total_successful}, Failed: {total_failed}")
                
                # Small delay between batches to be nice to the API
                time.sleep(1)
        
        logger.info(f"📊 Download complete!")
        logger.info(f"   Successful: {total_successful}")
        logger.info(f"   Failed: {total_failed}")
        
        return total_failed == 0
    
    def verify_download(self):
        """Verify all files are downloaded correctly"""
        logger.info("🔍 Verifying download completeness...")
        
        # Count local files
        local_files = list(self.download_dir.rglob("*.json"))
        valid_files = [f for f in local_files if f.stat().st_size > 0]
        empty_files = [f for f in local_files if f.stat().st_size == 0]
        
        logger.info(f"Valid files: {len(valid_files)}")
        logger.info(f"Empty files: {len(empty_files)}")
        
        # Remove empty files
        for empty_file in empty_files:
            empty_file.unlink()
            logger.info(f"Removed empty file: {empty_file}")
        
        # Try to get bucket count (with timeout)
        try:
            bucket_count = 0
            start_time = time.time()
            for blob in self.bucket.list_blobs():
                if blob.name.endswith('.json'):
                    bucket_count += 1
                # Timeout after 30 seconds
                if time.time() - start_time > 30:
                    logger.warning("Bucket count timeout - using estimated count")
                    bucket_count = 32483  # Use known count
                    break
            
            logger.info(f"Bucket files: {bucket_count}")
            logger.info(f"Downloaded: {len(valid_files)}")
            
            if len(valid_files) >= bucket_count:
                logger.info("✅ Download appears complete!")
                return True
            else:
                logger.warning(f"❌ Still missing {bucket_count - len(valid_files)} files")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying download: {e}")
            return False

def main():
    """Main download function"""
    print("🚀 Starting robust bucket download...")
    
    downloader = RobustDownloader()
    
    # Download missing files
    success = downloader.download_missing_files()
    
    if success:
        print("✅ Download completed successfully!")
    else:
        print("⚠️  Download completed with some failures - check logs")
    
    # Verify download
    downloader.verify_download()
    
    # Final status
    final_count = len(list(downloader.download_dir.rglob("*.json")))
    print(f"\n📊 Final status: {final_count} files downloaded")
    
    return success

if __name__ == "__main__":
    main()
