"""
Vehicle identification and validation tools for the agentic parts discovery system
"""

import json
import sys
from typing import Dict, List, Any
from pathlib import Path
from difflib import SequenceMatcher

# Import LangChain tool decorator
from langchain.tools import tool

# Add parent directory to path for bucket_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))
from bucket_manager import BucketManager

# Global bucket manager instance
bucket_manager = None

def get_bucket_manager():
    """Get or create global bucket manager instance."""
    global bucket_manager
    if bucket_manager is None:
        bucket_manager = BucketManager()
    return bucket_manager

@tool
def identify_vehicle_from_report(damage_report_json: str, vehicle_info_json: str) -> Dict:
    """
    Extract and validate vehicle information from damage report and vehicle info JSON.
    
    Args:
        damage_report_json: JSON string containing damage report data
        vehicle_info_json: JSON string containing vehicle information
        
    Returns:
        Dict with vehicle identification results including manufacturer_id, make, model, year
    """
    try:
        bm = get_bucket_manager()
        
        # Parse JSON inputs
        damage_report = json.loads(damage_report_json) if damage_report_json else {}
        vehicle_info = json.loads(vehicle_info_json) if vehicle_info_json else {}
        
        # Extract vehicle information with fallback fields
        make = None
        model = None
        year = None
        
        # Try multiple field variations for make
        for field in ['make', 'vehicle_make', 'manufacturer', 'brand']:
            if field in vehicle_info and vehicle_info[field]:
                make = str(vehicle_info[field]).strip()
                break
            elif field in damage_report and damage_report[field]:
                make = str(damage_report[field]).strip()
                break
        
        # Try multiple field variations for model
        for field in ['model', 'vehicle_model', 'model_name']:
            if field in vehicle_info and vehicle_info[field]:
                model = str(vehicle_info[field]).strip()
                break
            elif field in damage_report and damage_report[field]:
                model = str(damage_report[field]).strip()
                break
        
        # Try multiple field variations for year
        for field in ['year', 'vehicle_year', 'model_year', 'registration_year']:
            if field in vehicle_info and vehicle_info[field]:
                try:
                    year = int(vehicle_info[field])
                    break
                except (ValueError, TypeError):
                    continue
            elif field in damage_report and damage_report[field]:
                try:
                    year = int(damage_report[field])
                    break
                except (ValueError, TypeError):
                    continue
        
        # Validate required fields
        if not make:
            return {
                "success": False,
                "error": "Vehicle make not found in provided data",
                "fields_checked": ['make', 'vehicle_make', 'manufacturer', 'brand']
            }
        
        if not model:
            return {
                "success": False,
                "error": "Vehicle model not found in provided data", 
                "fields_checked": ['model', 'vehicle_model', 'model_name']
            }
        
        # Map manufacturer name to catalog ID
        manufacturer_id = bm.get_manufacturer_id(make)
        if not manufacturer_id:
            return {
                "success": False,
                "error": f"Unknown manufacturer: {make}",
                "make": make,
                "available_manufacturers": list(bm.manufacturer_mapping.keys())[:10]
            }
        
        # Calculate confidence based on data quality
        confidence = 1.0
        if not year:
            confidence -= 0.2
        
        return {
            "success": True,
            "manufacturer_id": manufacturer_id,
            "make": make.upper(),
            "model": model,
            "year": year,
            "confidence": confidence
        }
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Invalid JSON input: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Vehicle identification failed: {str(e)}"
        }

@tool
def validate_vehicle_in_catalog(manufacturer_id: str, model_name: str) -> Dict:
    """
    Validate if a vehicle exists in the parts catalog.
    
    Args:
        manufacturer_id: Manufacturer ID from catalog (e.g., "117")
        model_name: Vehicle model name (e.g., "Astra")
        
    Returns:
        Dict with validation results and available models
    """
    try:
        bm = get_bucket_manager()
        
        if not manufacturer_id or not model_name:
            return {
                "valid": False,
                "error": "Missing manufacturer_id or model_name"
            }
        
        # Load models for the manufacturer
        models = bm.get_models_for_manufacturer(manufacturer_id)
        if models is None:
            return {
                "valid": False,
                "error": f"No models found for manufacturer {manufacturer_id}",
                "available_models": []
            }
        
        if len(models) == 0:
            return {
                "valid": False,
                "error": f"Manufacturer {manufacturer_id} has no models in catalog",
                "available_models": []
            }
        
        # Check for model matches
        model_name_upper = model_name.upper()
        exact_matches = []
        fuzzy_matches = []
        
        for model in models:
            model_catalog_name = model.get("name", "").upper()
            
            # Exact match (full name or just the model part)
            if model_catalog_name == model_name_upper or model_name_upper in model_catalog_name:
                # Check if it's a meaningful match (not just a substring)
                if (model_catalog_name == model_name_upper or 
                    model_catalog_name.endswith(model_name_upper) or
                    f" {model_name_upper}" in model_catalog_name or
                    f" {model_name_upper} " in model_catalog_name):
                    exact_matches.append(model)
            else:
                # Use fuzzy matching for partial matches
                similarity = SequenceMatcher(None, model_name_upper, model_catalog_name).ratio()
                if similarity > 0.4:  # Lower threshold for fuzzy matching
                    fuzzy_matches.append({
                        "model": model,
                        "similarity": similarity
                    })
        
        # Sort fuzzy matches by similarity
        fuzzy_matches.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Get list of available models for reference
        available_models = [model.get("name") for model in models[:10]]  # First 10 for brevity
        
        return {
            "valid": len(exact_matches) > 0 or len(fuzzy_matches) > 0,
            "exact_matches": exact_matches,
            "fuzzy_matches": [fm["model"] for fm in fuzzy_matches],
            "similarity_scores": [fm["similarity"] for fm in fuzzy_matches],
            "available_models": available_models,
            "total_models": len(models)
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": f"Catalog validation failed: {str(e)}"
        }

@tool 
def find_matching_variants(manufacturer_id: str, model_name: str, year: int = None) -> Dict:
    """
    Find vehicle variants that match the given manufacturer, model, and optionally year.
    
    Args:
        manufacturer_id: Manufacturer ID from catalog (e.g., "117")
        model_name: Vehicle model name (e.g., "Astra")
        year: Optional vehicle year for filtering (e.g., 2018)
        
    Returns:
        Dict with matching variants and compatibility scores
    """
    try:
        bm = get_bucket_manager()
        
        if not manufacturer_id or not model_name:
            return {
                "success": False,
                "error": "Missing manufacturer_id or model_name",
                "variants": []
            }
        
        # Load models for the manufacturer
        models = bm.get_models_for_manufacturer(manufacturer_id)
        if models is None:
            return {
                "success": False,
                "error": f"No models found for manufacturer {manufacturer_id}",
                "variants": []
            }
        
        if len(models) == 0:
            return {
                "success": False,
                "error": f"Manufacturer {manufacturer_id} has no models in catalog",
                "variants": []
            }
        
        # Find matching models and their variants
        matching_variants = []
        model_name_upper = model_name.upper()
        
        for model in models:
            model_catalog_name = model.get("name", "").upper()
            
            # Calculate model name similarity - check for exact or partial match first
            name_similarity = 0.0
            
            if (model_catalog_name == model_name_upper or 
                model_name_upper in model_catalog_name or
                f" {model_name_upper}" in model_catalog_name or
                f" {model_name_upper} " in model_catalog_name):
                name_similarity = 0.9  # High score for exact/partial matches
            else:
                name_similarity = SequenceMatcher(None, model_name_upper, model_catalog_name).ratio()
            
            if name_similarity > 0.4:  # Lower threshold
                # Get variants for this model
                variants = model.get("variants", [])
                
                for variant in variants:
                    variant_year = variant.get("year")
                    variant_score = name_similarity
                    
                    # Boost score if year matches
                    if year and variant_year:
                        try:
                            if int(variant_year) == int(year):
                                variant_score += 0.3  # Year match bonus
                            elif abs(int(variant_year) - int(year)) <= 2:
                                variant_score += 0.1  # Close year bonus
                        except (ValueError, TypeError):
                            pass
                    
                    matching_variants.append({
                        "model_name": model.get("name"),
                        "variant_id": variant.get("id"),
                        "variant_name": variant.get("name", ""),
                        "year": variant_year,
                        "compatibility_score": min(variant_score, 1.0),
                        "engine": variant.get("engine", ""),
                        "fuel_type": variant.get("fuel_type", "")
                    })
        
        # Sort by compatibility score (highest first)
        matching_variants.sort(key=lambda x: x["compatibility_score"], reverse=True)
        
        # Return top 5 matches
        top_variants = matching_variants[:5]
        
        return {
            "success": True,
            "variants": top_variants,
            "total_found": len(matching_variants),
            "search_criteria": {
                "manufacturer_id": manufacturer_id,
                "model_name": model_name,
                "year": year
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Variant matching failed: {str(e)}",
            "variants": []
        }

# Export tools for LangChain agent use
vehicle_identification_tools = [
    identify_vehicle_from_report,
    validate_vehicle_in_catalog,
    find_matching_variants
]
