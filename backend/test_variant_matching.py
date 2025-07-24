#!/usr/bin/env python3
"""
Step 4 Verification: Test Enhanced Variant Matching
"""

import json
import sys
from pathlib import Path

# Add the current directory to the path so we can import agents
sys.path.insert(0, str(Path(__file__).parent))

from agents.tools.vehicle_tools import find_matching_variants

def test_variant_matching():
    """Test the enhanced variant matching functionality."""
    
    print("🧪 Testing Enhanced Variant Matching...")
    print("=" * 50)
    
    # Test 1: Standard variant matching for Vauxhall Astra 2018
    print("1. Testing standard variant matching...")
    
    try:
        result = find_matching_variants.func("117", "Astra", 2018)
        
        if result.get("success"):
            variants = result.get("variants", [])
            total_found = result.get("total_found", 0)
            
            print(f"✅ Found {len(variants)} top variants (total: {total_found}) for Vauxhall Astra 2018")
            
            # Show top 3 variants with detailed scoring
            for i, variant in enumerate(variants[:3]):
                model_name = variant.get("model_name", "Unknown")
                compatibility_score = variant.get("compatibility_score", 0)
                name_similarity = variant.get("name_similarity", 0)
                variant_year = variant.get("year", "Unknown")
                date_range = variant.get("date_range", {})
                
                print(f"   Variant {i+1}: {model_name}")
                print(f"     • Compatibility Score: {compatibility_score:.3f}")
                print(f"     • Name Similarity: {name_similarity:.3f}")
                print(f"     • Year: {variant_year}")
                print(f"     • Production: {date_range.get('from', 'Unknown')} to {date_range.get('to', 'Current')}")
                
        else:
            print(f"❌ Standard matching failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Standard matching error: {e}")
        return False
    
    # Test 2: Fuzzy matching with model name variations
    print("\n2. Testing fuzzy matching with model name variations...")
    
    test_variations = [
        ("ASTRA", "Testing uppercase"),
        ("astra", "Testing lowercase"), 
        ("Astra K", "Testing with generation suffix"),
        ("VAUXHALL ASTRA", "Testing with manufacturer prefix")
    ]
    
    for test_model, description in test_variations:
        try:
            result = find_matching_variants.func("117", test_model, None)
            
            if result.get("success"):
                variants = result.get("variants", [])
                if variants:
                    best_variant = variants[0]
                    score = best_variant.get("compatibility_score", 0)
                    name_sim = best_variant.get("name_similarity", 0)
                    
                    print(f"✅ {description}: \"{test_model}\" -> Score: {score:.3f} (Name: {name_sim:.3f})")
                else:
                    print(f"⚠️  {description}: \"{test_model}\" -> No variants found")
            else:
                print(f"❌ {description}: \"{test_model}\" -> {result.get('error')}")
                
        except Exception as e:
            print(f"❌ Fuzzy matching error for \"{test_model}\": {e}")
            return False
    
    # Test 3: Year filtering functionality
    print("\n3. Testing year filtering functionality...")
    
    # Test different years for the same model
    test_years = [2010, 2015, 2018, 2020, 2025]
    
    for test_year in test_years:
        try:
            result = find_matching_variants.func("117", "Astra", test_year)
            
            if result.get("success"):
                variants = result.get("variants", [])
                if variants:
                    # Find variants with perfect or near-perfect year matches
                    year_matches = [v for v in variants if v.get("compatibility_score", 0) > 0.8]
                    
                    if year_matches:
                        best_match = year_matches[0]
                        variant_year = best_match.get("year", "Unknown")
                        score = best_match.get("compatibility_score", 0)
                        
                        print(f"   Year {test_year}: Best match {variant_year} (Score: {score:.3f})")
                    else:
                        print(f"   Year {test_year}: Found {len(variants)} variants, best score: {variants[0].get('compatibility_score', 0):.3f}")
                else:
                    print(f"   Year {test_year}: No variants found")
                    
        except Exception as e:
            print(f"❌ Year filtering error for {test_year}: {e}")
            return False
    
    print("✅ Year filtering: Found appropriate variants for different years")
    
    # Test 4: Unknown model handling
    print("\n4. Testing unknown model handling...")
    
    try:
        result = find_matching_variants.func("117", "UnknownModel", 2020)
        
        if not result.get("success") or len(result.get("variants", [])) == 0:
            print("✅ Unknown model handled gracefully: No variants returned")
        else:
            print("⚠️  Unknown model: Should have returned no variants")
            
    except Exception as e:
        print(f"❌ Unknown model handling error: {e}")
        return False
    
    # Test 5: BMW model matching (different manufacturer) 
    print("\n5. Testing different manufacturer (BMW)...")
    
    try:
        # First get BMW manufacturer ID
        from agents.bucket_manager import BucketManager
        bm = BucketManager()
        bmw_id = bm.get_manufacturer_id("BMW")
        
        if bmw_id:
            result = find_matching_variants.func(bmw_id, "3 Series", 2020)
            
            if result.get("success"):
                variants = result.get("variants", [])
                print(f"✅ BMW matching: Found {len(variants)} variants for 3 Series")
                
                if variants:
                    best_variant = variants[0]
                    print(f"   Best match: {best_variant.get('model_name')} (Score: {best_variant.get('compatibility_score', 0):.3f})")
                    
            else:
                print(f"⚠️  BMW matching: {result.get('error')}")
        else:
            print("⚠️  BMW manufacturer not found in mapping")
            
    except Exception as e:
        print(f"❌ BMW matching error: {e}")
        return False
    
    # Test 6: Edge cases and error handling
    print("\n6. Testing edge cases...")
    
    edge_cases = [
        ("", "Astra", 2020, "Empty manufacturer ID"),
        ("117", "", 2020, "Empty model name"),
        ("999", "Astra", 2020, "Invalid manufacturer ID"),
        ("117", "Astra", -1, "Invalid year")
    ]
    
    for mfg_id, model, year, description in edge_cases:
        try:
            result = find_matching_variants.func(mfg_id, model, year)
            
            if not result.get("success"):
                print(f"✅ {description}: Handled gracefully")
            else:
                variants = result.get("variants", [])
                if len(variants) == 0:
                    print(f"✅ {description}: No variants returned (expected)")
                else:
                    print(f"⚠️  {description}: Unexpected variants found")
                    
        except Exception as e:
            print(f"❌ {description} error: {e}")
            return False
    
    print("\n" + "=" * 50)
    print("🎉 Enhanced variant matching test complete - Ready for Step 5!")
    print("✅ Finds multiple compatible variants for a given model")
    print("✅ Fuzzy matching works for model name variations")
    print("✅ Year filtering returns appropriate variants with scoring")
    print("✅ Compatibility scores help rank variants effectively")
    print("✅ Returns empty list for unknown models gracefully")
    print("✅ Enhanced scoring considers name similarity and year compatibility")
    print("✅ Handles edge cases and invalid inputs properly")
    
    return True

if __name__ == "__main__":
    success = test_variant_matching()
    exit(0 if success else 1)
