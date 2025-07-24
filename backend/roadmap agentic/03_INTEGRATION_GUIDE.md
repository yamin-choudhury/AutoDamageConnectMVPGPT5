# 🔧 Integration Guide: Step-by-Step Implementation

## 📋 **Prerequisites**

### **Install Required Dependencies**
```bash
cd /Users/yaminchoudhury/Documents/AutoDamageConnect/DamageReportMVP/backend

# Add to requirements.txt
echo "langchain>=0.1.0" >> requirements.txt
echo "langchain-openai>=0.1.0" >> requirements.txt  
echo "langchain-core>=0.1.0" >> requirements.txt
echo "langgraph>=0.1.0" >> requirements.txt
echo "google-cloud-storage>=2.10.0" >> requirements.txt

# Install dependencies
pip install -r requirements.txt
```

### **Environment Variables**
Add to your existing environment setup:
```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=rising-theater-466617-n8
PARTS_CATALOG_BUCKET=car-parts-catalogue-yc

# Agent Configuration  
AGENT_MODEL=gpt-4o
AGENT_TEMPERATURE=0.2
ENABLE_AGENT_CACHING=true
```

## 🏗️ **File Structure**

Create the following directory structure:
```
backend/
├── agents/
│   ├── __init__.py
│   ├── parts_agent.py          # Main agent implementation
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── vehicle_tools.py    # Vehicle identification tools
│   │   ├── catalog_tools.py    # Parts catalog tools
│   │   └── validation_tools.py # Parts validation tools
│   └── utils/
│       ├── __init__.py
│       ├── bucket_manager.py   # Google Cloud Storage interface
│       └── cache_manager.py    # Caching utilities
├── generate_damage_report_staged.py  # Your existing file (to modify)
└── main.py                     # Your existing file (to modify)
```

## 🛠️ **Implementation Steps**

### **Step 1: Create Bucket Manager (Day 1)**

Create `agents/utils/bucket_manager.py`:
```python
#!/usr/bin/env python3
"""Google Cloud Storage manager for parts catalog access."""

import json, os
from pathlib import Path
from google.cloud import storage
from typing import Optional, Dict, List, Any

class PartsCatalogBucket:
    """Manager for accessing parts catalog in Google Cloud Storage."""
    
    def __init__(self, bucket_name: str = None):
        self.bucket_name = bucket_name or os.getenv("PARTS_CATALOG_BUCKET", "car-parts-catalogue-yc")
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "rising-theater-466617-n8")
        self.client = storage.Client(project=self.project_id)
        self.bucket = self.client.bucket(self.bucket_name)
        self.cache = {}  # Simple in-memory cache
        
        # Manufacturer name to ID mapping
        self.manufacturer_map = {
            "VAUXHALL": "117",
            "BMW": "16", 
            "MERCEDES-BENZ": "74",
            "FORD": "58",
            "AUDI": "19",
            # Add all 35 manufacturers from your catalog
        }
    
    def get_manufacturer_id(self, make_name: str) -> Optional[str]:
        """Convert manufacturer name to catalog ID."""
        return self.manufacturer_map.get(make_name.upper())
    
    def load_json_file(self, file_path: str) -> Optional[Dict]:
        """Load JSON file from bucket with caching."""
        cache_key = f"json:{file_path}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            blob = self.bucket.blob(file_path)
            if not blob.exists():
                return None
                
            content = json.loads(blob.download_as_text())
            self.cache[cache_key] = content
            return content
            
        except Exception as e:
            print(f"Error loading {file_path}: {str(e)}")
            return None
    
    def get_models_for_manufacturer(self, manufacturer_id: str) -> List[Dict]:
        """Get all models for a manufacturer."""
        file_path = f"manufacturers/{manufacturer_id}/models_{manufacturer_id}.json"
        return self.load_json_file(file_path) or []
    
    def get_variants_for_model(self, manufacturer_id: str, model_id: str) -> List[Dict]:
        """Get all variants for a specific model."""
        file_path = f"manufacturers/{manufacturer_id}/variants_{model_id}.json"
        return self.load_json_file(file_path) or []
    
    def get_categories_for_variant(self, manufacturer_id: str, variant_id: str) -> List[Dict]:
        """Get categories available for a variant."""
        file_path = f"manufacturers/{manufacturer_id}/categories_{variant_id}.json"
        return self.load_json_file(file_path) or []
    
    def get_articles_for_category(self, manufacturer_id: str, variant_id: str, 
                                 category_id: str, product_group_id: str = None) -> List[Dict]:
        """Get articles/parts for a specific category."""
        # List all article files for this variant and category
        prefix = f"manufacturers/{manufacturer_id}/articles_{variant_id}_{category_id}"
        
        if product_group_id:
            prefix += f"_{product_group_id}"
        
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            all_articles = []
            
            for blob in blobs:
                if blob.name.endswith('.json'):
                    articles = self.load_json_file(blob.name)
                    if articles:
                        all_articles.extend(articles)
            
            return all_articles
            
        except Exception as e:
            print(f"Error getting articles: {str(e)}")
            return []
```

### **Step 2: Create Agent Tools (Day 1-2)**

Create `agents/tools/vehicle_tools.py`:
```python
#!/usr/bin/env python3
"""Vehicle identification and matching tools."""

from langchain_core.tools import tool
from typing import Dict, List, Optional
from ..utils.bucket_manager import PartsCatalogBucket

bucket_manager = PartsCatalogBucket()

@tool
def identify_vehicle_from_report(damage_report_json: str, vehicle_info_json: str) -> Dict:
    """
    Extract and refine vehicle identification from damage report.
    
    Args:
        damage_report_json: JSON string containing damage detection results
        vehicle_info_json: JSON string containing initial vehicle identification
    
    Returns:
        Dict with refined vehicle information including confidence scores
    """
    import json
    
    try:
        damage_data = json.loads(damage_report_json)
        vehicle_data = json.loads(vehicle_info_json)
        
        # Extract vehicle info with confidence scoring
        make = vehicle_data.get("make", "").upper().strip()
        model = vehicle_data.get("model", "").strip()
        year = vehicle_data.get("year")
        engine = vehicle_data.get("engine", "").strip()
        
        # Validate against known manufacturers
        manufacturer_id = bucket_manager.get_manufacturer_id(make)
        confidence = 0.9 if manufacturer_id else 0.3
        
        return {
            "make": make,
            "model": model,
            "year": year,
            "engine": engine,
            "manufacturer_id": manufacturer_id,
            "confidence": confidence,
            "validated": manufacturer_id is not None
        }
        
    except Exception as e:
        return {
            "error": f"Vehicle identification failed: {str(e)}",
            "confidence": 0.0,
            "validated": False
        }

@tool  
def find_matching_variants(manufacturer_id: str, model_name: str, year: int = None) -> List[Dict]:
    """
    Find matching vehicle variants in the parts catalog.
    
    Args:
        manufacturer_id: Catalog manufacturer ID (e.g., "117")
        model_name: Vehicle model name (e.g., "Astra")
        year: Vehicle year for filtering variants
    
    Returns:
        List of matching variant objects with compatibility scores
    """
    try:
        # Get all models for manufacturer
        models = bucket_manager.get_models_for_manufacturer(manufacturer_id)
        
        # Find matching model
        matching_models = []
        for model in models:
            model_name_clean = model.get("name", "").strip()
            if model_name.lower() in model_name_clean.lower():
                matching_models.append(model)
        
        if not matching_models:
            return []
        
        # Get variants for matching models
        all_variants = []
        for model in matching_models:
            variants = bucket_manager.get_variants_for_model(manufacturer_id, model["id"])
            
            for variant in variants:
                # Calculate compatibility score
                score = 1.0
                variant_name = variant.get("name", "").lower()
                
                # Year matching
                if year:
                    if str(year) in variant_name:
                        score += 0.5
                    else:
                        score -= 0.2
                
                variant["compatibility_score"] = max(0.1, score)
                variant["model_info"] = model
                all_variants.append(variant)
        
        # Sort by compatibility score
        all_variants.sort(key=lambda x: x["compatibility_score"], reverse=True)
        
        return all_variants[:5]  # Return top 5 matches
        
    except Exception as e:
        return [{"error": f"Variant matching failed: {str(e)}"}]
```

Create `agents/tools/catalog_tools.py`:
```python
#!/usr/bin/env python3
"""Parts catalog search and retrieval tools."""

from langchain_core.tools import tool
from typing import Dict, List, Optional
from ..utils.bucket_manager import PartsCatalogBucket

bucket_manager = PartsCatalogBucket()

# Component to category mapping
COMPONENT_MAPPING = {
    "brake": {"category_ids": ["100006"], "keywords": ["brake", "pad", "disc", "booster"]},
    "bumper": {"category_ids": ["100020"], "keywords": ["bumper", "cover", "support"]},
    "headlight": {"category_ids": ["100021"], "keywords": ["headlight", "lamp", "bulb"]},
    "radiator": {"category_ids": ["100008"], "keywords": ["radiator", "cooling", "fan"]},
    "suspension": {"category_ids": ["100007"], "keywords": ["shock", "strut", "spring"]},
    # Add more mappings based on your catalog structure
}

@tool
def search_parts_for_damage(variant_ids_json: str, damaged_components_json: str) -> List[Dict]:
    """
    Search parts catalog for components matching the identified damage.
    
    Args:
        variant_ids_json: JSON list of compatible vehicle variant IDs
        damaged_components_json: JSON list of damaged component descriptions
    
    Returns:
        List of compatible parts with full catalog information
    """
    import json
    
    try:
        variant_ids = json.loads(variant_ids_json)
        damaged_components = json.loads(damaged_components_json)
        
        all_parts = []
        
        for variant_id in variant_ids[:3]:  # Limit to top 3 variants
            manufacturer_id = get_manufacturer_from_variant(variant_id)
            
            for component in damaged_components:
                component_name = component.get("name", "").lower()
                
                # Map component to catalog categories
                matching_categories = find_matching_categories(component_name)
                
                for category_id in matching_categories:
                    # Get parts for this category
                    parts = bucket_manager.get_articles_for_category(
                        manufacturer_id, variant_id, category_id
                    )
                    
                    # Filter and score parts
                    for part in parts:
                        if is_part_relevant(part, component_name):
                            part["match_score"] = calculate_match_score(part, component)
                            part["variant_id"] = variant_id
                            part["source_component"] = component
                            all_parts.append(part)
        
        # Remove duplicates and sort by relevance
        unique_parts = remove_duplicate_parts(all_parts)
        unique_parts.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        
        return unique_parts[:20]  # Return top 20 parts
        
    except Exception as e:
        return [{"error": f"Parts search failed: {str(e)}"}]

def find_matching_categories(component_name: str) -> List[str]:
    """Find catalog categories that match a component description."""
    matching_categories = []
    
    for component_type, mapping in COMPONENT_MAPPING.items():
        if any(keyword in component_name for keyword in mapping["keywords"]):
            matching_categories.extend(mapping["category_ids"])
    
    return matching_categories or ["100000"]  # Default category if no match

def is_part_relevant(part: Dict, component_name: str) -> bool:
    """Check if a part is relevant to the damaged component."""
    part_name = part.get("name", "").lower()
    part_desc = part.get("description", "").lower()
    
    # Simple keyword matching (can be enhanced with ML)
    keywords = component_name.split()
    return any(keyword in part_name or keyword in part_desc for keyword in keywords)

def calculate_match_score(part: Dict, component: Dict) -> float:
    """Calculate relevance score for a part-component match."""
    score = 0.5  # Base score
    
    part_name = part.get("name", "").lower()
    component_name = component.get("name", "").lower()
    
    # Exact keyword matches
    common_words = set(part_name.split()) & set(component_name.split())
    score += len(common_words) * 0.2
    
    # Part availability and OEM status
    if part.get("oem_only", False):
        score += 0.1
    
    return min(1.0, score)

def remove_duplicate_parts(parts_list: List[Dict]) -> List[Dict]:
    """Remove duplicate parts based on part number or ID."""
    seen = set()
    unique_parts = []
    
    for part in parts_list:
        part_id = part.get("id") or part.get("partNo")
        if part_id and part_id not in seen:
            seen.add(part_id)
            unique_parts.append(part)
    
    return unique_parts

def get_manufacturer_from_variant(variant_id: str) -> str:
    """Extract manufacturer ID from variant (you may need to enhance this)."""
    # This is a placeholder - you may need to implement based on your data structure
    return "117"  # Default to Vauxhall for now
```

### **Step 3: Create Main Agent (Day 2-3)**

Create `agents/parts_agent.py`:
```python
#!/usr/bin/env python3
"""Main parts discovery agent implementation."""

import json, os
from typing import Dict, List, Any
from langchain.agents import create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from .tools.vehicle_tools import identify_vehicle_from_report, find_matching_variants
from .tools.catalog_tools import search_parts_for_damage
from .utils.bucket_manager import PartsCatalogBucket

class PartsDiscoveryAgent:
    """Intelligent agent for discovering OEM parts from damage reports."""
    
    def __init__(self):
        self.model = os.getenv("AGENT_MODEL", "gpt-4o")
        self.temperature = float(os.getenv("AGENT_TEMPERATURE", "0.2"))
        self.bucket_manager = PartsCatalogBucket()
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            max_tokens=4096
        )
        
        # Define tools
        self.tools = [
            identify_vehicle_from_report,
            find_matching_variants,
            search_parts_for_damage
        ]
        
        # Create agent
        self.agent = self._create_agent()
    
    def _create_agent(self):
        """Create the ReAct agent with tools."""
        system_prompt = """
        You are AutoPartsExpert, an expert automotive parts specialist with access to a comprehensive UK auto parts catalog containing 35 major manufacturers and millions of OEM parts.

        Your mission: Transform damage reports into precise, procurement-ready parts lists using real catalog data.

        CRITICAL RULES:
        1. You must ONLY recommend parts that exist in the catalog
        2. Never guess or hallucinate parts
        3. Always explain your reasoning for transparency
        4. Include part numbers, EAN codes, and OEM numbers when available
        5. Suggest related parts and consumables when relevant

        PROCESS:
        1. IDENTIFY: Extract precise vehicle information from the damage report
        2. LOCATE: Find the vehicle in the parts catalog using manufacturer and variant IDs  
        3. MAP: Connect damaged components to catalog categories
        4. SEARCH: Query catalog for compatible OEM parts
        5. VALIDATE: Ensure parts fit the specific vehicle variant
        6. ENHANCE: Include related parts based on damage type
        7. FORMAT: Return structured JSON with complete procurement information

        If any step fails, provide alternatives and explain limitations.
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        return create_openai_tools_agent(self.llm, self.tools, prompt)
    
    def process_damage_report(self, vehicle_info: Dict, damaged_parts: List[Dict]) -> Dict:
        """
        Main entry point: process damage report and return parts list.
        
        Args:
            vehicle_info: Vehicle identification from phase 1
            damaged_parts: Damage analysis from phase 2
        
        Returns:
            Dict: Structured parts list with procurement information
        """
        try:
            # Prepare input for agent
            input_data = {
                "vehicle_info": json.dumps(vehicle_info),
                "damaged_parts": json.dumps(damaged_parts),
                "task": "Find exact OEM parts for the identified damage using the parts catalog"
            }
            
            # Execute agent
            result = self.agent.invoke(input_data)
            
            # Parse and validate result
            return self._parse_agent_result(result)
            
        except Exception as e:
            return self._handle_error(str(e), vehicle_info, damaged_parts)
    
    def _parse_agent_result(self, result: Dict) -> Dict:
        """Parse agent result into structured format."""
        try:
            # Extract the agent's output
            output = result.get("output", "")
            
            # Try to parse as JSON
            if output.startswith("{") and output.endswith("}"):
                return json.loads(output)
            
            # Fallback: create structured response
            return {
                "repair_parts": [],
                "agent_response": output,
                "processing_status": "partial_success",
                "message": "Agent provided text response instead of structured JSON"
            }
            
        except Exception as e:
            return {
                "repair_parts": [],
                "error": f"Result parsing failed: {str(e)}",
                "processing_status": "error"
            }
    
    def _handle_error(self, error: str, vehicle_info: Dict, damaged_parts: List[Dict]) -> Dict:
        """Handle agent processing errors with fallback."""
        return {
            "repair_parts": [],
            "error": error,
            "processing_status": "error",
            "fallback_info": {
                "vehicle": vehicle_info.get("make", "Unknown"),
                "damage_count": len(damaged_parts)
            },
            "suggestion": "Review input data and retry, or process manually"
        }

# Factory function for easy integration
def create_parts_agent() -> PartsDiscoveryAgent:
    """Create and return a configured parts discovery agent."""
    return PartsDiscoveryAgent()
```

### **Step 4: Modify Existing Pipeline (Day 3)**

Modify `generate_damage_report_staged.py` to integrate the agent.

**Find this section** (around line 580-600):
```python
# Phase 3: Generate repair parts list
if PHASE3_PROMPT.exists():
    phase3_text = PHASE3_PROMPT.read_text()
    parts_prompt = phase3_text.replace("<DETECTED_PARTS_JSON>", json.dumps(enriched_parts))
    parts_resp = call_openai_text(parts_prompt, model="gpt-4")
    try:
        parts_data = json.loads(parts_resp)
        detected["repair_parts"] = parts_data.get("repair_parts", [])
    except:
        detected["repair_parts"] = []
```

**Replace with**:
```python
# Phase 3: Intelligent parts discovery with agent
try:
    from agents.parts_agent import create_parts_agent
    
    # Create agent
    agent = create_parts_agent()
    
    # Process damage report
    parts_result = agent.process_damage_report(
        vehicle_info=detected.get("vehicle_info", {}),
        damaged_parts=enriched_parts
    )
    
    # Integrate results
    if parts_result.get("processing_status") == "error":
        print(f"Agent processing failed: {parts_result.get('error')}")
        # Fallback to original method
        if PHASE3_PROMPT.exists():
            phase3_text = PHASE3_PROMPT.read_text()
            parts_prompt = phase3_text.replace("<DETECTED_PARTS_JSON>", json.dumps(enriched_parts))
            parts_resp = call_openai_text(parts_prompt, model="gpt-4")
            try:
                parts_data = json.loads(parts_resp)
                detected["repair_parts"] = parts_data.get("repair_parts", [])
            except:
                detected["repair_parts"] = []
    else:
        detected["repair_parts"] = parts_result.get("repair_parts", [])
        detected["agent_metadata"] = {
            "processing_status": parts_result.get("processing_status"),
            "agent_confidence": parts_result.get("confidence", 0.0)
        }
        
except ImportError as e:
    print(f"Agent not available, using fallback: {str(e)}")
    # Fallback to original method
    if PHASE3_PROMPT.exists():
        phase3_text = PHASE3_PROMPT.read_text()
        parts_prompt = phase3_text.replace("<DETECTED_PARTS_JSON>", json.dumps(enriched_parts))
        parts_resp = call_openai_text(parts_prompt, model="gpt-4")
        try:
            parts_data = json.loads(parts_resp)
            detected["repair_parts"] = parts_data.get("repair_parts", [])
        except:
            detected["repair_parts"] = []
except Exception as e:
    print(f"Unexpected agent error: {str(e)}")
    detected["repair_parts"] = []
```

This integration provides a seamless transition with automatic fallback to your existing system if the agent fails, ensuring zero downtime during deployment.
