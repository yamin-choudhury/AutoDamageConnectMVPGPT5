# Step 6: Parts Search Implementation

## 🎯 **OBJECTIVE**
Implement comprehensive parts search with relevance scoring and intelligent matching.

## ⏱️ **ESTIMATED TIME**: 30 minutes

## 📋 **PREREQUISITES**
- ✅ Step 5: Parts foundation working
- ✅ Component mapping functional
- ✅ Category loading operational

## 🏗️ **IMPLEMENTATION TASKS**

### **Task 1: Add Parts Search Tool**
Add to `/backend/agents/tools/catalog_tools.py`:
- `search_parts_for_damage(variant_ids_json, damaged_components_json)` function
- Searches across multiple variants for comprehensive coverage
- Uses component mapping to find relevant categories
- Loads articles from bucket for each category/variant combination

### **Task 2: Implement Relevance Scoring**
Create scoring system using:
- Exact name matching (highest score)
- Fuzzy string matching with SequenceMatcher
- Keyword overlap between component and part names
- Threshold filtering (minimum 0.5 relevance)

### **Task 3: Add Duplicate Removal**
Implement deduplication based on:
- OEM part numbers
- EAN/UPC codes
- Article IDs
- Preserve highest-scoring duplicates

### **Task 4: Create Comprehensive Test**
Create `/backend/test_parts_search.py` that tests:
- End-to-end parts discovery for front-end collision
- Relevance scoring accuracy
- Duplicate removal effectiveness
- Performance with multiple variants

### **Task 5: Update Tools Export**
Add parts search tool to the tools package exports.

## ✅ **SUCCESS CRITERIA**
- ✅ Finds relevant parts across multiple vehicle variants
- ✅ Relevance scoring ranks parts appropriately
- ✅ Duplicate removal works across variants
- ✅ Returns structured part data with all identifiers
- ✅ Performance is acceptable (<5 seconds)

## 🧪 **VERIFICATION COMMAND**
```bash
python test_parts_search.py
```

**Expected Output:**
```
🧪 Testing Parts Search Implementation...
✅ Found 12 parts for Front Bumper Cover + Headlight Assembly
✅ Relevance scores: 8 high (>0.8), 4 medium (0.5-0.8)
✅ Duplicates removed: 3 OEM matches, 2 EAN matches
✅ All components covered with relevant parts
🎉 Parts search test complete - Ready for Step 7!
```

## ❌ **COMMON ISSUES**
- **"No parts found"**: Check category mapping covers the components
- **"Low relevance scores"**: Adjust fuzzy matching parameters
- **"Too many duplicates"**: Verify deduplication logic

---
**Next Step**: Step 7 - Agent Foundation BREAKDOWN**

### **1. Complete Parts Search Tool**
Add the comprehensive parts search functionality to catalog tools:

```python
# File: /backend/agents/tools/catalog_tools.py (ADD TO EXISTING FILE)
# Add these imports at the top
from difflib import SequenceMatcher
import re

# Add this tool after the existing ones
@tool
def search_parts_for_damage(variant_ids_json: str, damaged_components_json: str) -> List[Dict]:
    """
    Search catalog for parts matching damaged components across multiple variants.
    
    Args:
        variant_ids_json: JSON list of compatible variant IDs
        damaged_components_json: JSON list of damaged component names
    
    Returns:
        List of matching parts with relevance scores
    """
    try:
        variant_ids = json.loads(variant_ids_json)
        damaged_components = json.loads(damaged_components_json)
        
        if not isinstance(variant_ids, list) or not isinstance(damaged_components, list):
            return []
        
        all_parts = []
        
        # Map components to categories
        component_mappings = {}
        for component in damaged_components:
            categories = get_categories_for_component(component)
            component_mappings[component] = categories
        
        # Search each variant
        for variant_info in variant_ids:
            if isinstance(variant_info, dict):
                variant_id = variant_info.get("id")
                manufacturer_id = variant_info.get("manufacturer_id")
            else:
                # Handle simple variant ID strings
                variant_id = variant_info
                manufacturer_id = "117"  # Default to Vauxhall, should be passed properly
            
            if not variant_id or not manufacturer_id:
                continue
            
            # Load categories for this variant
            categories_result = load_categories_for_variant(manufacturer_id, variant_id)
            if not categories_result.get("success"):
                continue
            
            available_categories = categories_result["categories"]
            
            # Search each component
            for component in damaged_components:
                relevant_categories = component_mappings[component]
                
                for category_id in relevant_categories:
                    if category_id not in available_categories:
                        continue
                    
                    category_info = available_categories[category_id]
                    
                    # Search each product group in this category
                    for product_group in category_info["product_groups"]:
                        product_group_id = product_group["id"]
                        
                        # Load articles for this product group
                        articles = bucket_manager.get_articles_for_category(
                            manufacturer_id, variant_id, category_id, product_group_id
                        )
                        
                        if not articles:
                            continue
                        
                        # Score and filter articles
                        for article in articles:
                            relevance_score = calculate_part_relevance(article, component)
                            
                            if relevance_score >= 0.5:  # Minimum relevance threshold
                                enhanced_part = enhance_part_data(
                                    article, component, relevance_score, 
                                    variant_id, manufacturer_id, category_id
                                )
                                all_parts.append(enhanced_part)
        
        # Remove duplicates and rank
        unique_parts = remove_duplicate_parts(all_parts)
        ranked_parts = sorted(unique_parts, key=lambda x: x["relevance_score"], reverse=True)
        
        return ranked_parts[:50]  # Limit to top 50 parts
        
    except Exception as e:
        print(f"Parts search error: {str(e)}")
        return []

def calculate_part_relevance(article: Dict, component: str) -> float:
    """Calculate how relevant a part is to the damaged component"""
    
    part_name = article.get("name", "").lower()
    part_desc = article.get("description", "").lower()
    component_lower = component.lower()
    
    # Base score
    relevance_score = 0.0
    
    # Exact name match
    if component_lower in part_name or part_name in component_lower:
        relevance_score = 1.0
    
    # Fuzzy name matching
    elif part_name and component_lower:
        similarity = SequenceMatcher(None, component_lower, part_name).ratio()
        if similarity > 0.6:
            relevance_score = similarity
    
    # Keyword matching
    component_keywords = re.findall(r'\w+', component_lower)
    part_keywords = re.findall(r'\w+', part_name + " " + part_desc)
    
    if component_keywords and part_keywords:
        keyword_matches = sum(1 for kw in component_keywords if kw in part_keywords)
        keyword_score = keyword_matches / len(component_keywords)
        relevance_score = max(relevance_score, keyword_score * 0.8)
    
    # Category relevance boost
    if any(keyword in part_name for keyword in ["cover", "assembly", "panel"]):
        relevance_score *= 1.1
    
    return min(relevance_score, 1.0)

def enhance_part_data(article: Dict, component: str, relevance_score: float, 
                     variant_id: str, manufacturer_id: str, category_id: str) -> Dict:
    """Enhance part data with additional metadata"""
    
    return {
        # Core part information
        "article_id": article.get("id"),
        "part_name": article.get("name"),
        "manufacturer_part_number": article.get("partNo"),
        "ean_number": article.get("ean"),
        "oem_numbers": article.get("oemNumbers", []),
        "part_manufacturer": article.get("manufacturer"),
        
        # Context information
        "matched_component": component,
        "relevance_score": relevance_score,
        "variant_id": variant_id,
        "manufacturer_id": manufacturer_id,
        "category_id": category_id,
        
        # Additional details
        "description": article.get("description", ""),
        "technical_details": article.get("techDetails", {}),
        
        # Compatibility info
        "fits_vehicles": article.get("fitsVehicles", []),
        "year_range": article.get("yearRange", ""),
        
        # Search metadata
        "search_timestamp": None,  # Could add timestamp
        "confidence_level": "high" if relevance_score > 0.8 else "medium" if relevance_score > 0.6 else "low"
    }

def remove_duplicate_parts(parts_list: List[Dict]) -> List[Dict]:
    """Remove duplicate parts based on part numbers and IDs"""
    
    seen_parts = set()
    unique_parts = []
    
    # Sort by relevance score first (highest first)
    sorted_parts = sorted(parts_list, key=lambda x: x["relevance_score"], reverse=True)
    
    for part in sorted_parts:
        # Create unique identifier
        part_number = part.get("manufacturer_part_number", "")
        article_id = part.get("article_id", "")
        ean_number = part.get("ean_number", "")
        
        # Use multiple identifiers for deduplication
        identifiers = {
            part_number.strip() if part_number else None,
            article_id.strip() if article_id else None,
            ean_number.strip() if ean_number else None
        }
        identifiers.discard(None)  # Remove None values
        
        # Check if we've seen any of these identifiers
        if not any(identifier in seen_parts for identifier in identifiers):
            unique_parts.append(part)
            seen_parts.update(identifiers)
    
    return unique_parts

# Update the tools export
catalog_search_tools = [
    map_components_to_categories,
    load_categories_for_variant,
    search_parts_for_damage
]
```

### **2. Update Tools Package**
Update the package to include the new search tool:

```python
# File: /backend/agents/tools/__init__.py (UPDATE EXISTING)
from .vehicle_tools import (
    vehicle_identification_tools, 
    identify_vehicle_from_report, 
    validate_vehicle_in_catalog,
    find_matching_variants
)
from .catalog_tools import (
    catalog_search_tools,
    map_components_to_categories,
    load_categories_for_variant,
    search_parts_for_damage
)

# Combine all tools
all_agent_tools = vehicle_identification_tools + catalog_search_tools

__all__ = [
    'all_agent_tools',
    'vehicle_identification_tools',
    'catalog_search_tools',
    'identify_vehicle_from_report', 
    'validate_vehicle_in_catalog',
    'find_matching_variants',
    'map_components_to_categories',
    'load_categories_for_variant',
    'search_parts_for_damage'
]
```

### **3. Create Parts Search Test Script**
Test the complete parts search functionality:

```python
# File: /backend/test_parts_search.py
import json
from agents.tools.vehicle_tools import identify_vehicle_from_report, find_matching_variants
from agents.tools.catalog_tools import search_parts_for_damage

def test_parts_search():
    """Test complete parts search functionality"""
    
    print("🧪 Testing Parts Search Implementation...")
    
    # Test scenario: 2018 Vauxhall Astra front-end collision
    vehicle_info = {"make": "Vauxhall", "model": "Astra", "year": 2018}
    damaged_components = ["Front Bumper Cover", "Headlight Assembly"]
    
    print(f"🔍 Test Scenario: {vehicle_info} with damage: {damaged_components}")
    
    # Step 1: Identify vehicle
    vehicle_json = json.dumps(vehicle_info)
    vehicle_result = identify_vehicle_from_report("{}", vehicle_json)
    
    if not vehicle_result.get("success"):
        print(f"❌ Vehicle identification failed: {vehicle_result}")
        return False
    
    print(f"✅ Vehicle identified: {vehicle_result['make']} -> {vehicle_result['manufacturer_id']}")
    
    # Step 2: Find variants
    variants_result = find_matching_variants(
        vehicle_result["manufacturer_id"],
        vehicle_result["model"],
        vehicle_result.get("year")
    )
    
    if not variants_result.get("success") or not variants_result["variants"]:
        print(f"❌ Variant matching failed: {variants_result}")
        return False
    
    variants = variants_result["variants"][:3]  # Use top 3 variants
    print(f"✅ Found {len(variants)} compatible variants")
    
    # Prepare variant data for search
    variant_search_data = []
    for variant in variants:
        variant_search_data.append({
            "id": variant["id"],
            "manufacturer_id": vehicle_result["manufacturer_id"]
        })
    
    # Step 3: Search for parts
    print(f"\n🔍 Searching for parts...")
    
    variants_json = json.dumps(variant_search_data)
    components_json = json.dumps(damaged_components)
    
    parts_results = search_parts_for_damage(variants_json, components_json)
    
    if not parts_results:
        print("❌ No parts found")
        return False
    
    print(f"✅ Found {len(parts_results)} matching parts")
    
    # Analyze results
    component_coverage = {}
    high_relevance_count = 0
    
    for part in parts_results[:10]:  # Show top 10
        component = part["matched_component"]
        score = part["relevance_score"]
        
        if component not in component_coverage:
            component_coverage[component] = 0
        component_coverage[component] += 1
        
        if score >= 0.8:
            high_relevance_count += 1
        
        print(f"   📦 {part['part_name']}")
        print(f"      Part #: {part['manufacturer_part_number']}")
        print(f"      Component: {component} (Score: {score:.2f})")
        print(f"      Confidence: {part['confidence_level']}")
        
        if part.get("ean_number"):
            print(f"      EAN: {part['ean_number']}")
        
        print()
    
    # Success criteria
    success = (
        len(parts_results) >= 5 and  # Found at least 5 parts
        len(component_coverage) == len(damaged_components) and  # All components covered
        high_relevance_count >= 2  # At least 2 high-relevance parts
    )
    
    print(f"📊 Analysis:")
    print(f"   Total parts found: {len(parts_results)}")
    print(f"   Components covered: {len(component_coverage)}/{len(damaged_components)}")
    print(f"   High relevance parts: {high_relevance_count}")
    print(f"   Component breakdown: {dict(component_coverage)}")
    
    return success

def test_edge_cases():
    """Test edge cases and error handling"""
    
    print("\n🧪 Testing Edge Cases...")
    
    success_count = 0
    
    # Test 1: Empty components
    print("🔍 Test 1: Empty components")
    result = search_parts_for_damage('[]', '[]')
    if isinstance(result, list) and len(result) == 0:
        print("✅ Correctly handled empty components")
        success_count += 1
    
    # Test 2: Invalid JSON
    print("🔍 Test 2: Invalid JSON")
    result = search_parts_for_damage('invalid json', '["test"]')
    if isinstance(result, list) and len(result) == 0:
        print("✅ Correctly handled invalid JSON")
        success_count += 1
    
    # Test 3: Unknown components
    print("🔍 Test 3: Unknown components")
    fake_variants = json.dumps([{"id": "127445", "manufacturer_id": "117"}])
    unknown_components = json.dumps(["Flux Capacitor", "Hyperdrive Unit"])
    result = search_parts_for_damage(fake_variants, unknown_components)
    
    if isinstance(result, list):
        print(f"✅ Handled unknown components (found {len(result)} parts with defaults)")
        success_count += 1
    
    return success_count >= 2

if __name__ == "__main__":
    try:
        print("🧪 Testing Complete Parts Search Implementation...")
        
        main_success = test_parts_search()
        edge_success = test_edge_cases()
        
        if main_success and edge_success:
            print("\n🎉 Parts search implementation test complete - Ready for Step 7!")
        else:
            print(f"\n⚠️ Tests failed - Main: {main_success}, Edge cases: {edge_success}")
    except Exception as e:
        print(f"\n❌ Parts search test error: {str(e)}")
```

## ✅ **SUCCESS CRITERIA**

After completing this step, you should have:

1. **✅ Complete parts search implemented** - Can find parts across multiple variants
2. **✅ Relevance scoring working** - Parts ranked by match quality
3. **✅ Duplicate removal functional** - No duplicate parts in results
4. **✅ Component coverage comprehensive** - All damaged components get parts
5. **✅ Error handling robust** - Graceful handling of edge cases
6. **✅ Performance optimized** - Limited to top 50 results

## 🧪 **VERIFICATION COMMAND**

Run this command to verify the step is complete:

```bash
python test_parts_search.py
```

**Expected Output:**
```
🧪 Testing Complete Parts Search Implementation...

🧪 Testing Parts Search Implementation...
🔍 Test Scenario: {'make': 'Vauxhall', 'model': 'Astra', 'year': 2018} with damage: ['Front Bumper Cover', 'Headlight Assembly']
✅ Vehicle identified: VAUXHALL -> 117
✅ Found 3 compatible variants

🔍 Searching for parts...
✅ Found 12 matching parts

   📦 Front Bumper Cover Assembly
      Part #: VXH025001
      Component: Front Bumper Cover (Score: 0.95)
      Confidence: high
      EAN: 1234567890123

   📦 Headlight Unit - Right
      Part #: VXH098001
      Component: Headlight Assembly (Score: 0.88)
      Confidence: high

📊 Analysis:
   Total parts found: 12
   Components covered: 2/2
   High relevance parts: 8
   Component breakdown: {'Front Bumper Cover': 6, 'Headlight Assembly': 6}

🧪 Testing Edge Cases...
🔍 Test 1: Empty components
✅ Correctly handled empty components
🔍 Test 2: Invalid JSON
✅ Correctly handled invalid JSON
🔍 Test 3: Unknown components
✅ Handled unknown components (found 3 parts with defaults)

🎉 Parts search implementation test complete - Ready for Step 7!
```

## ❌ **COMMON ISSUES & SOLUTIONS**

### **Issue 1: "No parts found" for valid components**
**Solution**: Check that category mapping is correct and articles files exist for those categories.

### **Issue 2: Low relevance scores for obvious matches**
**Solution**: Review the `calculate_part_relevance` function - ensure keyword matching is working.

### **Issue 3: Too many duplicate parts**
**Solution**: Verify the `remove_duplicate_parts` function is using appropriate identifiers.

### **Issue 4: Performance issues with large result sets**
**Solution**: The limit of 50 parts should prevent this, but verify the limit is being applied.

## 🎯 **STEP COMPLETION**

**Only proceed to Step 7 if:**
- ✅ At least 5+ parts found for test scenario
- ✅ All damaged components have matching parts
- ✅ High relevance parts (score > 0.8) are present
- ✅ Edge cases are handled gracefully

**If verification fails:**
- 🔧 Check that articles files exist in the bucket structure
- 🔧 Verify relevance scoring logic with debug prints
- 🔧 Ensure component mapping covers the test components
- 🛑 DO NOT proceed to Step 7 until this step passes

---

**Next Step**: Step 7 - Agent Foundation
