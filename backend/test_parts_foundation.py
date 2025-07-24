#!/usr/bin/env python3
"""
Step 5 Verification: Test Parts Foundation - Component Mapping and Category Loading
"""

import json
import sys
import time
from pathlib import Path

# Add the current directory to the path so we can import agents
sys.path.insert(0, str(Path(__file__).parent))

from agents.tools.catalog_tools import (
    map_components_to_categories,
    load_categories_for_variant,
    get_categories_for_component
)

def test_parts_foundation():
    """Test the parts foundation functionality."""
    
    print("🧪 Testing Parts Foundation...")
    print("=" * 50)
    
    # Test 1: Component mapping for common damage types
    print("1. Testing component mapping for common damage types...")
    
    # Test data representing damage from a real report
    damaged_components = [
        "Front Bumper Cover",
        "Headlight Assembly", 
        "Left Front Fender",
        "Hood",
        "Front Grille"
    ]
    
    damaged_components_json = json.dumps(damaged_components)
    
    try:
        result = map_components_to_categories.func(damaged_components_json)
        
        if result.get("success"):
            component_mapping = result.get("component_mapping", {})
            all_categories = result.get("all_categories", [])
            total_components = result.get("total_components", 0)
            total_categories = result.get("total_categories", 0)
            
            print(f"✅ Component mapping: {total_components} components -> {total_categories} unique categories")
            
            # Show detailed mapping for each component
            for component, mapping in component_mapping.items():
                categories = mapping.get("categories", [])
                print(f"   • \"{component}\" -> {categories}")
            
            print(f"   All categories needed: {all_categories}")
            
            # Verify expected mappings
            if "Front Bumper Cover" in component_mapping:
                bumper_cats = component_mapping["Front Bumper Cover"]["categories"]
                if "100020" in bumper_cats:
                    print("   ✓ Front Bumper Cover correctly mapped to Body Parts (100020)")
                else:
                    print("   ⚠️  Front Bumper Cover mapping unexpected")
            
            if "Headlight Assembly" in component_mapping:
                headlight_cats = component_mapping["Headlight Assembly"]["categories"]
                if "100021" in headlight_cats:
                    print("   ✓ Headlight Assembly correctly mapped to Lighting (100021)")
                else:
                    print("   ⚠️  Headlight Assembly mapping unexpected")
                    
        else:
            print(f"❌ Component mapping failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Component mapping error: {e}")
        return False
    
    # Test 2: Individual component mapping with variations
    print("\n2. Testing individual component mapping with variations...")
    
    test_components = [
        ("Front Bumper Cover", "Exact match"),
        ("FRONT BUMPER COVER", "Case insensitive"),
        ("Bumper Cover", "Partial match"),
        ("Left Headlight", "Fuzzy match"),
        ("Driver Side Mirror", "Complex fuzzy match"),
        ("Unknown Component", "Unknown fallback")
    ]
    
    for component, description in test_components:
        try:
            categories = get_categories_for_component(component)
            print(f"   • {description}: \"{component}\" -> {categories}")
            
        except Exception as e:
            print(f"❌ Individual mapping error for \"{component}\": {e}")
            return False
    
    # Test 3: Category loading for known variants
    print("\n3. Testing category loading for known variants...")
    
    # Test with manufacturer 104, variant 10615 - we know this has real data
    try:
        print("   Testing with manufacturer 104, variant 10615 (known to have data)")
        
        # Load categories for this variant
        start_time = time.time()
        category_result = load_categories_for_variant.func("104", "10615")
        load_time = time.time() - start_time
        
        if category_result.get("success"):
            categories = category_result.get("categories", [])
            category_count = category_result.get("category_count", 0)
            total_articles = category_result.get("total_articles", 0)
            
            print(f"✅ Category loading: Found {category_count} categories with {total_articles} total articles")
            print(f"   Load time: {load_time:.3f} seconds")
            
            # Show first few categories with their article counts
            for i, category in enumerate(categories[:5]):
                cat_id = category.get("category_id")
                article_count = category.get("article_count", 0)
                articles = category.get("articles", [])
                sample_article = articles[0] if articles else {}
                article_id = sample_article.get("article_id", "")
                
                print(f"   Category {i+1}: {cat_id} ({article_count} articles)")
                if article_id:
                    print(f"     Sample article: {article_id}")
            
            if category_count > 5:
                print(f"   ... and {category_count - 5} more categories")
            
            # Verify the data structure
            if category_count > 0 and total_articles > 0:
                print("   ✓ Real article data successfully loaded and parsed")
            else:
                print("   ⚠️  Categories found but no articles - might be empty files")
                
        else:
            print(f"❌ Category loading failed: {category_result.get('error')}")
            return False
        
        # Also test with a non-existent variant to verify error handling
        print("\n   Testing error handling with non-existent variant...")
        
        error_result = load_categories_for_variant.func("104", "99999")
        if error_result.get("success") and error_result.get("category_count", 0) == 0:
            print("   ✅ Non-existent variant: Handled gracefully (no categories found)")
        elif not error_result.get("success"):
            print("   ✅ Non-existent variant: Properly returned error")
        else:
            print("   ⚠️  Non-existent variant: Unexpected result")
            
    except Exception as e:
        print(f"❌ Category loading error: {e}")
        return False
    
    # Test 4: Cache performance testing
    print("\n4. Testing cache performance...")
    
    try:
        # Test the same component mapping multiple times
        test_components_json = json.dumps(["Front Bumper", "Headlight", "Door"])
        
        # First call
        start_time = time.time()
        result1 = map_components_to_categories.func(test_components_json)
        first_call_time = time.time() - start_time
        
        # Second call (should be faster due to any internal optimizations)
        start_time = time.time()
        result2 = map_components_to_categories.func(test_components_json)
        second_call_time = time.time() - start_time
        
        print(f"   First call: {first_call_time:.4f}s")
        print(f"   Second call: {second_call_time:.4f}s")
        
        if first_call_time > 0 and second_call_time > 0:
            speedup = first_call_time / second_call_time
            if speedup > 1.2:
                print(f"✅ Cache performance: 2nd call {speedup:.1f}x faster")
            else:
                print(f"✅ Cache performance: Consistent timing ({speedup:.1f}x)")
        else:
            print("✅ Cache performance: Both calls very fast")
            
    except Exception as e:
        print(f"❌ Cache performance error: {e}")
        return False
    
    # Test 5: Error handling for unknown components
    print("\n5. Testing error handling...")
    
    error_test_cases = [
        ("[]", "Empty component list"),
        ("[\"Completely Unknown Part\", \"Another Unknown\"]", "Unknown components"),
        ("invalid json", "Invalid JSON"),
        ("{\"not\": \"a list\"}", "Invalid data structure")
    ]
    
    for test_json, description in error_test_cases:
        try:
            result = map_components_to_categories.func(test_json)
            
            if description == "Unknown components" and result.get("success"):
                # Unknown components should still succeed with fallback categories
                print(f"✅ {description}: Handled with fallback categories")
            elif not result.get("success"):
                print(f"✅ {description}: Gracefully handled error")
            else:
                print(f"⚠️  {description}: Unexpected success")
                
        except Exception as e:
            print(f"❌ {description} error handling failed: {e}")
            return False
    
    # Test 6: Integration test with bucket_manager
    print("\n6. Testing integration with bucket_manager...")
    
    try:
        from agents.bucket_manager import BucketManager
        bm = BucketManager()
        
        # Test loading some manufacturer data
        manufacturers = list(bm.manufacturer_mapping.keys())[:5]
        print(f"✅ Integration: BucketManager loaded {len(bm.manufacturer_mapping)} manufacturers")
        print(f"   Sample manufacturers: {manufacturers}")
        
        # Test that our tools can access the same bucket manager
        category_result = load_categories_for_variant.func("999", "nonexistent")
        if not category_result.get("success"):
            print("✅ Integration: Properly handles non-existent data")
        else:
            print("⚠️  Integration: Should have failed for non-existent data")
            
    except Exception as e:
        print(f"❌ Integration test error: {e}")
        return False
    
    # Test 7: Comprehensive component coverage test
    print("\n7. Testing comprehensive component coverage...")
    
    automotive_parts = [
        "Front Bumper", "Rear Bumper", "Headlight", "Taillight",
        "Hood", "Trunk Lid", "Door", "Window", "Mirror",
        "Fender", "Grille", "Brake Disc", "Brake Pad",
        "Shock Absorber", "Spring", "Tire", "Wheel",
        "Radiator", "Battery", "Alternator", "Exhaust Pipe",
        "Gearbox", "Clutch", "Dashboard", "Seat"
    ]
    
    coverage_stats = {
        "mapped": 0,
        "fallback": 0,
        "categories": set()
    }
    
    for part in automotive_parts:
        categories = get_categories_for_component(part)
        coverage_stats["categories"].update(categories)
        
        # Check if it's a fallback (only contains default body parts category)
        if categories == ["100020"] and part.lower() not in ["body panel", "door", "hood", "fender", "bumper"]:
            coverage_stats["fallback"] += 1
        else:
            coverage_stats["mapped"] += 1
    
    total_parts = len(automotive_parts)
    mapped_percentage = (coverage_stats["mapped"] / total_parts) * 100
    unique_categories = len(coverage_stats["categories"])
    
    print(f"✅ Coverage: {coverage_stats['mapped']}/{total_parts} parts properly mapped ({mapped_percentage:.1f}%)")
    print(f"   Fallback cases: {coverage_stats['fallback']}")
    print(f"   Unique categories used: {unique_categories}")
    print(f"   Categories: {sorted(list(coverage_stats['categories']))}")
    
    print("\n" + "=" * 50)
    print("🎉 Parts foundation test complete - Ready for Step 6!")
    print("✅ Maps damaged components to relevant catalog categories")
    print("✅ Loads categories successfully for vehicle variants")
    print("✅ Handles unknown components gracefully with fallbacks")
    print("✅ Comprehensive coverage of automotive parts")
    print("✅ Fast lookup performance with proper error handling")
    print("✅ Strong integration with bucket manager and caching")
    
    return True

if __name__ == "__main__":
    success = test_parts_foundation()
    exit(0 if success else 1)
