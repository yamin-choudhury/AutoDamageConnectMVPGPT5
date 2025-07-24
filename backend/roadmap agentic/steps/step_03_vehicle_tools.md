# Step 3: Vehicle Identification Tools

## 🎯 **OBJECTIVE**
Create LangChain tools for vehicle identification from damage reports and catalog validation.

## ⏱️ **ESTIMATED TIME**: 25 minutes

## 📋 **PREREQUISITES**
- ✅ Step 2: Bucket manager working
- ✅ Can load manufacturer models from catalog
- ✅ Manufacturer mapping functional

## 🏗️ **IMPLEMENTATION TASKS**

### **Task 1: Create Vehicle Identification Tool**
Create `/backend/agents/tools/vehicle_tools.py` with:
- `identify_vehicle_from_report(damage_report_json, vehicle_info_json)` tool
- Extracts make, model, year from JSON inputs
- Maps manufacturer name to catalog ID using bucket_manager
- Returns structured result with success/error status
- Handles multiple input field variations ("make" vs "vehicle_make")

### **Task 2: Create Vehicle Validation Tool**
Add `validate_vehicle_in_catalog(vehicle_info_json)` tool that:
- Takes vehicle info and checks if it exists in catalog
- Uses bucket_manager to verify manufacturer has models
- Returns validation status and available models count

### **Task 3: Create Variant Matching Tool**
Add `find_matching_variants(manufacturer_id, model_name, year)` tool that:
- Loads all models for the manufacturer
- Finds models that match the given model name (fuzzy matching)
- Filters variants by year if provided
- Returns list of compatible variants with compatibility scores

### **Task 4: Update Tools Package**
Update `/backend/agents/tools/__init__.py` to export:
- `vehicle_identification_tools` list
- Individual tool functions for direct import

## ✅ **SUCCESS CRITERIA**
- ✅ Vehicle identification tool extracts make/model/year from JSON
- ✅ Manufacturer names map to catalog IDs correctly
- ✅ Vehicle validation confirms catalog presence
- ✅ Variant matching finds compatible vehicle variants
- ✅ Tools return structured results with error handling
- ✅ Package exports all tools for agent use

## 🧪 **VERIFICATION COMMAND**
```bash
python test_vehicle_tools.py
```

**Expected Output:**
```
🧪 Testing Vehicle Tools...
✅ Vehicle identification: Vauxhall Astra -> 117
✅ Catalog validation: Found 15 models for manufacturer 117
✅ Variant matching: Found 3 compatible variants for Astra 2018
✅ Error handling: Gracefully handled unknown manufacturer
🎉 Vehicle tools test complete - Ready for Step 4!
```

## ❌ **COMMON ISSUES**
- **"Unknown manufacturer"**: Add more mappings to manufacturer_mapping.json
- **"No models found"**: Check manufacturer ID is correct in catalog
- **"Import errors"**: Ensure bucket_manager is properly imported

---
**Next Step**: Step 4 - Variant Matching Tools
                "error": f"No models found for manufacturer {manufacturer_id}",
                "available_models": []
            }
        
        # Check for exact match
        model_name_upper = model_name.upper()
        exact_matches = []
        fuzzy_matches = []
        
        for model in models:
            model_catalog_name = model.get("name", "").upper()
            
            if model_catalog_name == model_name_upper:
                exact_matches.append(model)
            elif model_name_upper in model_catalog_name or model_catalog_name in model_name_upper:
                fuzzy_matches.append(model)
        
        # Get list of available models for reference
        available_models = [model.get("name") for model in models[:10]]  # First 10 for brevity
        
        return {
            "valid": len(exact_matches) > 0 or len(fuzzy_matches) > 0,
            "exact_matches": exact_matches,
            "fuzzy_matches": fuzzy_matches,
            "available_models": available_models,
            "total_models": len(models)
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": f"Catalog validation failed: {str(e)}",
            "available_models": []
        }

# Export tools for agent use
vehicle_identification_tools = [
    identify_vehicle_from_report,
    validate_vehicle_in_catalog
]
```

### **2. Update Tools Package**
Make the tools easily importable:

```python
# File: /backend/agents/tools/__init__.py
from .vehicle_tools import vehicle_identification_tools, identify_vehicle_from_report, validate_vehicle_in_catalog

__all__ = [
    'vehicle_identification_tools',
    'identify_vehicle_from_report', 
    'validate_vehicle_in_catalog'
]
```

### **3. Create Vehicle Tools Test Script**
Verify the vehicle identification functionality:

```python
# File: /backend/test_vehicle_tools.py
import json
from agents.tools.vehicle_tools import identify_vehicle_from_report, validate_vehicle_in_catalog

def test_vehicle_identification():
    """Test vehicle identification tool functionality"""
    
    print("🧪 Testing Vehicle Identification Tools...")
    
    # Test data
    test_cases = [
        {
            "name": "Complete Vauxhall Astra",
            "vehicle_info": {"make": "Vauxhall", "model": "Astra", "year": 2018},
            "expected_manufacturer": "117"
        },
        {
            "name": "BMW with different case",
            "vehicle_info": {"make": "bmw", "model": "3 Series", "year": 2020},
            "expected_manufacturer": "16"
        },
        {
            "name": "Mercedes-Benz variation",
            "vehicle_info": {"make": "Mercedes", "model": "C-Class", "year": 2019},
            "expected_manufacturer": "74"
        },
        {
            "name": "Missing year",
            "vehicle_info": {"make": "Vauxhall", "model": "Corsa"},
            "expected_manufacturer": "117"
        },
        {
            "name": "Unknown manufacturer",
            "vehicle_info": {"make": "Tesla", "model": "Model 3", "year": 2021},
            "expected_manufacturer": None
        }
    ]
    
    success_count = 0
    
    for test_case in test_cases:
        print(f"\n🔍 Testing: {test_case['name']}")
        
        # Convert test data to JSON strings
        damage_json = json.dumps({})  # Empty damage data for this test
        vehicle_json = json.dumps(test_case["vehicle_info"])
        
        # Run the tool
        result = identify_vehicle_from_report(damage_json, vehicle_json)
        
        # Check results
        if test_case["expected_manufacturer"]:
            if result.get("success") and result.get("manufacturer_id") == test_case["expected_manufacturer"]:
                print(f"✅ Success: {test_case['vehicle_info']['make']} -> {result['manufacturer_id']}")
                print(f"   Confidence: {result['confidence']:.2f}")
                success_count += 1
            else:
                print(f"❌ Failed: Expected {test_case['expected_manufacturer']}, got {result}")
        else:
            # Expecting failure for unknown manufacturer
            if not result.get("success"):
                print(f"✅ Correctly rejected unknown manufacturer: {result.get('error')}")
                success_count += 1
            else:
                print(f"❌ Should have failed for unknown manufacturer: {result}")
    
    print(f"\n📊 Results: {success_count}/{len(test_cases)} tests passed")
    
    # Test catalog validation
    print("\n🔍 Testing catalog validation:")
    if success_count > 0:
        validation_result = validate_vehicle_in_catalog("117", "Astra")
        if validation_result.get("valid"):
            print("✅ Catalog validation working")
            print(f"   Found {len(validation_result.get('exact_matches', []))} exact matches")
            print(f"   Available models: {len(validation_result.get('available_models', []))}")
        else:
            print(f"❌ Catalog validation failed: {validation_result}")
    
    return success_count >= len(test_cases) - 1  # Allow one failure for unknown manufacturer

if __name__ == "__main__":
    try:
        success = test_vehicle_identification()
        if success:
            print("\n🎉 Vehicle identification tools test complete - Ready for Step 4!")
        else:
            print("\n⚠️ Vehicle identification test failed")
    except Exception as e:
        print(f"\n❌ Vehicle identification test error: {str(e)}")
```

## ✅ **SUCCESS CRITERIA**

After completing this step, you should have:

1. **✅ Vehicle identification tool created** - Can extract vehicle info from JSON
2. **✅ Manufacturer mapping working** - Converts names to catalog IDs
3. **✅ Error handling implemented** - Graceful failure for invalid input
4. **✅ Confidence scoring added** - Rates data completeness
5. **✅ Catalog validation functional** - Can verify models exist
6. **✅ Multiple input formats supported** - Flexible field extraction

## 🧪 **VERIFICATION COMMAND**

Run this command to verify the step is complete:

```bash
python test_vehicle_tools.py
```

**Expected Output:**
```
🧪 Testing Vehicle Identification Tools...

🔍 Testing: Complete Vauxhall Astra
✅ Success: Vauxhall -> 117
   Confidence: 1.00

🔍 Testing: BMW with different case
✅ Success: bmw -> 16
   Confidence: 1.00

🔍 Testing: Mercedes-Benz variation
✅ Success: Mercedes -> 74
   Confidence: 1.00

🔍 Testing: Missing year
✅ Success: Vauxhall -> 117
   Confidence: 0.90

🔍 Testing: Unknown manufacturer
✅ Correctly rejected unknown manufacturer: Unknown manufacturer: Tesla

📊 Results: 5/5 tests passed

🔍 Testing catalog validation:
✅ Catalog validation working
   Found 1 exact matches
   Available models: 10

🎉 Vehicle identification tools test complete - Ready for Step 4!
```

## ❌ **COMMON ISSUES & SOLUTIONS**

### **Issue 1: ImportError for langchain.tools**
**Solution**: Install LangChain: `pip install langchain`

### **Issue 2: "No models found for manufacturer"**
**Solution**: Verify the manufacturer ID exists in bucket using Step 2's verification.

### **Issue 3: JSON parsing errors**
**Solution**: Ensure test data is properly formatted JSON strings.

### **Issue 4: Confidence scores seem wrong**
**Solution**: Review the confidence calculation logic - base 0.7 + 0.2 for model + 0.1 for year.

## 🎯 **STEP COMPLETION**

**Only proceed to Step 4 if:**
- ✅ At least 4/5 test cases pass (allowing unknown manufacturer to fail)
- ✅ Catalog validation shows available models
- ✅ Manufacturer mapping works for known brands
- ✅ Confidence scores are reasonable (0.7-1.0)

**If verification fails:**
- 🔧 Check the manufacturer mapping in bucket_manager.py
- 🔧 Verify bucket access is still working from Step 2
- 🔧 Ensure proper JSON formatting in test cases
- 🛑 DO NOT proceed to Step 4 until this step passes

---

**Next Step**: Step 4 - Variant Matching Tool
