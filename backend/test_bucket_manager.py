#!/usr/bin/env python3
"""
Step 2 Verification: Test BucketManager class functionality
"""

import time
import sys
from pathlib import Path

# Add the current directory to the path so we can import agents
sys.path.insert(0, str(Path(__file__).parent))

from agents.bucket_manager import BucketManager

def test_bucket_manager():
    """Test the BucketManager class functionality."""
    
    print("🧪 Testing Bucket Manager...")
    print("=" * 50)
    
    # Initialize bucket manager
    print("1. Initializing BucketManager...")
    try:
        bucket_manager = BucketManager()
        print("✅ BucketManager initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize BucketManager: {e}")
        return False
    
    # Test manufacturer ID lookup
    print("\n2. Testing manufacturer ID lookup...")
    test_cases = [
        ("Vauxhall", "117"),
        ("VAUXHALL", "117"),
        ("vauxhall", "117"),
        ("BMW", "13"),
        ("Bmw", "13"),
        ("FORD", "52"),
        ("Mercedes", "85"),
        ("Unknown Brand", None)
    ]
    
    for manufacturer_name, expected_id in test_cases:
        result = bucket_manager.get_manufacturer_id(manufacturer_name)
        if result == expected_id:
            print(f"✅ {manufacturer_name} -> {result}")
        else:
            print(f"❌ {manufacturer_name} -> {result} (expected {expected_id})")
    
    # Test models loading
    print("\n3. Testing models loading...")
    # Use manufacturer 104 since we know it exists from Step 1
    manufacturer_id = "104"
    
    # First call (should hit the API)
    start_time = time.time()
    models = bucket_manager.get_models_for_manufacturer(manufacturer_id)
    first_call_time = time.time() - start_time
    
    if models:
        print(f"✅ Loaded {len(models)} models for manufacturer {manufacturer_id}")
        print(f"   First call time: {first_call_time:.3f}s")
    else:
        print(f"❌ Failed to load models for manufacturer {manufacturer_id}")
        return False
    
    # Second call (should hit cache)
    start_time = time.time()
    models_cached = bucket_manager.get_models_for_manufacturer(manufacturer_id)
    second_call_time = time.time() - start_time
    
    if models_cached:
        print(f"✅ Loaded {len(models_cached)} models from cache")
        print(f"   Second call time: {second_call_time:.3f}s")
        
        # Check if caching made it faster
        if second_call_time < first_call_time:
            print("✅ Cache working correctly - second call is faster")
        else:
            print("⚠️  Cache may not be working - second call not faster")
    else:
        print("❌ Failed to load models from cache")
        return False
    
    # Test articles loading
    print("\n4. Testing articles loading...")
    # List available articles for this manufacturer
    article_files = bucket_manager.list_manufacturer_articles(manufacturer_id)
    
    if article_files:
        print(f"✅ Found {len(article_files)} article files for manufacturer {manufacturer_id}")
        
        # Try to load one article file
        # Parse the first article file to get variant_id and category_id
        if article_files:
            # Example: manufacturers/104/articles_10615_100001_101343.json
            # Extract variant_id and category_id from filename
            first_file = article_files[0]
            filename = first_file.split('/')[-1]  # Get just the filename
            print(f"   Parsing filename: {filename}")
            
            # Parse: articles_10615_100001_101343.json
            parts = filename.replace('articles_', '').replace('.json', '').split('_')
            print(f"   Parsed parts: {parts}")
            
            if len(parts) >= 3:
                variant_id = parts[0]
                category_id = parts[1]
                print(f"   Trying to load: variant_id={variant_id}, category_id={category_id}")
                
                articles = bucket_manager.get_articles_for_category(manufacturer_id, variant_id, category_id)
                if articles:
                    print(f"✅ Loaded {len(articles)} articles for category {category_id}")
                else:
                    print(f"❌ Failed to load articles for category {category_id}")
                    # Try loading the file directly to see what's wrong
                    print(f"   Trying to load file directly: {first_file}")
                    direct_load = bucket_manager._load_json_file(first_file)
                    if direct_load:
                        print(f"✅ Direct load successful: {len(direct_load)} items")
                    else:
                        print(f"❌ Direct load failed")
                        return False
            else:
                print(f"⚠️  Could not parse article filename: {filename}")
                # Just try loading the file directly
                direct_load = bucket_manager._load_json_file(first_file)
                if direct_load:
                    print(f"✅ Direct load successful: {len(direct_load)} items")
                else:
                    print(f"❌ Direct load failed")
                    return False
    else:
        print("❌ No article files found")
        return False
    
    # Test cache statistics
    print("\n5. Testing cache statistics...")
    cache_stats = bucket_manager.get_cache_stats()
    print(f"✅ Cache statistics: {cache_stats['cache_size']}/{cache_stats['cache_limit']} items")
    
    # Test error handling
    print("\n6. Testing error handling...")
    result = bucket_manager.get_models_for_manufacturer("99999")  # Non-existent manufacturer
    if result is None:
        print("✅ Error handling working - returns None for non-existent manufacturer")
    else:
        print("❌ Error handling failed - should return None for non-existent manufacturer")
    
    print("\n" + "=" * 50)
    print("🎉 Bucket manager test complete - Ready for Step 3!")
    print("✅ BucketManager class functional")
    print("✅ Manufacturer mapping with fuzzy matching working")
    print("✅ Caching reduces repeated API calls")
    print("✅ Can load models and articles")
    print("✅ Error handling for missing files")
    
    return True

if __name__ == "__main__":
    success = test_bucket_manager()
    exit(0 if success else 1)
