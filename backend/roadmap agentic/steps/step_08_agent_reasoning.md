# Step 8: Enhanced Reasoning

## 🎯 **OBJECTIVE**
Add advanced reasoning for damage propagation and parts validation.

## ⏱️ **ESTIMATED TIME**: 25 minutes

## 📋 **PREREQUISITES**
- ✅ Step 7: Agent foundation working
- ✅ Basic agent processing functional
- ✅ All tools operational

## 🏗️ **IMPLEMENTATION TASKS**

### **Task 1: Create Damage Propagation Tool**
Create `/backend/agents/tools/reasoning_tools.py` with:
- `analyze_damage_propagation(primary_damage_json, vehicle_type)` function
- Maps primary damage to secondary/consumable parts
- Uses automotive damage propagation rules
- Returns categorized parts (primary/secondary/consumable)

### **Task 2: Add Parts Validation Tool**
Add `validate_parts_compatibility(parts_json, vehicle_info_json)` that:
- Checks parts compatibility with specific vehicle
- Validates year ranges and model fits
- Assigns compatibility scores to each part
- Filters out incompatible parts

### **Task 3: Enhance Agent Prompt**
Update agent prompt template to include:
- Damage propagation analysis instructions
- Parts validation requirements
- Comprehensive output format with categories
- Quality control verification steps

### **Task 4: Update Tools Integration**
Add reasoning tools to the agent's toolkit and update exports.

### **Task 5: Create Reasoning Test**
Create `/backend/test_enhanced_reasoning.py` that tests:
- Damage propagation for front-end collision
- Parts validation with compatibility scoring
- Enhanced agent processing with categorized results
- Complex damage scenarios

## ✅ **SUCCESS CRITERIA**
- ✅ Identifies secondary damage from primary damage
- ✅ Validates parts compatibility with vehicle specs
- ✅ Categorizes parts (primary/secondary/consumable)
- ✅ Enhanced agent finds more comprehensive parts lists
- ✅ Higher confidence scores for validated results

## 🧪 **VERIFICATION COMMAND**
```bash
python test_enhanced_reasoning.py
```

**Expected Output:**
```
🧪 Testing Enhanced Reasoning...
✅ Damage propagation: 6 secondary + 8 consumable parts identified
✅ Parts validation: 12/15 parts compatible with 2018 Astra
✅ Enhanced processing: 18 total parts (8 primary, 6 secondary, 4 consumable)
✅ Confidence score: 0.82 (improved from 0.65)
🎉 Enhanced reasoning test complete - Ready for Step 9!
```

## ❌ **COMMON ISSUES**
- **"No secondary parts found"**: Expand propagation rules
- **"Low compatibility scores"**: Check year range validation logic
- **"Agent doesn't use reasoning tools"**: Verify tools imported and prompt updated

---
**Next Step**: Step 9 - Performance Optimization

### **1. Add Damage Propagation Tool**
Create a tool to identify secondary damage and related parts:

```python
# File: /backend/agents/tools/reasoning_tools.py (NEW FILE)
import json
from typing import Dict, List
from langchain.tools import tool

@tool
def analyze_damage_propagation(primary_damage_json: str, vehicle_type: str = "sedan") -> Dict:
    """
    Analyze damage propagation to identify secondary and consumable parts that may need replacement.
    
    Args:
        primary_damage_json: JSON array of primary damaged components
        vehicle_type: Type of vehicle (sedan, hatchback, suv, etc.)
    
    Returns:
        Dict with secondary parts, consumables, and reasoning
    """
    try:
        primary_damage = json.loads(primary_damage_json)
        
        if not isinstance(primary_damage, list):
            return {"error": "Invalid primary damage format", "secondary_parts": [], "consumables": []}
        
        # Damage propagation rules
        propagation_rules = {
            # Front-end collisions
            "Front Bumper Cover": {
                "secondary": ["Front Grille", "License Plate Bracket", "Fog Light Housing", "Bumper Reinforcement"],
                "consumables": ["Clips", "Fasteners", "Mounting Hardware"]
            },
            "Headlight Assembly": {
                "secondary": ["Headlight Bracket", "Wiring Harness"],
                "consumables": ["Bulbs", "Seals", "Mounting Screws"]
            },
            "Hood": {
                "secondary": ["Hood Hinges", "Hood Support Struts", "Hood Latch"],
                "consumables": ["Hood Insulation", "Weather Stripping"]
            },
            "Front Fender": {
                "secondary": ["Fender Liner", "Side Marker Light", "Antenna"],
                "consumables": ["Fender Clips", "Mounting Bolts"]
            },
            
            # Side impacts
            "Door Panel": {
                "secondary": ["Door Handle", "Window Regulator", "Door Mirror", "Door Seal"],
                "consumables": ["Door Clips", "Interior Trim", "Weather Stripping"]
            },
            "Side Mirror": {
                "secondary": ["Mirror Housing", "Mirror Glass", "Turn Signal"],
                "consumables": ["Mirror Adjustment Motor", "Wiring"]
            },
            
            # Rear-end collisions
            "Rear Bumper Cover": {
                "secondary": ["Rear Grille", "License Plate Light", "Backup Sensor"],
                "consumables": ["Bumper Clips", "Mounting Hardware"]
            },
            "Taillight Assembly": {
                "secondary": ["Taillight Housing", "Wiring Harness"],
                "consumables": ["Bulbs", "Seals", "Gaskets"]
            },
            "Trunk Lid": {
                "secondary": ["Trunk Hinges", "Trunk Struts", "Trunk Lock"],
                "consumables": ["Trunk Seal", "Interior Lining"]
            }
        }
        
        # Analyze each damaged component
        all_secondary = []
        all_consumables = []
        reasoning_steps = []
        
        for component in primary_damage:
            component_name = component.get("component", str(component)) if isinstance(component, dict) else str(component)
            
            # Find matching propagation rule (fuzzy matching)
            matching_rule = None
            for rule_key in propagation_rules:
                if rule_key.lower() in component_name.lower() or component_name.lower() in rule_key.lower():
                    matching_rule = propagation_rules[rule_key]
                    break
            
            if matching_rule:
                reasoning_steps.append(f"Found propagation rule for {component_name}")
                all_secondary.extend(matching_rule["secondary"])
                all_consumables.extend(matching_rule["consumables"])
            else:
                reasoning_steps.append(f"No specific propagation rule for {component_name}, applying general rules")
                # General consumables for any damage
                all_consumables.extend(["Paint", "Primer", "Clear Coat"])
        
        # Remove duplicates while preserving order
        unique_secondary = list(dict.fromkeys(all_secondary))
        unique_consumables = list(dict.fromkeys(all_consumables))
        
        return {
            "success": True,
            "secondary_parts": unique_secondary,
            "consumables": unique_consumables,
            "reasoning_steps": reasoning_steps,
            "propagation_confidence": 0.8 if unique_secondary else 0.5,
            "total_additional_parts": len(unique_secondary) + len(unique_consumables)
        }
        
    except Exception as e:
        return {
            "error": f"Damage propagation analysis failed: {str(e)}",
            "secondary_parts": [],
            "consumables": [],
            "reasoning_steps": [f"Error: {str(e)}"]
        }

@tool
def validate_parts_compatibility(parts_json: str, vehicle_info_json: str) -> Dict:
    """
    Validate that found parts are compatible with the specific vehicle.
    
    Args:
        parts_json: JSON array of found parts
        vehicle_info_json: JSON object with vehicle details
    
    Returns:
        Dict with validation results and compatibility scores
    """
    try:
        parts = json.loads(parts_json)
        vehicle_info = json.loads(vehicle_info_json)
        
        if not isinstance(parts, list) or not isinstance(vehicle_info, dict):
            return {"error": "Invalid input format", "validated_parts": []}
        
        vehicle_year = vehicle_info.get("year")
        vehicle_model = vehicle_info.get("model", "").lower()
        
        validated_parts = []
        validation_notes = []
        
        for part in parts:
            if not isinstance(part, dict):
                continue
            
            validation_score = 1.0  # Start with perfect score
            compatibility_issues = []
            
            # Check year compatibility
            if vehicle_year:
                year_range = part.get("year_range", "")
                if year_range and "-" in year_range:
                    try:
                        start_year, end_year = map(int, year_range.split("-"))
                        if not (start_year <= vehicle_year <= end_year):
                            validation_score *= 0.5
                            compatibility_issues.append(f"Year mismatch: part fits {year_range}, vehicle is {vehicle_year}")
                    except:
                        pass
            
            # Check model compatibility
            fits_vehicles = part.get("fits_vehicles", [])
            if fits_vehicles and vehicle_model:
                model_match = any(vehicle_model in str(vehicle).lower() for vehicle in fits_vehicles)
                if not model_match:
                    validation_score *= 0.7
                    compatibility_issues.append("Model compatibility unclear")
            
            # Check part completeness
            required_fields = ["part_name", "manufacturer_part_number"]
            missing_fields = [field for field in required_fields if not part.get(field)]
            if missing_fields:
                validation_score *= 0.8
                compatibility_issues.append(f"Missing fields: {missing_fields}")
            
            # Add validation metadata
            validated_part = part.copy()
            validated_part.update({
                "validation_score": validation_score,
                "compatibility_issues": compatibility_issues,
                "validation_status": "compatible" if validation_score >= 0.8 else "questionable" if validation_score >= 0.5 else "incompatible"
            })
            
            validated_parts.append(validated_part)
            
            if compatibility_issues:
                validation_notes.append(f"Part {part.get('part_name', 'Unknown')}: {', '.join(compatibility_issues)}")
        
        # Filter out incompatible parts
        compatible_parts = [p for p in validated_parts if p["validation_score"] >= 0.5]
        
        return {
            "success": True,
            "validated_parts": compatible_parts,
            "total_parts_validated": len(parts),
            "compatible_parts_count": len(compatible_parts),
            "average_compatibility": sum(p["validation_score"] for p in validated_parts) / len(validated_parts) if validated_parts else 0,
            "validation_notes": validation_notes
        }
        
    except Exception as e:
        return {
            "error": f"Parts validation failed: {str(e)}",
            "validated_parts": []
        }

# Export tools
reasoning_tools = [analyze_damage_propagation, validate_parts_compatibility]
```

### **2. Update Enhanced Agent Prompt**
Create a more sophisticated prompt for better reasoning:

```python
# File: /backend/agents/parts_agent.py (UPDATE _create_agent_prompt method)
def _create_agent_prompt(self) -> PromptTemplate:
    """Create the enhanced agent prompt template with sophisticated reasoning"""
    
    template = """You are an expert automotive parts specialist AI agent with deep knowledge of vehicle damage patterns and OEM parts catalogs. Your mission is to provide comprehensive, accurate parts lists for insurance claims and repair workflows.

AVAILABLE TOOLS:
{tools}

ADVANCED REASONING METHODOLOGY:

1. VEHICLE IDENTIFICATION & VALIDATION
   - Extract vehicle make, model, year from the damage report
   - Map manufacturer to catalog ID using identify_vehicle_from_report
   - Validate vehicle exists in catalog using validate_vehicle_in_catalog

2. VARIANT DISCOVERY & COMPATIBILITY
   - Find all compatible vehicle variants using find_matching_variants
   - Consider trim levels, engine types, and regional variations
   - Prioritize exact matches but include close alternatives

3. PRIMARY PARTS DISCOVERY
   - Map damaged components to catalog categories using map_components_to_categories
   - Search for exact parts matches using search_parts_for_damage
   - Analyze relevance scores and prioritize high-confidence matches

4. DAMAGE PROPAGATION ANALYSIS
   - Use analyze_damage_propagation to identify secondary damage
   - Consider parts that may be damaged but not immediately visible
   - Include consumables like clips, fasteners, and finishing materials

5. PARTS VALIDATION & QUALITY CONTROL
   - Validate all parts using validate_parts_compatibility
   - Check year compatibility, model fit, and part completeness
   - Remove or flag questionable parts with low compatibility scores

6. INTELLIGENT RESULT COMPILATION
   - Organize parts by category: Primary, Secondary, Consumables
   - Provide complete part information: OEM numbers, EANs, descriptions
   - Include confidence levels and reasoning for each part

CRITICAL SUCCESS FACTORS:
- Always start with vehicle identification - this is the foundation
- Be thorough in damage propagation - insurance companies expect comprehensive lists
- Validate every part for compatibility - accuracy is paramount
- Provide clear reasoning for each step you take
- If any step fails, explain why and provide alternative approaches

INPUT FORMAT:
- vehicle_info: JSON with make, model, year, trim, etc.
- damaged_parts: JSON array of damaged component objects with severity levels

OUTPUT FORMAT:
Return a comprehensive JSON with:
{{
  "parts_list": [
    {{
      "category": "primary|secondary|consumable",
      "part_name": "Official part name",
      "manufacturer_part_number": "OEM part number",
      "ean_number": "EAN/UPC if available",
      "oem_numbers": ["Alternative OEM numbers"],
      "matched_component": "Which damage this addresses",
      "relevance_score": 0.95,
      "validation_score": 0.88,
      "compatibility_status": "compatible",
      "confidence_level": "high|medium|low"
    }}
  ],
  "reasoning_steps": ["Step-by-step reasoning process"],
  "confidence_score": 0.85,
  "total_parts_found": 15,
  "coverage_analysis": {{
    "primary_coverage": "Complete coverage of all primary damage",
    "secondary_coverage": "Identified 3 potential secondary issues",
    "consumables_included": true
  }}
}}

DAMAGE CONTEXT:
Vehicle Information: {vehicle_info}
Damaged Components: {damaged_parts}

Think step by step and use all available tools to build a comprehensive parts list. Start with vehicle identification, then proceed methodically through each step.

{agent_scratchpad}"""

    return PromptTemplate(
        input_variables=["tools", "tool_names", "vehicle_info", "damaged_parts", "agent_scratchpad"],
        template=template
    )
```

### **3. Update Tools Import**
Add the new reasoning tools to the agent:

```python
# File: /backend/agents/tools/__init__.py (UPDATE)
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
from .reasoning_tools import (
    reasoning_tools,
    analyze_damage_propagation,
    validate_parts_compatibility
)

# Combine all tools
all_agent_tools = vehicle_identification_tools + catalog_search_tools + reasoning_tools

__all__ = [
    'all_agent_tools',
    'vehicle_identification_tools',
    'catalog_search_tools',
    'reasoning_tools',
    'identify_vehicle_from_report', 
    'validate_vehicle_in_catalog',
    'find_matching_variants',
    'map_components_to_categories',
    'load_categories_for_variant',
    'search_parts_for_damage',
    'analyze_damage_propagation',
    'validate_parts_compatibility'
]
```

### **4. Create Advanced Reasoning Test**
Test the enhanced reasoning capabilities:

```python
# File: /backend/test_agent_reasoning.py
import json
from agents.parts_agent import parts_agent

def test_damage_propagation():
    """Test damage propagation analysis"""
    
    print("🧪 Testing Damage Propagation Analysis...")
    
    # Test front-end collision scenario
    primary_damage = [
        {"component": "Front Bumper Cover", "severity": "severe"},
        {"component": "Headlight Assembly", "severity": "moderate"}
    ]
    
    # Import the tool directly to test
    from agents.tools.reasoning_tools import analyze_damage_propagation
    
    result = analyze_damage_propagation(json.dumps(primary_damage))
    
    if result.get("success"):
        secondary = result.get("secondary_parts", [])
        consumables = result.get("consumables", [])
        reasoning = result.get("reasoning_steps", [])
        
        print(f"✅ Propagation analysis successful")
        print(f"   Secondary parts: {len(secondary)} ({secondary[:3]}...)")
        print(f"   Consumables: {len(consumables)} ({consumables[:3]}...)")
        print(f"   Reasoning steps: {len(reasoning)}")
        
        return len(secondary) >= 3 and len(consumables) >= 3
    else:
        print(f"❌ Propagation analysis failed: {result.get('error')}")
        return False

def test_enhanced_agent_processing():
    """Test the enhanced agent with sophisticated reasoning"""
    
    print("\n🧪 Testing Enhanced Agent Processing...")
    
    # Complex damage scenario
    vehicle_info = {
        "make": "Vauxhall",
        "model": "Astra",
        "year": 2018,
        "trim": "SRi"
    }
    
    damaged_parts = [
        {"component": "Front Bumper Cover", "severity": "severe", "notes": "Cracked and deformed"},
        {"component": "Headlight Assembly", "severity": "moderate", "notes": "Left headlight damaged"},
        {"component": "Hood", "severity": "minor", "notes": "Small dent and scratches"}
    ]
    
    print(f"🔍 Complex scenario: {vehicle_info['make']} {vehicle_info['model']} with {len(damaged_parts)} damaged components")
    
    try:
        result = parts_agent.process_damage_report(vehicle_info, damaged_parts)
        
        if result.get("success"):
            parts_list = result.get("parts_list", [])
            reasoning = result.get("reasoning_steps", [])
            confidence = result.get("confidence_score", 0.0)
            coverage = result.get("coverage_analysis", {})
            
            print(f"✅ Enhanced processing successful")
            print(f"   Total parts found: {len(parts_list)}")
            print(f"   Confidence score: {confidence:.2f}")
            print(f"   Reasoning steps: {len(reasoning)}")
            
            # Analyze part categories
            categories = {}
            high_confidence_parts = 0
            
            for part in parts_list:
                category = part.get("category", "unknown")
                confidence_level = part.get("confidence_level", "low")
                
                categories[category] = categories.get(category, 0) + 1
                if confidence_level == "high":
                    high_confidence_parts += 1
            
            print(f"   Part categories: {dict(categories)}")
            print(f"   High-confidence parts: {high_confidence_parts}")
            
            # Show sample parts
            print("   Sample parts:")
            for part in parts_list[:3]:
                print(f"     - {part.get('part_name')} (Category: {part.get('category')}, Confidence: {part.get('confidence_level')})")
            
            # Success criteria for enhanced processing
            return (
                len(parts_list) >= 8 and  # Should find more parts with propagation
                confidence >= 0.7 and    # Higher confidence expected
                "primary" in categories and  # Should categorize parts
                high_confidence_parts >= 3   # Should have confident matches
            )
            
        else:
            print(f"❌ Enhanced processing failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Enhanced processing error: {str(e)}")
        return False

def test_parts_validation():
    """Test parts validation functionality"""
    
    print("\n🧪 Testing Parts Validation...")
    
    # Mock parts data for validation
    test_parts = [
        {
            "part_name": "Front Bumper Cover",
            "manufacturer_part_number": "VXH025001",
            "year_range": "2015-2020",
            "fits_vehicles": ["Astra", "Insignia"]
        },
        {
            "part_name": "Headlight Assembly", 
            "manufacturer_part_number": "VXH098001",
            "year_range": "2010-2018",
            "fits_vehicles": ["Corsa", "Adam"]  # Incompatible model
        }
    ]
    
    vehicle_info = {"make": "Vauxhall", "model": "Astra", "year": 2018}
    
    from agents.tools.reasoning_tools import validate_parts_compatibility
    
    result = validate_parts_compatibility(json.dumps(test_parts), json.dumps(vehicle_info))
    
    if result.get("success"):
        validated = result.get("validated_parts", [])
        compatible_count = result.get("compatible_parts_count", 0)
        avg_compatibility = result.get("average_compatibility", 0.0)
        
        print(f"✅ Parts validation successful")
        print(f"   Validated parts: {len(validated)}")
        print(f"   Compatible parts: {compatible_count}")
        print(f"   Average compatibility: {avg_compatibility:.2f}")
        
        # Check validation scores
        for part in validated:
            score = part.get("validation_score", 0.0)
            status = part.get("validation_status", "unknown")
            print(f"     {part.get('part_name')}: {score:.2f} ({status})")
        
        return compatible_count >= 1 and avg_compatibility >= 0.5
    else:
        print(f"❌ Parts validation failed: {result.get('error')}")
        return False

if __name__ == "__main__":
    try:
        print("🧪 Testing Enhanced Agent Reasoning...")
        
        propagation_success = test_damage_propagation()
        validation_success = test_parts_validation()
        processing_success = test_enhanced_agent_processing()
        
        if propagation_success and validation_success and processing_success:
            print("\n🎉 Enhanced agent reasoning test complete - Ready for Step 9!")
        else:
            print(f"\n⚠️ Tests failed - Propagation: {propagation_success}, Validation: {validation_success}, Processing: {processing_success}")
    except Exception as e:
        print(f"\n❌ Agent reasoning test error: {str(e)}")
```

## ✅ **SUCCESS CRITERIA**

After completing this step, you should have:

1. **✅ Damage propagation working** - Identifies secondary and consumable parts
2. **✅ Parts validation implemented** - Checks compatibility and completeness
3. **✅ Enhanced reasoning prompt** - More sophisticated agent instructions
4. **✅ Advanced result structuring** - Categorized parts with metadata
5. **✅ Comprehensive testing** - All reasoning functions verified
6. **✅ Higher part discovery** - Should find 8+ parts for complex scenarios

## 🧪 **VERIFICATION COMMAND**

```bash
python test_agent_reasoning.py
```

**Expected Output:**
```
🧪 Testing Enhanced Agent Reasoning...

🧪 Testing Damage Propagation Analysis...
✅ Propagation analysis successful
   Secondary parts: 6 (['Front Grille', 'License Plate Bracket', 'Fog Light Housing']...)
   Consumables: 8 (['Clips', 'Fasteners', 'Mounting Hardware']...)
   Reasoning steps: 4

🧪 Testing Parts Validation...
✅ Parts validation successful
   Validated parts: 2
   Compatible parts: 1
   Average compatibility: 0.75
     Front Bumper Cover: 1.00 (compatible)
     Headlight Assembly: 0.50 (questionable)

🧪 Testing Enhanced Agent Processing...
🔍 Complex scenario: Vauxhall Astra with 3 damaged components
✅ Enhanced processing successful
   Total parts found: 12
   Confidence score: 0.82
   Reasoning steps: 18
   Part categories: {'primary': 8, 'secondary': 3, 'consumable': 1}
   High-confidence parts: 6
   Sample parts:
     - Front Bumper Cover Assembly (Category: primary, Confidence: high)
     - Headlight Unit - Left (Category: primary, Confidence: high)
     - Front Grille Assembly (Category: secondary, Confidence: medium)

🎉 Enhanced agent reasoning test complete - Ready for Step 9!
```

## ❌ **COMMON ISSUES & SOLUTIONS**

### **Issue 1: Damage propagation finds too few secondary parts**
**Solution**: Review and expand the propagation rules in `reasoning_tools.py`.

### **Issue 2: Parts validation marks compatible parts as incompatible**
**Solution**: Check year range parsing and model matching logic.

### **Issue 3: Agent doesn't use reasoning tools**
**Solution**: Ensure tools are properly imported and agent prompt encourages their use.

## 🎯 **STEP COMPLETION**

**Only proceed to Step 9 if:**
- ✅ Damage propagation finds 6+ secondary parts
- ✅ Parts validation correctly scores compatibility
- ✅ Enhanced agent finds 12+ parts for complex scenarios
- ✅ Parts are properly categorized (primary/secondary/consumable)

---

**Next Step**: Step 9 - Performance Optimization
