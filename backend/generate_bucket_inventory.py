#!/usr/bin/env python3
"""
Generate comprehensive inventory of all manufacturers, models, and variants in the bucket.
This helps understand what data is actually available as the scraper continues to populate it.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add the current directory to the path so we can import agents
sys.path.insert(0, str(Path(__file__).parent))

from agents.bucket_manager import BucketManager

def generate_bucket_inventory():
    """Generate a comprehensive inventory of the bucket contents."""
    
    print("🔍 Generating Bucket Inventory...")
    print("=" * 60)
    
    bm = BucketManager()
    
    # Initialize inventory structure
    inventory = {
        "generated_at": datetime.now().isoformat(),
        "bucket_name": bm.bucket.name,
        "project_id": bm.project_id,
        "manufacturers": {},
        "summary": {
            "total_manufacturers": 0,
            "total_models": 0,
            "total_variants": 0,
            "manufacturers_with_models": 0,
            "models_with_variants": 0
        }
    }
    
    print("📋 Step 1: Scanning all manufacturer directories...")
    
    # Get all manufacturer directories
    manufacturer_dirs = set()
    blobs = bm.bucket.list_blobs(prefix="manufacturers/")
    
    for blob in blobs:
        # Extract manufacturer ID from path like "manufacturers/117/models.json"
        path_parts = blob.name.split('/')
        if len(path_parts) >= 2 and path_parts[0] == "manufacturers":
            manufacturer_id = path_parts[1]
            manufacturer_dirs.add(manufacturer_id)
    
    inventory["summary"]["total_manufacturers"] = len(manufacturer_dirs)
    print(f"   Found {len(manufacturer_dirs)} manufacturer directories")
    
    print("\n📊 Step 2: Processing each manufacturer...")
    
    processed_count = 0
    for manufacturer_id in sorted(manufacturer_dirs):
        processed_count += 1
        print(f"   Processing {processed_count}/{len(manufacturer_dirs)}: Manufacturer {manufacturer_id}")
        
        # Get manufacturer name from mapping
        manufacturer_name = None
        for name, mapped_id in bm.manufacturer_mapping.items():
            if mapped_id == manufacturer_id:
                manufacturer_name = name
                break
        
        # Initialize manufacturer entry
        manufacturer_info = {
            "id": manufacturer_id,
            "name": manufacturer_name or f"Unknown_{manufacturer_id}",
            "models": {},
            "model_count": 0,
            "variant_count": 0,
            "has_models_file": False,
            "article_files": []
        }
        
        # Try to load models for this manufacturer
        models = bm.get_models_for_manufacturer(manufacturer_id)
        
        if models is not None:
            manufacturer_info["has_models_file"] = True
            manufacturer_info["model_count"] = len(models)
            inventory["summary"]["manufacturers_with_models"] += 1
            inventory["summary"]["total_models"] += len(models)
            
            # Process each model
            for model in models:
                model_id = model.get("id", "unknown")
                model_name = model.get("name", "Unknown Model")
                variants = model.get("variants", [])
                
                model_info = {
                    "id": model_id,
                    "name": model_name,
                    "manufacturer_id": model.get("manufacturerId", manufacturer_id),
                    "url": model.get("url", ""),
                    "variants": [],
                    "variant_count": len(variants),
                    "additional_info": model.get("additionalInfo", {})
                }
                
                # Process variants
                for variant in variants:
                    variant_info = {
                        "id": variant.get("id", "unknown"),
                        "name": variant.get("name", ""),
                        "year": variant.get("year"),
                        "engine": variant.get("engine", ""),
                        "fuel_type": variant.get("fuel_type", ""),
                        "additional_info": {k: v for k, v in variant.items() 
                                         if k not in ["id", "name", "year", "engine", "fuel_type"]}
                    }
                    model_info["variants"].append(variant_info)
                
                manufacturer_info["models"][model_id] = model_info
                manufacturer_info["variant_count"] += len(variants)
                inventory["summary"]["total_variants"] += len(variants)
                
                if len(variants) > 0:
                    inventory["summary"]["models_with_variants"] += 1
        
        # Scan for article files
        article_prefix = f"manufacturers/{manufacturer_id}/articles_"
        article_blobs = bm.bucket.list_blobs(prefix=article_prefix)
        
        for blob in article_blobs:
            if blob.name.endswith('.json'):
                # Extract article file info
                filename = blob.name.split('/')[-1]  # Get just the filename
                manufacturer_info["article_files"].append({
                    "filename": filename,
                    "full_path": blob.name,
                    "size_bytes": blob.size,
                    "updated": blob.updated.isoformat() if blob.updated else None
                })
        
        inventory["manufacturers"][manufacturer_id] = manufacturer_info
    
    print(f"\n✅ Step 3: Inventory generation complete!")
    print(f"   📊 Summary Statistics:")
    print(f"   • Total Manufacturers: {inventory['summary']['total_manufacturers']}")
    print(f"   • Manufacturers with Models: {inventory['summary']['manufacturers_with_models']}")
    print(f"   • Total Models: {inventory['summary']['total_models']}")
    print(f"   • Models with Variants: {inventory['summary']['models_with_variants']}")
    print(f"   • Total Variants: {inventory['summary']['total_variants']}")
    
    return inventory

def save_inventory_files(inventory):
    """Save inventory in multiple formats for different use cases."""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Full detailed inventory
    full_filename = f"bucket_inventory_full_{timestamp}.json"
    with open(full_filename, 'w') as f:
        json.dump(inventory, f, indent=2)
    print(f"📄 Full inventory saved: {full_filename}")
    
    # 2. Summary-only version
    summary_data = {
        "generated_at": inventory["generated_at"],
        "bucket_name": inventory["bucket_name"],
        "project_id": inventory["project_id"],
        "summary": inventory["summary"],
        "manufacturer_list": [
            {
                "id": mfg_id,
                "name": mfg_data["name"],
                "model_count": mfg_data["model_count"],
                "variant_count": mfg_data["variant_count"],
                "has_models_file": mfg_data["has_models_file"],
                "article_files_count": len(mfg_data["article_files"])
            }
            for mfg_id, mfg_data in inventory["manufacturers"].items()
        ]
    }
    
    summary_filename = f"bucket_inventory_summary_{timestamp}.json"
    with open(summary_filename, 'w') as f:
        json.dump(summary_data, f, indent=2)
    print(f"📋 Summary inventory saved: {summary_filename}")
    
    # 3. Testing-friendly lookup format
    lookup_data = {
        "generated_at": inventory["generated_at"],
        "manufacturer_model_combinations": [],
        "available_manufacturers": {},
        "quick_lookup": {}
    }
    
    for mfg_id, mfg_data in inventory["manufacturers"].items():
        mfg_name = mfg_data["name"]
        lookup_data["available_manufacturers"][mfg_id] = mfg_name
        lookup_data["quick_lookup"][mfg_name.upper()] = mfg_id
        
        for model_id, model_data in mfg_data["models"].items():
            model_name = model_data["name"]
            combo = {
                "manufacturer_id": mfg_id,
                "manufacturer_name": mfg_name,
                "model_id": model_id,
                "model_name": model_name,
                "variant_count": model_data["variant_count"],
                "variants": [v["name"] for v in model_data["variants"]]
            }
            lookup_data["manufacturer_model_combinations"].append(combo)
    
    lookup_filename = f"bucket_inventory_lookup_{timestamp}.json"
    with open(lookup_filename, 'w') as f:
        json.dump(lookup_data, f, indent=2)
    print(f"🔍 Lookup inventory saved: {lookup_filename}")
    
    # 4. Create a latest symlink for easy reference
    try:
        import os
        if os.path.exists("bucket_inventory_latest.json"):
            os.remove("bucket_inventory_latest.json")
        os.symlink(full_filename, "bucket_inventory_latest.json")
        print(f"🔗 Latest inventory linked: bucket_inventory_latest.json")
    except:
        print("   (Could not create symlink - not critical)")
    
    return full_filename, summary_filename, lookup_filename

def print_interesting_findings(inventory):
    """Print some interesting findings from the inventory."""
    
    print(f"\n🔍 Interesting Findings:")
    print("=" * 40)
    
    # Find manufacturers with most models
    mfg_by_models = [(mfg_data["model_count"], mfg_data["name"], mfg_id) 
                     for mfg_id, mfg_data in inventory["manufacturers"].items()]
    mfg_by_models.sort(reverse=True)
    
    print("🏆 Top 5 Manufacturers by Model Count:")
    for i, (count, name, mfg_id) in enumerate(mfg_by_models[:5]):
        print(f"   {i+1}. {name} (ID: {mfg_id}): {count} models")
    
    # Find models with most variants
    model_variants = []
    for mfg_id, mfg_data in inventory["manufacturers"].items():
        for model_id, model_data in mfg_data["models"].items():
            if model_data["variant_count"] > 0:
                model_variants.append((
                    model_data["variant_count"],
                    model_data["name"],
                    mfg_data["name"]
                ))
    
    model_variants.sort(reverse=True)
    
    print("\n🚗 Top 5 Models by Variant Count:")
    for i, (count, model_name, mfg_name) in enumerate(model_variants[:5]):
        print(f"   {i+1}. {model_name} ({mfg_name}): {count} variants")
    
    # Show manufacturers with article files
    mfg_with_articles = [(len(mfg_data["article_files"]), mfg_data["name"], mfg_id)
                        for mfg_id, mfg_data in inventory["manufacturers"].items()
                        if len(mfg_data["article_files"]) > 0]
    mfg_with_articles.sort(reverse=True)
    
    print("\n📦 Top 5 Manufacturers by Article Files:")
    for i, (count, name, mfg_id) in enumerate(mfg_with_articles[:5]):
        print(f"   {i+1}. {name} (ID: {mfg_id}): {count} article files")

if __name__ == "__main__":
    try:
        # Generate the inventory
        inventory = generate_bucket_inventory()
        
        # Save in multiple formats
        full_file, summary_file, lookup_file = save_inventory_files(inventory)
        
        # Print interesting findings
        print_interesting_findings(inventory)
        
        print(f"\n🎉 Bucket inventory generation complete!")
        print(f"📁 Files generated:")
        print(f"   • Full inventory: {full_file}")
        print(f"   • Summary: {summary_file}")
        print(f"   • Lookup format: {lookup_file}")
        print(f"   • Latest symlink: bucket_inventory_latest.json")
        
        print(f"\n💡 Usage recommendations:")
        print(f"   • Use lookup format for testing vehicle combinations")
        print(f"   • Use summary for quick statistics and overview")
        print(f"   • Use full inventory for detailed analysis")
        print(f"   • Re-run this script periodically as scraper adds data")
        
    except Exception as e:
        print(f"❌ Error generating inventory: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
