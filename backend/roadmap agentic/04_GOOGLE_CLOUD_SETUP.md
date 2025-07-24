# ☁️ Google Cloud Setup: Parts Catalog Access

## 🔑 **Authentication Setup**

### **Option 1: Service Account (Recommended for Production)**
```bash
# Create service account
gcloud iam service-accounts create auto-damage-parts-reader \
    --display-name="Auto Damage Parts Reader" \
    --project=rising-theater-466617-n8

# Grant bucket access
gcloud projects add-iam-policy-binding rising-theater-466617-n8 \
    --member="serviceAccount:auto-damage-parts-reader@rising-theater-466617-n8.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# Download service account key
gcloud iam service-accounts keys create ~/auto-damage-sa-key.json \
    --iam-account="auto-damage-parts-reader@rising-theater-466617-n8.iam.gserviceaccount.com"

# Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS=~/auto-damage-sa-key.json
```

### **Option 2: Application Default Credentials (Development)**
```bash
# Login with your account
gcloud auth application-default login

# Set project
gcloud config set project rising-theater-466617-n8
```

## 📊 **Bucket Structure Validation**

### **Verify Bucket Access**
```python
#!/usr/bin/env python3
"""Validate access to parts catalog bucket."""

from google.cloud import storage
import json

def validate_bucket_access():
    """Test bucket access and structure."""
    try:
        client = storage.Client(project="rising-theater-466617-n8")
        bucket = client.bucket("car-parts-catalogue-yc")
        
        print("✅ Bucket access successful")
        
        # List manufacturers
        blobs = bucket.list_blobs(prefix="manufacturers/", delimiter="/")
        manufacturers = []
        for page in blobs.pages:
            for blob in page:
                if blob.name.endswith("/"):
                    manufacturer_id = blob.name.split("/")[1]
                    manufacturers.append(manufacturer_id)
        
        print(f"✅ Found {len(manufacturers)} manufacturers")
        print(f"📋 Manufacturer IDs: {manufacturers[:10]}...")  # Show first 10
        
        # Test specific manufacturer (Vauxhall = 117)
        test_manufacturer = "117"
        if test_manufacturer in manufacturers:
            print(f"✅ Testing manufacturer {test_manufacturer} (VAUXHALL)...")
            
            # Check models file
            models_blob = bucket.blob(f"manufacturers/{test_manufacturer}/models_{test_manufacturer}.json")
            if models_blob.exists():
                models_content = json.loads(models_blob.download_as_text())
                print(f"✅ Models file exists: {len(models_content)} models found")
                
                # Show first model
                if models_content:
                    first_model = models_content[0]
                    print(f"📋 Sample model: {first_model}")
                    
                    # Check variants for first model
                    model_id = first_model["id"]
                    variants_blob = bucket.blob(f"manufacturers/{test_manufacturer}/variants_{model_id}.json")
                    if variants_blob.exists():
                        variants_content = json.loads(variants_blob.download_as_text())
                        print(f"✅ Variants file exists: {len(variants_content)} variants found")
                        
                        if variants_content:
                            first_variant = variants_content[0]
                            print(f"📋 Sample variant: {first_variant}")
            else:
                print(f"❌ Models file missing for manufacturer {test_manufacturer}")
        else:
            print(f"❌ Test manufacturer {test_manufacturer} not found")
            
        return True
        
    except Exception as e:
        print(f"❌ Bucket access failed: {str(e)}")
        return False

if __name__ == "__main__":
    validate_bucket_access()
```

### **Save as `validate_bucket.py` and run:**
```bash
cd /Users/yaminchoudhury/Documents/AutoDamageConnect/DamageReportMVP/backend
python validate_bucket.py
```

## 🗺️ **Manufacturer Mapping**

### **Complete Manufacturer ID Mapping**
Create `agents/utils/manufacturer_mapping.py`:
```python
#!/usr/bin/env python3
"""Complete mapping of manufacturer names to catalog IDs."""

# Based on your actual bucket structure - verify these IDs
MANUFACTURER_MAPPING = {
    # Major UK Manufacturers (confirmed from your memory)
    "VAUXHALL": "117",
    "BMW": "16", 
    "MERCEDES-BENZ": "74",
    
    # Additional manufacturers - verify these IDs from your bucket
    "AUDI": "19",
    "FORD": "58",
    "HONDA": "12",
    "TOYOTA": "8",
    "NISSAN": "13",
    "VOLKSWAGEN": "7",
    "VW": "7",  # Alias
    "PEUGEOT": "25",
    "CITROËN": "26",
    "RENAULT": "93",  # From your memory
    "FIAT": "30",
    "HYUNDAI": "45",
    "KIA": "46",
    "MAZDA": "15",
    "MITSUBISHI": "18",
    "SUBARU": "20",
    "SUZUKI": "22",
    "JAGUAR": "35",
    "LAND ROVER": "36",
    "MINI": "40",
    "SMART": "42",
    "SEAT": "28",
    "SKODA": "29",
    "VOLVO": "14",
    "LEXUS": "50",
    "MASERATI": "55",
    "LOTUS": "60",
    "MORGAN": "65",
    "BENTLEY": "70",
    "TVR": "75",
    
    # VW variants from your memory
    "VW (FAW)": "2859",
    "VW (SVW)": "3035",
    
    # Daimler group
    "DAIMLER": "74",  # Same as Mercedes-Benz
}

# Reverse mapping for lookup
ID_TO_MANUFACTURER = {v: k for k, v in MANUFACTURER_MAPPING.items()}

def get_manufacturer_id(make_name: str) -> str:
    """Get manufacturer ID from name with fuzzy matching."""
    if not make_name:
        return None
        
    # Direct lookup
    make_upper = make_name.upper().strip()
    if make_upper in MANUFACTURER_MAPPING:
        return MANUFACTURER_MAPPING[make_upper]
    
    # Fuzzy matching for common variations
    fuzzy_matches = {
        "MERCEDES": "74",
        "MERC": "74", 
        "BENZ": "74",
        "VOLKSWAGEN": "7",
        "CITROEN": "26",  # Without accent
        "LANDROVER": "36",  # One word
        "RANGE ROVER": "36",  # Range Rover is Land Rover
    }
    
    if make_upper in fuzzy_matches:
        return fuzzy_matches[make_upper]
    
    # Partial matching
    for name, id_val in MANUFACTURER_MAPPING.items():
        if make_upper in name or name in make_upper:
            return id_val
    
    return None

def get_manufacturer_name(manufacturer_id: str) -> str:
    """Get manufacturer name from ID."""
    return ID_TO_MANUFACTURER.get(manufacturer_id, "Unknown")

def list_all_manufacturers() -> dict:
    """Get all manufacturer mappings."""
    return MANUFACTURER_MAPPING.copy()
```

### **Verify Manufacturer IDs**
Create `verify_manufacturers.py`:
```python
#!/usr/bin/env python3
"""Verify manufacturer IDs against actual bucket contents."""

from google.cloud import storage
from agents.utils.manufacturer_mapping import MANUFACTURER_MAPPING

def verify_manufacturer_ids():
    """Check which manufacturer IDs actually exist in the bucket."""
    client = storage.Client(project="rising-theater-466617-n8")
    bucket = client.bucket("car-parts-catalogue-yc")
    
    # Get actual manufacturer IDs from bucket
    blobs = bucket.list_blobs(prefix="manufacturers/", delimiter="/")
    actual_ids = set()
    
    for page in blobs.pages:
        for blob in page:
            if blob.name.endswith("/"):
                manufacturer_id = blob.name.split("/")[1]
                actual_ids.add(manufacturer_id)
    
    print(f"📊 Found {len(actual_ids)} manufacturers in bucket")
    print(f"🏭 Actual IDs: {sorted(actual_ids)}")
    
    # Check mapping accuracy
    mapped_ids = set(MANUFACTURER_MAPPING.values())
    print(f"\n📋 Mapped IDs: {len(mapped_ids)}")
    
    # Find matches and mismatches
    correct_ids = actual_ids & mapped_ids
    missing_ids = actual_ids - mapped_ids
    invalid_ids = mapped_ids - actual_ids
    
    print(f"\n✅ Correct mappings: {len(correct_ids)}")
    print(f"❌ Missing from mapping: {len(missing_ids)} - {sorted(missing_ids)}")
    print(f"⚠️  Invalid mappings: {len(invalid_ids)} - {sorted(invalid_ids)}")
    
    # Check specific manufacturers
    test_manufacturers = ["VAUXHALL", "BMW", "MERCEDES-BENZ", "FORD", "AUDI"]
    print(f"\n🧪 Testing key manufacturers:")
    
    for make in test_manufacturers:
        mapped_id = MANUFACTURER_MAPPING.get(make)
        exists = mapped_id in actual_ids if mapped_id else False
        status = "✅" if exists else "❌"
        print(f"{status} {make}: {mapped_id} - {'EXISTS' if exists else 'MISSING'}")

if __name__ == "__main__":
    verify_manufacturer_ids()
```

## 🔧 **Environment Configuration**

### **Add to `.env` file:**
```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=rising-theater-466617-n8
PARTS_CATALOG_BUCKET=car-parts-catalogue-yc
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Agent Configuration
AGENT_MODEL=gpt-4o
AGENT_TEMPERATURE=0.2
ENABLE_PARTS_CACHING=true
CACHE_TTL_SECONDS=3600

# Performance Settings
MAX_VARIANTS_PER_SEARCH=3
MAX_PARTS_PER_COMPONENT=10
BUCKET_TIMEOUT_SECONDS=30
```

### **Update `requirements.txt`:**
```txt
# Existing dependencies...
google-cloud-storage>=2.10.0
google-auth>=2.0.0
google-cloud-core>=2.0.0
```

## 🚀 **Performance Optimization**

### **Bucket Access Optimization**
```python
#!/usr/bin/env python3
"""Optimized bucket access patterns."""

import json, time
from functools import lru_cache
from google.cloud import storage
from typing import Dict, List, Optional

class OptimizedBucketManager:
    """High-performance bucket manager with caching and batching."""
    
    def __init__(self, bucket_name: str, project_id: str):
        self.client = storage.Client(project=project_id)
        self.bucket = self.client.bucket(bucket_name)
        self.cache = {}
        self.cache_ttl = {}
        self.ttl_seconds = 3600  # 1 hour cache
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached item is still valid."""
        if key not in self.cache_ttl:
            return False
        return time.time() - self.cache_ttl[key] < self.ttl_seconds
    
    def load_with_cache(self, file_path: str) -> Optional[Dict]:
        """Load JSON with intelligent caching."""
        cache_key = f"json:{file_path}"
        
        # Check cache
        if cache_key in self.cache and self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        try:
            blob = self.bucket.blob(file_path)
            if not blob.exists():
                return None
            
            content = json.loads(blob.download_as_text())
            
            # Cache the result
            self.cache[cache_key] = content
            self.cache_ttl[cache_key] = time.time()
            
            return content
            
        except Exception as e:
            print(f"Error loading {file_path}: {str(e)}")
            return None
    
    def batch_load_articles(self, manufacturer_id: str, variant_id: str, 
                           category_ids: List[str]) -> Dict[str, List]:
        """Load multiple article files in batch for efficiency."""
        results = {}
        
        for category_id in category_ids:
            prefix = f"manufacturers/{manufacturer_id}/articles_{variant_id}_{category_id}"
            
            try:
                blobs = self.bucket.list_blobs(prefix=prefix)
                articles = []
                
                for blob in blobs:
                    if blob.name.endswith('.json'):
                        content = self.load_with_cache(blob.name)
                        if content:
                            articles.extend(content)
                
                results[category_id] = articles
                
            except Exception as e:
                print(f"Error batch loading articles for category {category_id}: {str(e)}")
                results[category_id] = []
        
        return results
    
    @lru_cache(maxsize=100)
    def get_manufacturer_models(self, manufacturer_id: str) -> List[Dict]:
        """Cached manufacturer models lookup."""
        file_path = f"manufacturers/{manufacturer_id}/models_{manufacturer_id}.json"
        return self.load_with_cache(file_path) or []
```

## 🔍 **Troubleshooting**

### **Common Issues and Solutions**

#### **Authentication Errors**
```bash
# Check authentication
gcloud auth list

# Re-authenticate if needed
gcloud auth application-default login

# Verify project
gcloud config get-value project
```

#### **Bucket Access Denied**
```bash
# Check bucket permissions
gsutil ls gs://car-parts-catalogue-yc/

# Check IAM permissions
gcloud projects get-iam-policy rising-theater-466617-n8
```

#### **Missing Manufacturer Data**
```python
# Debug missing manufacturers
from google.cloud import storage

client = storage.Client()
bucket = client.bucket("car-parts-catalogue-yc")

# List all manufacturer folders
for blob in bucket.list_blobs(prefix="manufacturers/", delimiter="/"):
    print(blob.name)
```

#### **Performance Issues**
- Enable caching with `ENABLE_PARTS_CACHING=true`
- Reduce search scope with `MAX_VARIANTS_PER_SEARCH=3`
- Use batch loading for multiple category queries
- Monitor bucket request quota

This setup ensures reliable, high-performance access to your parts catalog with proper error handling and optimization.
