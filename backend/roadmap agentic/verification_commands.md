# Verification Commands - Agentic Parts Discovery

## 🧪 **VERIFICATION COMMAND LIBRARY**

Run these commands to verify each step completion:

### **Step 1: Environment Setup**
```bash
python test_bucket_access.py
```
**Expected**: `✅ Bucket access successful - Found 35 manufacturers`

### **Step 2: Bucket Manager**
```bash
python test_bucket_manager.py
```
**Expected**: `✅ Loaded 45 models for VAUXHALL`

### **Step 3: Vehicle Tools**
```bash
python test_vehicle_tools.py
```
**Expected**: `✅ Vehicle identification working - Found manufacturer_id: 117`

### **Step 4: Variant Matching**
```bash
python test_variant_matching.py
```
**Expected**: `✅ Found 3 compatible variants for 2018 Astra`

### **Step 5: Parts Search Foundation**
```bash
python test_catalog_tools.py
```
**Expected**: `✅ Component mapping working - Front Bumper → Category 100020`

### **Step 6: Parts Search Implementation**
```bash
python test_parts_search.py
```
**Expected**: `✅ Found 12 relevant parts for Front Bumper Cover`

### **Step 7: Agent Foundation**
```bash
python test_agent_setup.py
```
**Expected**: `✅ Agent created with 3 tools - Ready for processing`

### **Step 8: Agent Reasoning**
```bash
python test_agent_reasoning.py
```
**Expected**: `✅ Agent completed reasoning - Found 8 relevant parts`

### **Step 9: Damage Propagation**
```bash
python test_damage_propagation.py
```
**Expected**: `✅ Propagation working - Found 12 parts including secondary damage`

### **Step 10: Pipeline Integration**
```bash
python test_pipeline_integration.py
```
**Expected**: `✅ Pipeline integration working - Generated report with real parts`

### **Step 11: Performance Optimization**
```bash
python test_performance.py
```
**Expected**: `✅ Performance optimized - 3x faster on repeat requests`

### **Step 12: End-to-End Testing**
```bash
python test_end_to_end.py
```
**Expected**: `✅ All 15 test scenarios passed - System ready for production`

### **Step 13: Web App Integration**
```bash
python test_web_integration.py
```
**Expected**: `✅ Web integration complete - Rich parts data displaying correctly`

## 🔍 **DEBUGGING COMMANDS**

If any verification fails, use these debugging commands:

### **Check Environment**
```bash
python -c "import os; print('BUCKET:', os.getenv('PARTS_CATALOG_BUCKET')); print('PROJECT:', os.getenv('GOOGLE_CLOUD_PROJECT'))"
```

### **Test Google Cloud Auth**
```bash
gcloud auth list
gcloud config list project
```

### **Check Bucket Access**
```bash
gsutil ls gs://car-parts-catalogue-yc/manufacturers/ | head -10
```

### **Verify Python Dependencies**
```bash
python -c "import google.cloud.storage, langchain, openai; print('All dependencies available')"
```

## ⚠️ **FAILURE PROTOCOL**

If any verification command fails:

1. **🛑 STOP** - Do not proceed to next step
2. **🔍 READ** the error message carefully
3. **🔧 DEBUG** the specific issue using debugging commands above
4. **🔄 RETRY** the verification command
5. **✅ PROCEED** only when verification passes

## 📊 **SUCCESS PATTERN**

Each successful step should show:
- ✅ Green checkmarks for successful operations
- 📊 Actual data counts (e.g., "Found 35 manufacturers", "Loaded 45 models")  
- 🎉 Success message with next step indication
- ❌ Red X marks only for expected failures (e.g., "Unknown Brand -> Not found")

## 🚀 **QUICK VERIFICATION CHECK**

Run this command to check overall system health:
```bash
python -c "
from agents.bucket_manager import bucket_manager
print('✅ BucketManager available')
print(f'✅ Cache stats: {bucket_manager.get_cache_stats()}')
print('✅ System health check passed')
"
```
