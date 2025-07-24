# Step 2: Bucket Manager Foundation

## 🎯 **OBJECTIVE**
Create a bucket manager class to handle Google Cloud Storage operations with caching and manufacturer mapping.

## ⏱️ **ESTIMATED TIME**: 20 minutes

## 📋 **PREREQUISITES**
- ✅ Step 1: Environment setup working
- ✅ Google Cloud Storage access validated
- ✅ Manufacturer mapping created

## 🏗️ **IMPLEMENTATION TASKS**

### **Task 1: Create Bucket Manager Class**
Create `/backend/agents/bucket_manager.py` with:
- `BucketManager` class that connects to Google Cloud Storage
- `get_manufacturer_id(name)` method with fuzzy matching
- `get_models_for_manufacturer(id)` method with caching
- `get_articles_for_category(manufacturer_id, variant_id, category_id)` method
- Simple in-memory cache with TTL (1 hour) and size limit (100 items)
- Error handling for missing files
- **Note**: Article files follow pattern `articles_{variant}_{category}_{id}.json`

### **Task 2: Create Package Structure**
Create the agents package:
```bash
mkdir -p /backend/agents/tools
touch /backend/agents/__init__.py
touch /backend/agents/tools/__init__.py
```

### **Task 3: Create Bucket Manager Test**
Create `/backend/test_bucket_manager.py` that tests:
- Manufacturer ID lookup ("Vauxhall" -> "117")
- Models loading for a manufacturer
- Cache functionality (second call should be faster)
- Articles loading for a category

### **Task 4: Test Fuzzy Manufacturer Matching**
Ensure the manager handles variations like:
- "VAUXHALL", "Vauxhall", "vauxhall" -> "117"
- "OPEL" -> "117" (same as Vauxhall)
- "BMW", "Bmw" -> "13"

## ✅ **SUCCESS CRITERIA**
- ✅ BucketManager class created and functional
- ✅ Manufacturer mapping works with fuzzy matching
- ✅ Caching reduces repeated API calls
- ✅ Can load models for any manufacturer
- ✅ Can load articles for categories
- ✅ Error handling for missing files

## 🧪 **VERIFICATION COMMAND**
```bash
python test_bucket_manager.py
```

**Expected Output:**
```
🧪 Testing Bucket Manager...
✅ BucketManager initialized successfully
✅ Vauxhall -> 117 (fuzzy matching working)
✅ Loaded 57 models for manufacturer 104
✅ Cache working correctly - second call is faster
✅ Loaded 53 articles for category 100001
🎉 Bucket manager test complete - Ready for Step 3!
```

## ❌ **COMMON ISSUES**
- **"Models file not found"**: Check manufacturer ID is correct
- **"Cache not working"**: Verify cache key generation is consistent
- **"Articles loading fails"**: Check variant_id and category_id exist

---
**Next Step**: Step 3 - Vehicle Identification Tools
