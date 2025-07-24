# Step 4: Variant Matching Tool

## 🎯 **OBJECTIVE**
Create a tool to find matching vehicle variants in the catalog with fuzzy model matching and year filtering.

## ⏱️ **ESTIMATED TIME**: 20 minutes

## 📋 **PREREQUISITES**
- ✅ Step 3: Vehicle tools working
- ✅ Can identify vehicles from reports
- ✅ Manufacturer mapping functional

## 🏗️ **IMPLEMENTATION TASKS**

### **Task 1: Add Variant Matching Tool**
Add to `/backend/agents/tools/vehicle_tools.py`:
- `find_matching_variants(manufacturer_id, model_name, year)` function
- Uses SequenceMatcher for fuzzy model name matching
- Filters variants by year range if provided
- Returns compatibility scores for each variant
- Handles model name variations ("Astra" vs "ASTRA K")

### **Task 2: Implement Compatibility Scoring**
Create scoring system that considers:
- Model name similarity (0.0-1.0)
- Year compatibility (bonus for exact year match)
- Variant availability in catalog
- Return top 5 most compatible variants

### **Task 3: Create Variant Test**
Create `/backend/test_variant_matching.py` that tests:
- Finding Vauxhall Astra variants for 2018
- Fuzzy matching for slightly different model names
- Year filtering functionality
- Error handling for unknown models

### **Task 4: Update Tools Export**
Update `/backend/agents/tools/__init__.py` to include the new variant matching tool.

## ✅ **SUCCESS CRITERIA**
- ✅ Finds multiple compatible variants for a given model
- ✅ Fuzzy matching works for model name variations
- ✅ Year filtering returns appropriate variants
- ✅ Compatibility scores help rank variants
- ✅ Returns empty list for unknown models gracefully

## 🧪 **VERIFICATION COMMAND**
```bash
python test_variant_matching.py
```

**Expected Output:**
```
🧪 Testing Variant Matching...
✅ Found 3 variants for Vauxhall Astra 2018
✅ Fuzzy matching: "ASTRA" matches "Astra K" (score: 0.85)
✅ Year filtering: 2018 variants found in 2015-2020 range
✅ Unknown model handled gracefully
🎉 Variant matching test complete - Ready for Step 5!
```

## ❌ **COMMON ISSUES**
- **"No variants found"**: Check that models exist for the manufacturer
- **"Low similarity scores"**: Adjust fuzzy matching threshold
- **"Year filtering too strict"**: Expand year range tolerance

---
**Next Step**: Step 5 - Parts Search Foundation

### **1. Add Variant Matching Tool**
Extend the vehicle tools with variant matching capability:

```python
# File: /backend/agents/tools/vehicle_tools.py (ADD TO EXISTING FILE)
# Add this import at the top
from difflib import SequenceMatcher

# Add this tool after the existing tools
@tool
def find_matching_variants(manufacturer_id: str, model_name: str, year: int = None) -> Dict:
    """
    Find compatible vehicle variants from the catalog.
    
    Args:
        manufacturer_id: Manufacturer ID from catalog
        model_name: Model name to search for
        year: Vehicle year (optional for filtering)
    
    Returns:
        List of compatible variants with compatibility scores
    """
    try:
        # Load models for this manufacturer
        models = bucket_manager.get_models_for_manufacturer(manufacturer_id)
        
        if not models:
            return {
                "variants": [],
                "error": f"No models found for manufacturer {manufacturer_id}",
                "success": False
            }
        
        # Find matching model
        matching_model = None
        best_score = 0.0
        
        model_name_clean = model_name.upper().strip()
        
        for model in models:
            catalog_name = model.get("name", "").upper().strip()
            
            # Calculate similarity score
            score = SequenceMatcher(None, model_name_clean, catalog_name).ratio()
            
            # Boost score for exact matches or common variations
            if model_name_clean == catalog_name:
                score = 1.0
            elif model_name_clean in catalog_name or catalog_name in model_name_clean:
                score = max(score, 0.9)
            
            if score > best_score and score >= 0.7:  # Minimum similarity threshold
                best_score = score
                matching_model = model
        
        if not matching_model:
            return {
                "variants": [],
                "error": f"No matching model found for '{model_name}'",
                "success": False,
                "available_models": [m.get("name") for m in models[:5]]
            }
        
        # Load variants for the matching model
        model_id = matching_model.get("id")
        variants = bucket_manager.get_variants_for_model(manufacturer_id, model_id)
        
        if not variants:
            return {
                "variants": [],
                "error": f"No variants found for model {matching_model.get('name')}",
                "success": False
            }
        
        # Filter and score variants
        compatible_variants = []
        
        for variant in variants:
            variant_score = 0.8  # Base compatibility score
            
            # Extract variant information
            variant_name = variant.get("name", "")
            variant_year_range = variant.get("yearRange", "")
            variant_years = variant.get("years", [])
            
            # Year compatibility scoring
            if year:
                year_compatible = False
                
                # Check if year is in explicit years list
                if variant_years and year in variant_years:
                    year_compatible = True
                    variant_score += 0.2
                
                # Check year range (format like "2015-2020" or "2018+")
                elif variant_year_range:
                    if "-" in variant_year_range:
                        try:
                            start_year, end_year = variant_year_range.split("-")
                            if int(start_year) <= year <= int(end_year):
                                year_compatible = True
                                variant_score += 0.2
                        except:
                            pass
                    elif "+" in variant_year_range:
                        try:
                            start_year = int(variant_year_range.replace("+", ""))
                            if year >= start_year:
                                year_compatible = True
                                variant_score += 0.2
                        except:
                            pass
                
                # If no year info available, assume compatible but lower score
                if not year_compatible and not variant_years and not variant_year_range:
                    year_compatible = True
                    variant_score = 0.6  # Lower score for unknown compatibility
                
                if not year_compatible:
                    continue  # Skip incompatible variants
            
            compatible_variants.append({
                "id": variant.get("id"),
                "name": variant_name,
                "year_range": variant_year_range,
                "years": variant_years,
                "model_name": matching_model.get("name"),
                "model_id": model_id,
                "compatibility_score": min(variant_score, 1.0)
            })
        
        # Sort by compatibility score
        compatible_variants.sort(key=lambda x: x["compatibility_score"], reverse=True)
        
        return {
            "variants": compatible_variants,
            "model_match": {
                "name": matching_model.get("name"),
                "id": model_id,
                "similarity_score": best_score
            },
            "total_variants": len(compatible_variants),
            "success": True
        }
        
    except Exception as e:
        return {
            "variants": [],
            "error": f"Variant matching failed: {str(e)}",
            "success": False
        }

# Update the tools export list
vehicle_identification_tools = [
    identify_vehicle_from_report,
    validate_vehicle_in_catalog,
    find_matching_variants
]
```

### **2. Update Tools Package Export**
Update the tools package to include the new tool:

```python
# File: /backend/agents/tools/__init__.py (UPDATE EXISTING)
from .vehicle_tools import (
    vehicle_identification_tools, 
    identify_vehicle_from_report, 
    validate_vehicle_in_catalog,
    find_matching_variants
)

__all__ = [
    'vehicle_identification_tools',
    'identify_vehicle_from_report', 
    'validate_vehicle_in_catalog',
    'find_matching_variants'
]
```

### **3. Create Variant Matching Test Script**
Test the variant matching functionality:

```python
# File: /backend/test_variant_matching.py
import json
from agents.tools.vehicle_tools import identify_vehicle_from_report, find_matching_variants

def test_variant_matching():
    """Test variant matching functionality"""
    
    print("🧪 Testing Variant Matching...")
    
    # Test cases with different scenarios
    test_cases = [
        {
            "name": "2018 Vauxhall Astra",
            "vehicle_info": {"make": "Vauxhall", "model": "Astra", "year": 2018},
            "expected_variants": True
        },
        {
            "name": "BMW 3 Series without year",
            "vehicle_info": {"make": "BMW", "model": "3 Series"},  
            "expected_variants": True
        },
        {
            "name": "Mercedes C-Class 2019",
            "vehicle_info": {"make": "Mercedes", "model": "C-Class", "year": 2019},
            "expected_variants": True
        },
        {
            "name": "Fuzzy model match",
            "vehicle_info": {"make": "Vauxhall", "model": "Astra Hatchback", "year": 2017},
            "expected_variants": True
        }
    ]
    
    success_count = 0
    
    for test_case in test_cases:
        print(f"\n🔍 Testing: {test_case['name']}")
        
        # Step 1: Identify vehicle
        vehicle_json = json.dumps(test_case["vehicle_info"])
        vehicle_result = identify_vehicle_from_report("{}", vehicle_json)
        
        if not vehicle_result.get("success"):
            print(f"❌ Vehicle identification failed: {vehicle_result}")
            continue
        
        print(f"✅ Vehicle identified: {vehicle_result['make']} -> {vehicle_result['manufacturer_id']}")
        
        # Step 2: Find variants
        variants_result = find_matching_variants(
            vehicle_result["manufacturer_id"],
            vehicle_result["model"],
            vehicle_result.get("year")
        )
        
        if not variants_result.get("success"):
            print(f"❌ Variant matching failed: {variants_result}")
            continue
        
        variants = variants_result["variants"]
        model_match = variants_result["model_match"]
        
        print(f"✅ Model match: {model_match['name']} (similarity: {model_match['similarity_score']:.2f})")
        print(f"✅ Found {len(variants)} compatible variants")
        
        # Show top 3 variants
        for i, variant in enumerate(variants[:3]):
            year_info = variant.get("year_range") or f"Years: {variant.get('years', 'Unknown')}"
            print(f"   {i+1}. {variant['name']} ({year_info}) - Score: {variant['compatibility_score']:.2f}")
        
        if test_case["expected_variants"] and len(variants) > 0:
            success_count += 1
        elif not test_case["expected_variants"] and len(variants) == 0:
            success_count += 1
        else:
            print(f"❌ Expected variants: {test_case['expected_variants']}, got {len(variants)} variants")
    
    print(f"\n📊 Results: {success_count}/{len(test_cases)} tests passed")
    
    # Additional functionality test
    print("\n🔍 Testing edge cases:")
    
    # Test invalid manufacturer
    invalid_result = find_matching_variants("999", "NonExistent", 2020)
    if not invalid_result.get("success"):
        print("✅ Correctly handled invalid manufacturer")
        success_count += 0.5
    
    # Test invalid model name
    if success_count > 0:
        valid_manufacturer = "117"  # Vauxhall
        invalid_model_result = find_matching_variants(valid_manufacturer, "XYZ_NonExistent_Model", 2020)
        if not invalid_model_result.get("success"):
            print("✅ Correctly handled invalid model name")
            success_count += 0.5
    
    return success_count >= len(test_cases)

if __name__ == "__main__":
    try:
        success = test_variant_matching()
        if success:
            print("\n🎉 Variant matching test complete - Ready for Step 5!")
        else:
            print("\n⚠️ Variant matching test failed")
    except Exception as e:
        print(f"\n❌ Variant matching test error: {str(e)}")
```

## ✅ **SUCCESS CRITERIA**

After completing this step, you should have:

1. **✅ Variant matching tool created** - Can find compatible variants
2. **✅ Fuzzy model matching working** - Handles slight name variations
3. **✅ Year filtering implemented** - Respects vehicle year constraints
4. **✅ Compatibility scoring added** - Ranks variants by fit
5. **✅ Error handling comprehensive** - Graceful failure for invalid inputs
6. **✅ Multiple variants supported** - Returns list of compatible options

## 🧪 **VERIFICATION COMMAND**

Run this command to verify the step is complete:

```bash
python test_variant_matching.py
```

**Expected Output:**
```
🧪 Testing Variant Matching...

🔍 Testing: 2018 Vauxhall Astra
✅ Vehicle identified: VAUXHALL -> 117
✅ Model match: Astra (similarity: 1.00)
✅ Found 3 compatible variants
   1. Astra 1.4T (2016-2020) - Score: 1.00
   2. Astra 1.6L (2015-2019) - Score: 1.00
   3. Astra 2.0L (2017-2021) - Score: 1.00

🔍 Testing: BMW 3 Series without year
✅ Vehicle identified: BMW -> 16
✅ Model match: 3 Series (similarity: 1.00)
✅ Found 5 compatible variants

📊 Results: 4/4 tests passed

🔍 Testing edge cases:
✅ Correctly handled invalid manufacturer
✅ Correctly handled invalid model name

🎉 Variant matching test complete - Ready for Step 5!
```

## ❌ **COMMON ISSUES & SOLUTIONS**

### **Issue 1: "No matching model found"**
**Solution**: Check the similarity threshold (0.7) and add more model name variations.

### **Issue 2: "No variants found for model"**
**Solution**: Verify the model ID is correct and variants file exists in bucket.

### **Issue 3: Year filtering too strict**
**Solution**: Review year parsing logic - ensure it handles ranges like "2015-2020" and "2018+".

### **Issue 4: Low compatibility scores**
**Solution**: Adjust scoring logic - base 0.8 + 0.2 for year match should give reasonable scores.

## 🎯 **STEP COMPLETION**

**Only proceed to Step 5 if:**
- ✅ At least 3/4 main test cases pass
- ✅ Model similarity matching works (scores > 0.7)
- ✅ Variants are returned with reasonable compatibility scores
- ✅ Edge cases are handled properly

**If verification fails:**
- 🔧 Check the bucket structure matches expected paths
- 🔧 Verify model and variant files exist for test manufacturers
- 🔧 Ensure fuzzy matching logic is working correctly
- 🛑 DO NOT proceed to Step 5 until this step passes

---

**Next Step**: Step 5 - Parts Search Foundation
