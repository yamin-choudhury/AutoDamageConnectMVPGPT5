# Step 1: Environment Setup & Validation

## 🎯 **OBJECTIVE**
Set up the development environment and validate Google Cloud Storage access to the parts catalog bucket.

## ⏱️ **ESTIMATED TIME**: 15 minutes

## 📋 **PREREQUISITES**
- Python 3.8+ installed
- Google Cloud credentials configured
- Access to `car-parts-catalogue-yc` bucket

## 🏗️ **IMPLEMENTATION TASKS**

### **Task 1: Create Environment Configuration**
Create a `.env` file in `/backend/` with these variables:
```bash
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account.json
GOOGLE_CLOUD_PROJECT=rising-theater-466617-n8
PARTS_CATALOG_BUCKET=car-parts-catalogue-yc
OPENAI_API_KEY=your_openai_key
```

### **Task 2: Install Required Dependencies**
Add these to your requirements.txt and install:
```
google-cloud-storage>=2.10.0
langchain>=0.1.0
langchain-openai>=0.1.0
python-dotenv>=0.0.0
```

### Task 3: Create Bucket Access Test
Create `/backend/test_bucket_access.py` that:
- Loads environment variables from root `.env` file
- Connects to Google Cloud Storage
- Lists manufacturers from the `manufacturers/` folder in bucket
- Validates the bucket structure: `manufacturers/{ID}/models.json` and article files
- **Note**: Bucket structure discovered: `manufacturers/104/`, `manufacturers/117/`, etc.

### Task 4: Create Manufacturer Mapping
Create `/backend/manufacturer_mapping.json` with common manufacturer name variations:
```json
{
  "VAUXHALL": "117",
  "OPEL": "117",
  "FORD": "52",
  "BMW": "13",
  "MERCEDES": "85"
}
```

## ✅ **SUCCESS CRITERIA**
- ✅ Environment variables loaded correctly
- ✅ Google Cloud Storage connection working
- ✅ Can list manufacturers from bucket
- ✅ Manufacturer mapping file created
- ✅ Test script runs without errors

## 🧪 **VERIFICATION COMMAND**
```bash
python test_bucket_access.py
```

**Expected Output:**
```
🧪 Testing Google Cloud Storage Access...
✅ Environment variables loaded
✅ Connection successful to bucket: car-parts-catalogue-yc
✅ Found manufacturers: ['104']
✅ Models data structure valid (57 models)
✅ Manufacturer mapping loaded (18 mappings)
🎉 Step 1 verification complete - Environment setup successful!
```

## ❌ **COMMON ISSUES**
- **"Credentials not found"**: Check GOOGLE_APPLICATION_CREDENTIALS path
- **"Bucket not accessible"**: Verify service account has Storage Object Viewer role
- **"Import errors"**: Run `pip install -r requirements.txt`
- **"No manufacturers found"**: Bucket structure uses `manufacturers/` folder prefix

## 📝 **DISCOVERED BUCKET STRUCTURE**
```
car-parts-catalogue-yc/
└── manufacturers/
    └── 104/
        ├── models.json (57 models)
        └── articles_*.json (parts data)
```
**Note**: Manufacturers are stored in `manufacturers/{ID}/` not root level.

---
**Next Step**: Step 2 - Bucket Manager Foundation
import os
from google.cloud import storage
from dotenv import load_dotenv

def verify_manufacturer_mapping():
    """Verify known manufacturer IDs exist in bucket"""
    load_dotenv()
    
    # Known manufacturer mappings from catalog
    known_manufacturers = {
        "VAUXHALL": "117",
        "BMW": "16", 
        "MERCEDES-BENZ": "74"
    }
    
    try:
        client = storage.Client()
        bucket_name = os.getenv('PARTS_CATALOG_BUCKET')
        
        verified = {}
        for name, manufacturer_id in known_manufacturers.items():
            models_blob_name = f"manufacturers/{manufacturer_id}/models_{manufacturer_id}.json"
            blob = client.bucket(bucket_name).blob(models_blob_name)
            
            if blob.exists():
                verified[name] = manufacturer_id
                print(f"✅ {name} -> {manufacturer_id} verified")
            else:
                print(f"❌ {name} -> {manufacturer_id} not found")
        
        print(f"\n✅ Verified {len(verified)}/{len(known_manufacturers)} manufacturers")
        return len(verified) > 0
        
    except Exception as e:
        print(f"❌ Manufacturer verification failed: {str(e)}")
        return False

if __name__ == "__main__":
    verify_manufacturer_mapping()
```

## ✅ **SUCCESS CRITERIA**

After completing this step, you should have:

1. **✅ Environment variables configured** - `.env` file with correct paths
2. **✅ Dependencies installed** - All required Python packages available
3. **✅ Bucket access working** - Can list manufacturers from bucket
4. **✅ Sample data loading** - Can load a manufacturer's models file
5. **✅ Manufacturer mapping verified** - Known manufacturers exist in bucket

## 🧪 **VERIFICATION COMMAND**

Run this command to verify the step is complete:

```bash
python test_bucket_access.py
```

**Expected Output:**
```
✅ Bucket access successful - Found 35 manufacturers
Sample manufacturer IDs: ['117', '16', '74', '123', '456']
✅ Successfully loaded models for manufacturer 117
Models data size: 15420 characters

🎉 Environment setup complete - Ready for Step 2!
```

## ❌ **COMMON ISSUES & SOLUTIONS**

### **Issue 1: "No such file or directory" for service account key**
**Solution**: Ensure the path in `GOOGLE_APPLICATION_CREDENTIALS` points to your actual service account JSON file.

### **Issue 2: "Access Denied" or "Forbidden"**
**Solution**: Verify your service account has Storage Object Viewer permissions on the bucket.

### **Issue 3: "Bucket not found"**
**Solution**: Confirm the bucket name `car-parts-catalogue-yc` is correct and accessible.

### **Issue 4: ImportError for google-cloud-storage**
**Solution**: Run `pip install google-cloud-storage` to install the missing dependency.

## 🎯 **STEP COMPLETION**

**Only proceed to Step 2 if:**
- ✅ Verification command outputs success message
- ✅ No error messages in the output
- ✅ Manufacturer count is > 30 (indicating full catalog access)

**If verification fails:**
- 🔧 Debug the specific error message
- 🔧 Fix the underlying issue (credentials, permissions, etc.)
- 🔧 Re-run verification until it passes
- 🛑 DO NOT proceed to Step 2 until this step passes

---

**Next Step**: Step 2 - Bucket Manager Foundation
