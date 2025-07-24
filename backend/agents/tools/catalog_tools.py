"""
Catalog tools for component-to-category mapping and parts searching
"""

import json
import sys
import re
from typing import Dict, List, Any, Optional, Tuple
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

# Comprehensive component to category mapping based on automotive catalog structure
COMPONENT_CATEGORY_MAPPING = {
    # FRONT END COMPONENTS
    "Front Bumper Cover": ["100020"],  # Body Parts
    "Front Bumper": ["100020"],
    "Bumper Cover": ["100020"],
    "Headlight Assembly": ["100021"],  # Lighting
    "Headlight": ["100021"],
    "Front Headlight": ["100021"],
    "Headlamp": ["100021"],
    "Grille": ["100020"],
    "Front Grille": ["100020"],
    "Radiator Grille": ["100020"],
    "Fog Light": ["100021"],
    "Fog Lamp": ["100021"],
    "Front Fog Light": ["100021"],
    "Turn Signal": ["100021"],
    "Front Turn Signal": ["100021"],
    "Hood": ["100020"],
    "Bonnet": ["100020"],
    
    # SIDE COMPONENTS  
    "Left Front Fender": ["100020"],
    "Right Front Fender": ["100020"],
    "Left Fender": ["100020"],
    "Right Fender": ["100020"],
    "Fender": ["100020"],
    "Front Fender": ["100020"],
    "Rear Fender": ["100020"],
    "Door Panel": ["100020"],
    "Door": ["100020"],
    "Front Door": ["100020"],
    "Rear Door": ["100020"],
    "Left Door": ["100020"],
    "Right Door": ["100020"],
    "Side Mirror": ["100021", "100015"],  # Lighting + Electrical
    "Mirror": ["100021", "100015"],
    "Wing Mirror": ["100021", "100015"],
    "Door Mirror": ["100021", "100015"],
    "Window": ["100022"],  # Glass & Mirrors
    "Side Window": ["100022"],
    "Door Window": ["100022"],
    "Window Glass": ["100022"],
    "Window Regulator": ["100015"],  # Electrical
    "Door Handle": ["100020", "100015"],
    "Side Skirt": ["100020"],
    
    # REAR COMPONENTS
    "Rear Bumper": ["100020"],
    "Rear Bumper Cover": ["100020"],
    "Taillight Assembly": ["100021"],
    "Taillight": ["100021"],
    "Tail Light": ["100021"],
    "Rear Light": ["100021"],
    "Brake Light": ["100021"],
    "Reverse Light": ["100021"],
    "Rear Turn Signal": ["100021"],
    "Rear Window": ["100022"],
    "Back Window": ["100022"],
    "Rear Windscreen": ["100022"],
    "Trunk Lid": ["100020"],
    "Boot Lid": ["100020"],
    "Tailgate": ["100020"],
    "Rear Hatch": ["100020"],
    "License Plate Light": ["100021"],
    "Number Plate Light": ["100021"],
    
    # ROOF AND TOP
    "Roof": ["100020"],
    "Sunroof": ["100022", "100015"],
    "Roof Rails": ["100020"],
    "Antenna": ["100015"],
    
    # WINDSCREEN AND GLASS
    "Windscreen": ["100022"],
    "Windshield": ["100022"],
    "Front Windscreen": ["100022"],
    "Windscreen Wipers": ["100015"],
    "Wipers": ["100015"],
    "Wiper Blades": ["100015"],
    "Windscreen Washer": ["100015"],
    
    # ENGINE BAY COMPONENTS
    "Radiator": ["100008"],  # Cooling System
    "Radiator Fan": ["100008", "100015"],
    "Cooling Fan": ["100008", "100015"],
    "Engine Mount": ["100001"],  # Engine
    "Engine Block": ["100001"],
    "Cylinder Head": ["100001"],
    "Intake Manifold": ["100001"],
    "Exhaust Manifold": ["100001"],
    "Battery": ["100015"],  # Electrical
    "Car Battery": ["100015"],
    "Alternator": ["100015"],
    "Starter Motor": ["100015"],
    "Starter": ["100015"],
    "Air Filter": ["100001"],
    "Air Filter Housing": ["100001"],
    "Oil Filter": ["100001"],
    "Fuel Filter": ["100001"],
    "Spark Plugs": ["100001"],
    "Ignition Coil": ["100015"],
    "Fuel Injector": ["100001"],
    "Throttle Body": ["100001"],
    "ECU": ["100015"],
    "Engine Control Unit": ["100015"],
    
    # BRAKE SYSTEM
    "Brake Disc": ["100006"],  # Brake System
    "Brake Rotor": ["100006"],
    "Brake Pad": ["100006"],
    "Brake Pads": ["100006"],
    "Brake Caliper": ["100006"],
    "Brake Caliper Piston": ["100006"],
    "Brake Booster": ["100006"],
    "Brake Master Cylinder": ["100006"],
    "Brake Line": ["100006"],
    "Brake Hose": ["100006"],
    "Brake Fluid Reservoir": ["100006"],
    "Handbrake": ["100006"],
    "Parking Brake": ["100006"],
    "ABS Sensor": ["100015", "100006"],
    
    # SUSPENSION & STEERING
    "Shock Absorber": ["100004"],  # Suspension & Steering
    "Strut": ["100004"],
    "Front Strut": ["100004"],
    "Rear Strut": ["100004"],
    "Spring": ["100004"],
    "Coil Spring": ["100004"],
    "Control Arm": ["100004"],
    "Wishbone": ["100004"],
    "Ball Joint": ["100004"],
    "Tie Rod": ["100004"],
    "Steering Rack": ["100004"],
    "Power Steering Pump": ["100004"],
    "Steering Column": ["100004"],
    "Anti Roll Bar": ["100004"],
    "Sway Bar": ["100004"],
    "Stabilizer Bar": ["100004"],
    
    # WHEELS AND TYRES
    "Wheel": ["100005"],  # Wheels & Tyres
    "Rim": ["100005"],
    "Alloy Wheel": ["100005"],
    "Steel Wheel": ["100005"],
    "Tyre": ["100005"],
    "Tire": ["100005"],
    "Wheel Bearing": ["100005"],
    "Hub Cap": ["100005"],
    "Wheel Hub": ["100005"],
    
    # INTERIOR COMPONENTS
    "Dashboard": ["100016"],  # Interior
    "Dash": ["100016"],
    "Instrument Panel": ["100016"],
    "Instrument Cluster": ["100015", "100016"],
    "Seat": ["100016"],
    "Front Seat": ["100016"],
    "Rear Seat": ["100016"],
    "Driver Seat": ["100016"],
    "Passenger Seat": ["100016"],
    "Seat Belt": ["100016"],
    "Seatbelt": ["100016"],
    "Steering Wheel": ["100015", "100016"],  # Electrical (airbag)
    "Center Console": ["100016"],
    "Centre Console": ["100016"],
    "Door Panel Interior": ["100016"],
    "Interior Door Panel": ["100016"],
    "Glove Box": ["100016"],
    "Glovebox": ["100016"],
    "Armrest": ["100016"],
    "Cup Holder": ["100016"],
    "Floor Mat": ["100016"],
    "Carpet": ["100016"],
    "Headliner": ["100016"],
    "Sun Visor": ["100016"],
    "Interior Light": ["100015"],
    "Dome Light": ["100015"],
    "Reading Light": ["100015"],
    
    # AIRBAG SYSTEM
    "Airbag": ["100015"],
    "Driver Airbag": ["100015"],
    "Passenger Airbag": ["100015"],
    "Side Airbag": ["100015"],
    "Curtain Airbag": ["100015"],
    "Airbag Sensor": ["100015"],
    
    # EXHAUST SYSTEM
    "Exhaust Pipe": ["100003"],  # Exhaust System
    "Exhaust System": ["100003"],
    "Muffler": ["100003"],
    "Silencer": ["100003"],
    "Catalytic Converter": ["100003"],
    "Cat Converter": ["100003"],
    "Exhaust Manifold": ["100003"],
    "Exhaust Gasket": ["100003"],
    "Lambda Sensor": ["100015", "100003"],
    "Oxygen Sensor": ["100015", "100003"],
    
    # TRANSMISSION & DRIVETRAIN
    "Gearbox": ["100002"],  # Transmission
    "Transmission": ["100002"],
    "Manual Transmission": ["100002"],
    "Automatic Transmission": ["100002"],
    "CVT": ["100002"],
    "Clutch": ["100002"],
    "Clutch Disc": ["100002"],
    "Clutch Plate": ["100002"],
    "Pressure Plate": ["100002"],
    "Flywheel": ["100002"],
    "Drive Shaft": ["100002"],
    "Driveshaft": ["100002"],
    "CV Joint": ["100002"],
    "Differential": ["100002"],
    "Transfer Case": ["100002"],
    
    # FUEL SYSTEM
    "Fuel Tank": ["100001"],
    "Fuel Pump": ["100001", "100015"],
    "Fuel Rail": ["100001"],
    "Fuel Line": ["100001"],
    "Fuel Cap": ["100001"],
    "Filler Cap": ["100001"],
    
    # CLIMATE CONTROL
    "Air Conditioning": ["100015"],
    "AC Compressor": ["100015"],
    "AC Condenser": ["100008", "100015"],
    "Heater Core": ["100008"],
    "Blower Motor": ["100015"],
    "Climate Control Unit": ["100015"],
    
    # ELECTRICAL COMPONENTS
    "Fuse Box": ["100015"],
    "Relay": ["100015"],
    "Wiring Harness": ["100015"],
    "Headlight Switch": ["100015"],
    "Turn Signal Switch": ["100015"],
    "Hazard Switch": ["100015"],
    "Power Window Switch": ["100015"],
    "Central Locking": ["100015"],
    "Remote Key": ["100015"],
    "Key Fob": ["100015"],
    
    # GENERIC FALLBACKS
    "Body Panel": ["100020"],
    "Light": ["100021"],
    "Electrical Component": ["100015"],
    "Engine Component": ["100001"],
    "Brake Component": ["100006"],
    "Suspension Component": ["100004"]
}

def get_categories_for_component(component_name: str) -> List[str]:
    """
    Map a damaged component to relevant catalog categories.
    
    Args:
        component_name: Name of the damaged component
    
    Returns:
        List of category IDs to search
    """
    component_clean = component_name.strip()
    
    # Try exact match first
    if component_clean in COMPONENT_CATEGORY_MAPPING:
        return COMPONENT_CATEGORY_MAPPING[component_clean]
    
    # Try case-insensitive match
    for mapped_component, categories in COMPONENT_CATEGORY_MAPPING.items():
        if component_clean.upper() == mapped_component.upper():
            return categories
    
    # Try partial matching with fuzzy logic
    best_matches = []
    component_upper = component_clean.upper()
    
    for mapped_component, categories in COMPONENT_CATEGORY_MAPPING.items():
        mapped_upper = mapped_component.upper()
        
        # Check if component name contains mapped component or vice versa
        if (component_upper in mapped_upper or mapped_upper in component_upper):
            similarity = SequenceMatcher(None, component_upper, mapped_upper).ratio()
            if similarity > 0.6:  # 60% similarity threshold
                best_matches.append((similarity, categories))
        
        # Check for keyword matches
        component_words = set(component_upper.split())
        mapped_words = set(mapped_upper.split())
        word_overlap = len(component_words.intersection(mapped_words))
        
        if word_overlap > 0:
            word_similarity = word_overlap / max(len(component_words), len(mapped_words))
            if word_similarity > 0.5:  # 50% word overlap
                best_matches.append((word_similarity, categories))
    
    if best_matches:
        # Sort by similarity and return categories from best match
        best_matches.sort(reverse=True)
        return best_matches[0][1]
    
    # Fallback: return generic body parts category
    return ["100020"]  # Body Parts as default

@tool
def map_components_to_categories(damaged_components_json: str) -> Dict:
    """
    Map damaged components from damage report to catalog categories.
    
    Args:
        damaged_components_json: JSON string containing list of damaged components
        
    Returns:
        Dict with component mapping results and category IDs
    """
    try:
        damaged_components = json.loads(damaged_components_json)
        
        if not isinstance(damaged_components, list):
            return {
                "success": False,
                "error": "Expected list of damaged components",
                "mapping": {}
            }
        
        if len(damaged_components) == 0:
            return {
                "success": False,
                "error": "Empty component list provided",
                "component_mapping": {},
                "all_categories": [],
                "total_components": 0,
                "total_categories": 0
            }
        
        component_mapping = {}
        all_categories = set()
        
        for component in damaged_components:
            if isinstance(component, dict):
                component_name = component.get("name", "") or component.get("component", "")
            else:
                component_name = str(component)
            
            if component_name:
                categories = get_categories_for_component(component_name)
                component_mapping[component_name] = {
                    "categories": categories,
                    "category_count": len(categories)
                }
                all_categories.update(categories)
        
        return {
            "success": True,
            "component_mapping": component_mapping,
            "all_categories": list(all_categories),
            "total_components": len(component_mapping),
            "total_categories": len(all_categories)
        }
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Invalid JSON input: {str(e)}",
            "mapping": {}
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Component mapping failed: {str(e)}",
            "mapping": {}
        }

@tool
def load_categories_for_variant(manufacturer_id: str, variant_id: str) -> Dict:
    """
    Load available categories for a specific vehicle variant.
    
    Args:
        manufacturer_id: Manufacturer ID from catalog (e.g., "117")
        variant_id: Vehicle variant ID (e.g., "127445")
        
    Returns:
        Dict with available categories and metadata
    """
    try:
        bm = get_bucket_manager()
        
        if not manufacturer_id or not variant_id:
            return {
                "success": False,
                "error": "Missing manufacturer_id or variant_id",
                "categories": []
            }
        
        # List all article files for this manufacturer/variant combination
        article_prefix = f"manufacturers/{manufacturer_id}/articles_{variant_id}_"
        
        try:
            blobs = list(bm.bucket.list_blobs(prefix=article_prefix))
        except Exception as e:
            return {
                "success": False,
                "error": f"Error accessing catalog data: {str(e)}",
                "categories": []
            }
        
        # Extract categories from article filenames
        categories = {}
        
        for blob in blobs:
            if blob.name.endswith('.json'):
                # Extract category from filename pattern: articles_{variant}_{category}_{id}.json
                filename = blob.name.split('/')[-1]  # Get just the filename
                parts = filename.replace('.json', '').split('_')
                
                if len(parts) >= 4 and parts[0] == "articles":
                    try:
                        file_variant = parts[1]
                        category_id = parts[2]
                        article_id = parts[3]
                        
                        if file_variant == variant_id:
                            if category_id not in categories:
                                categories[category_id] = {
                                    "category_id": category_id,
                                    "article_count": 0,
                                    "articles": []
                                }
                            
                            categories[category_id]["article_count"] += 1
                            categories[category_id]["articles"].append({
                                "article_id": article_id,
                                "filename": filename,
                                "blob_name": blob.name,
                                "size_bytes": blob.size,
                                "updated": blob.updated.isoformat() if blob.updated else None
                            })
                    except (IndexError, ValueError):
                        continue  # Skip malformed filenames
        
        category_list = list(categories.values())
        
        return {
            "success": True,
            "manufacturer_id": manufacturer_id,
            "variant_id": variant_id,
            "categories": category_list,
            "category_count": len(category_list),
            "total_articles": sum(cat["article_count"] for cat in category_list),
            "search_prefix": article_prefix
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Category loading failed: {str(e)}",
            "categories": []
        }

def calculate_part_relevance(component_name: str, part_name: str, part_data: Dict) -> float:
    """
    Calculate relevance score between a damaged component and a catalog part.
    
    Args:
        component_name: Name of the damaged component
        part_name: Name of the catalog part
        part_data: Full part data dictionary
        
    Returns:
        Relevance score from 0.0 to 1.0
    """
    component_clean = component_name.upper().strip()
    part_clean = part_name.upper().strip()
    
    # Exact match gets highest score
    if component_clean == part_clean:
        return 1.0
    
    # Check if component is contained in part name or vice versa
    if component_clean in part_clean:
        return 0.9
    elif part_clean in component_clean:
        return 0.85
    
    # Word-by-word matching
    component_words = set(component_clean.split())
    part_words = set(part_clean.split())
    
    # Remove common automotive words for better matching
    common_words = {'FRONT', 'REAR', 'LEFT', 'RIGHT', 'DRIVER', 'PASSENGER', 'SIDE', 'ASSEMBLY'}
    component_words_filtered = component_words - common_words
    part_words_filtered = part_words - common_words
    
    if component_words_filtered and part_words_filtered:
        word_overlap = len(component_words_filtered.intersection(part_words_filtered))
        word_score = word_overlap / max(len(component_words_filtered), len(part_words_filtered))
        
        if word_score > 0.7:
            return 0.8 + (word_score - 0.7) * 0.5  # 0.8 to 0.95 range
        elif word_score > 0.4:
            return 0.6 + (word_score - 0.4) * 0.67  # 0.6 to 0.8 range
    
    # Fuzzy string matching as fallback
    fuzzy_score = SequenceMatcher(None, component_clean, part_clean).ratio()
    
    # Keyword matching in part details (if available)
    detail_bonus = 0.0
    tech_details = part_data.get('techDetails', '')
    if tech_details and isinstance(tech_details, str):
        if any(word in tech_details.upper() for word in component_words_filtered):
            detail_bonus = 0.1
    
    return min(fuzzy_score + detail_bonus, 1.0)

def deduplicate_parts(parts_list: List[Dict]) -> List[Dict]:
    """
    Remove duplicate parts based on various identifiers.
    
    Args:
        parts_list: List of part dictionaries
        
    Returns:
        Deduplicated list preserving highest-scoring parts
    """
    if not parts_list:
        return []
    
    # Group parts by different identifiers
    seen_parts = {}
    
    for part in parts_list:
        # Try different deduplication keys in order of preference
        dedup_keys = [
            ('partNo', part.get('partNo', '')),
            ('id', part.get('id', '')),
            ('name', part.get('name', ''))
        ]
        
        dedup_key = None
        for key_name, key_value in dedup_keys:
            if key_value and str(key_value).strip():
                dedup_key = f"{key_name}:{key_value}"
                break
        
        if not dedup_key:
            # Use combination as fallback
            name = part.get('name', 'unknown')
            manufacturer = part.get('manufacturer', 'unknown')
            dedup_key = f"fallback:{name}:{manufacturer}"
        
        # Keep the part with highest relevance score
        current_score = part.get('relevance_score', 0.0)
        
        if dedup_key not in seen_parts or current_score > seen_parts[dedup_key].get('relevance_score', 0.0):
            seen_parts[dedup_key] = part
    
    # Return deduplicated parts sorted by relevance score
    deduplicated = list(seen_parts.values())
    deduplicated.sort(key=lambda x: x.get('relevance_score', 0.0), reverse=True)
    
    return deduplicated

@tool
def search_parts_for_damage(variant_ids_json: str, damaged_components_json: str) -> Dict:
    """
    Search catalog for parts matching damaged components across multiple variants.
    
    Args:
        variant_ids_json: JSON string containing list of compatible variant IDs
        damaged_components_json: JSON string containing list of damaged component names
        
    Returns:
        Dict with matching parts, relevance scores, and search metadata
    """
    try:
        bm = get_bucket_manager()
        
        # Parse inputs
        variant_ids = json.loads(variant_ids_json)
        damaged_components = json.loads(damaged_components_json)
        
        if not isinstance(variant_ids, list) or not isinstance(damaged_components, list):
            return {
                "success": False,
                "error": "Expected lists for variant_ids and damaged_components",
                "parts": []
            }
        
        if not variant_ids or not damaged_components:
            return {
                "success": False,
                "error": "Empty variant_ids or damaged_components provided",
                "parts": []
            }
        
        # Step 1: Map components to categories
        component_mapping = map_components_to_categories.func(damaged_components_json)
        if not component_mapping.get("success"):
            return {
                "success": False,
                "error": f"Component mapping failed: {component_mapping.get('error')}",
                "parts": []
            }
        
        target_categories = component_mapping.get("all_categories", [])
        
        # Step 2: Search across all variant/category combinations
        all_parts = []
        search_stats = {
            "variants_searched": 0,
            "categories_searched": 0,
            "articles_loaded": 0,
            "parts_found": 0,
            "errors": []
        }
        
        for variant_id in variant_ids:
            search_stats["variants_searched"] += 1
            
            for category_id in target_categories:
                search_stats["categories_searched"] += 1
                
                try:
                    # Load articles for this variant/category combination
                    articles = bm.get_articles_for_category("104", variant_id, category_id)  # Using manufacturer 104 for now
                    
                    if articles:
                        search_stats["articles_loaded"] += 1
                        
                        # Process each part in the articles
                        for part in articles:
                            part_name = part.get('name', '')
                            
                            # Calculate relevance for each damaged component
                            best_relevance = 0.0
                            best_component = ""
                            
                            for component in damaged_components:
                                component_str = str(component)
                                relevance = calculate_part_relevance(component_str, part_name, part)
                                
                                if relevance > best_relevance:
                                    best_relevance = relevance
                                    best_component = component_str
                            
                            # Only include parts above minimum threshold
                            if best_relevance >= 0.4:  # Lower threshold for more coverage
                                enhanced_part = {
                                    **part,
                                    "relevance_score": best_relevance,
                                    "matched_component": best_component,
                                    "variant_id": variant_id,
                                    "category_id": category_id,
                                    "search_source": f"variant_{variant_id}_category_{category_id}"
                                }
                                all_parts.append(enhanced_part)
                                search_stats["parts_found"] += 1
                                
                except Exception as e:
                    error_msg = f"Error loading variant {variant_id}, category {category_id}: {str(e)}"
                    search_stats["errors"].append(error_msg)
        
        # Step 3: Deduplicate parts
        deduplicated_parts = deduplicate_parts(all_parts)
        
        # Step 4: Analyze results
        score_distribution = {
            "high_relevance": len([p for p in deduplicated_parts if p.get('relevance_score', 0) >= 0.8]),
            "medium_relevance": len([p for p in deduplicated_parts if 0.5 <= p.get('relevance_score', 0) < 0.8]),
            "low_relevance": len([p for p in deduplicated_parts if 0.4 <= p.get('relevance_score', 0) < 0.5])
        }
        
        # Step 5: Group parts by component
        parts_by_component = {}
        for component in damaged_components:
            component_str = str(component)
            matching_parts = [p for p in deduplicated_parts if p.get('matched_component') == component_str]
            parts_by_component[component_str] = matching_parts
        
        return {
            "success": True,
            "parts": deduplicated_parts[:50],  # Limit to top 50 parts
            "total_parts_found": len(deduplicated_parts),
            "parts_by_component": parts_by_component,
            "score_distribution": score_distribution,
            "search_stats": search_stats,
            "deduplication_stats": {
                "before_dedup": len(all_parts),
                "after_dedup": len(deduplicated_parts),
                "duplicates_removed": len(all_parts) - len(deduplicated_parts)
            },
            "component_mapping": component_mapping
        }
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Invalid JSON input: {str(e)}",
            "parts": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Parts search failed: {str(e)}",
            "parts": []
        }

# Export tools for LangChain agent use
catalog_tools = [
    map_components_to_categories,
    load_categories_for_variant,
    search_parts_for_damage
]
