#!/usr/bin/env python3
"""
Step 1 Verification: Test Google Cloud Storage access to parts catalog bucket
"""

import os
import json
from pathlib import Path
from google.cloud import storage
from dotenv import load_dotenv

def test_bucket_access():
    """Test Google Cloud Storage access to parts catalog"""
    
    print("🧪 Testing Google Cloud Storage Access...")
    print("=" * 50)
    
    # Load environment variables from multiple possible locations
    print("1. Loading environment variables...")
    
    # Try backend/.env first, then parent directory .env
    env_paths = [
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env"
    ]
    
    env_loaded = False
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"   Loading from: {env_path}")
            env_loaded = True
            break
    
    if not env_loaded:
        print("   Loading from system environment...")
        load_dotenv()
    
    # Check required environment variables
    required_vars = [
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT", 
        "PARTS_CATALOG_BUCKET"
    ]
    
    # Debug: Show what environment variables we can find
    print("   Found environment variables:")
    for key, value in os.environ.items():
        if any(search_term in key.upper() for search_term in ['GOOGLE', 'PARTS', 'CLOUD', 'OPENAI']):
            print(f"     {key}: {value[:50]}..." if len(value) > 50 else f"     {key}: {value}")
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {missing_vars}")
        print("\nPlease add these to your backend/.env file:")
        print("GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json")
        print("GOOGLE_CLOUD_PROJECT=rising-theater-466617-n8")
        print("PARTS_CATALOG_BUCKET=car-parts-catalogue-yc")
        print("OPENAI_API_KEY=your_openai_key_here")
        return False
    
    print("✅ Environment variables loaded")
    
    # Test Google Cloud Storage connection
    print("2. Connecting to Google Cloud Storage...")
    try:
        client = storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))
        bucket_name = os.getenv("PARTS_CATALOG_BUCKET")
        bucket = client.bucket(bucket_name)
        
        # Test bucket access by listing a few items
        blobs = list(bucket.list_blobs(max_results=10))
        print(f"✅ Connection successful to bucket: {bucket_name}")
        
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check your service account JSON file path")
        print("2. Verify service account has 'Storage Object Viewer' role")
        print("3. Ensure bucket name is correct")
        return False
    
    # List manufacturers (should be top-level folders in bucket)
    print("3. Listing manufacturers...")
    try:
        manufacturers = set()
        
        # First, let's explore the bucket structure
        print("   Exploring bucket structure...")
        blob_count = 0
        for blob in bucket.list_blobs(max_results=20):
            blob_count += 1
            print(f"     {blob.name}")
            
            # Check if it's a folder-like structure
            if '/' in blob.name:
                first_part = blob.name.split('/')[0]
                if first_part.isdigit():
                    manufacturers.add(first_part)
        
        if blob_count == 0:
            print("   ❌ Bucket appears to be empty")
            return False
        
        # Look for manufacturer folders inside 'manufacturers/' directory
        print("   Looking for manufacturer folders in 'manufacturers/' directory...")
        
        # Also get manufacturers from the file paths we already found
        print("   Extracting manufacturers from file paths...")
        for blob in bucket.list_blobs(prefix='manufacturers/', max_results=50):
            if blob.name.startswith('manufacturers/') and '/' in blob.name[14:]:  # Skip "manufacturers/" prefix
                path_parts = blob.name.split('/')
                if len(path_parts) >= 2:
                    manufacturer_id = path_parts[1]  # Should be the manufacturer ID
                    if manufacturer_id.isdigit():
                        manufacturers.add(manufacturer_id)
        
        # Also try the delimiter approach
        for blob in bucket.list_blobs(prefix='manufacturers/', delimiter='/'):
            if blob.name.endswith('/') and blob.name != 'manufacturers/':
                # This is a "folder" (prefix)
                folder_path = blob.name.rstrip('/')
                manufacturer_id = folder_path.split('/')[-1]  # Get the last part after 'manufacturers/'
                print(f"     Found folder: {manufacturer_id}")
                if manufacturer_id.isdigit():
                    manufacturers.add(manufacturer_id)
        
        manufacturer_list = sorted(list(manufacturers))[:5]  # First 5
        print(f"✅ Found manufacturers: {manufacturer_list}")
        
        if len(manufacturer_list) == 0:
            print("❌ No manufacturers found in bucket")
            print("   This might be a bucket structure issue.")
            return False
            
    except Exception as e:
        print(f"❌ Failed to list manufacturers: {str(e)}")
        return False
    
    # Validate bucket structure by checking one manufacturer
    print("4. Validating bucket structure...")
    try:
        test_manufacturer = manufacturer_list[0]
        
        # Look for models.json in the manufacturer folder
        models_blob_name = f"manufacturers/{test_manufacturer}/models.json"
        models_blob = bucket.blob(models_blob_name)
        
        if models_blob.exists():
            print(f"✅ Found models.json for manufacturer {test_manufacturer}")
            
            # Try to parse the JSON to validate structure
            models_data = json.loads(models_blob.download_as_text())
            if isinstance(models_data, list) and len(models_data) > 0:
                print(f"✅ Models data structure valid ({len(models_data)} models)")
            else:
                print("❌ Models data structure invalid")
                return False
        else:
            print(f"❌ No models.json found for manufacturer {test_manufacturer}")
            return False
            
    except Exception as e:
        print(f"❌ Bucket structure validation failed: {str(e)}")
        return False
    
    # Test manufacturer mapping file
    print("5. Testing manufacturer mapping...")
    mapping_file = Path(__file__).parent / "manufacturer_mapping.json"
    if mapping_file.exists():
        try:
            with open(mapping_file, 'r') as f:
                mapping = json.load(f)
            print(f"✅ Manufacturer mapping loaded ({len(mapping)} mappings)")
        except Exception as e:
            print(f"❌ Failed to load manufacturer mapping: {str(e)}")
            return False
    else:
        print("❌ manufacturer_mapping.json not found")
        return False
    
    print("=" * 50)
    print("🎉 Step 1 verification complete - Environment setup successful!")
    print("✅ Google Cloud Storage access working")
    print("✅ Parts catalog bucket accessible")
    print("✅ Manufacturer mapping ready")
    print("\n➡️  Ready to proceed to Step 2: Bucket Manager Foundation")
    
    return True

if __name__ == "__main__":
    success = test_bucket_access()
    exit(0 if success else 1)
