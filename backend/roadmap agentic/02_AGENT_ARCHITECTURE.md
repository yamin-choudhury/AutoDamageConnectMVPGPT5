# 🤖 Agent Architecture: Technical Design

## 🏗️ **Agent System Design**

### **Single Agent with Multiple Tools (Recommended)**
Use a **ReAct pattern agent** with specialized tools rather than multiple agents. This approach provides:
- **Coherent reasoning** across the entire parts discovery process
- **Simpler debugging** and maintenance
- **Better context retention** between tool calls
- **Easier integration** with existing pipeline

### **Agent Framework Choice: LangChain/LangGraph**
```python
from langchain.agents import create_openai_tools_agent
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
```

**Why LangChain over CrewAI:**
- Better integration with your existing OpenAI setup
- More control over tool execution flow
- Extensive documentation and community support
- Natural fit with your current prompt-based architecture

## 🛠️ **Core Agent Tools**

### **Tool 1: Vehicle Identifier**
```python
@tool
def identify_vehicle_from_report(damage_report: str, vehicle_info: dict) -> dict:
    """
    Extract precise vehicle identification from damage report.
    
    Args:
        damage_report: JSON string from damage detection phase
        vehicle_info: Vehicle identification from phase 1
    
    Returns:
        dict: {
            "make": "VAUXHALL",
            "model": "Astra", 
            "year": 2018,
            "engine": "1.6L Turbo",
            "confidence": 0.95
        }
    """
```

### **Tool 2: Manufacturer Lookup**
```python
@tool
def get_manufacturer_id(make_name: str) -> str:
    """
    Convert manufacturer name to catalog ID.
    
    Args:
        make_name: Vehicle manufacturer name (e.g., "VAUXHALL")
    
    Returns:
        str: Manufacturer ID for catalog queries (e.g., "117")
    """
```

### **Tool 3: Vehicle Variant Finder**
```python
@tool
def find_vehicle_variants(manufacturer_id: str, model_name: str, year: int) -> list:
    """
    Find matching vehicle variants in parts catalog.
    
    Args:
        manufacturer_id: Catalog manufacturer ID
        model_name: Vehicle model name
        year: Vehicle year
    
    Returns:
        list: Matching variant objects with IDs and specifications
    """
```

### **Tool 4: Parts Catalog Searcher**
```python
@tool
def search_parts_for_damage(variant_ids: list, damaged_components: list) -> list:
    """
    Find compatible OEM parts for identified damage.
    
    Args:
        variant_ids: List of compatible vehicle variant IDs
        damaged_components: List of damaged component descriptions
    
    Returns:
        list: Compatible parts with full catalog information
    """
```

### **Tool 5: Parts Validator**
```python
@tool
def validate_parts_compatibility(parts_list: list, vehicle_variant: dict) -> dict:
    """
    Validate parts compatibility and suggest alternatives.
    
    Args:
        parts_list: List of identified parts
        vehicle_variant: Specific vehicle variant information
    
    Returns:
        dict: Validation results with alternatives if needed
    """
```

## 🧠 **Agent System Prompt**

### **Core Identity**
```
You are "AutoPartsExpert", an expert automotive parts specialist with access to a comprehensive UK auto parts catalog containing 35 major manufacturers and millions of OEM parts.

Your mission: Transform damage reports into precise, procurement-ready parts lists using real catalog data.

CRITICAL: You must ONLY recommend parts that exist in the catalog. Never guess or hallucinate parts.
```

### **Reasoning Instructions**
```
When processing a damage report, follow this reasoning chain:

1. IDENTIFY: Extract precise vehicle information (make, model, year, engine)
2. LOCATE: Find the vehicle in the parts catalog using manufacturer and variant IDs
3. MAP: Connect damaged components to catalog categories and product groups  
4. SEARCH: Query catalog for compatible OEM parts
5. VALIDATE: Ensure parts fit the specific vehicle variant
6. ENHANCE: Include related parts and consumables based on damage type
7. FORMAT: Return structured JSON with complete procurement information

Always explain your reasoning for transparency and debugging.
```

### **Error Handling Instructions**
```
If any step fails:
- Vehicle not found: Suggest closest match with confidence score
- Parts not available: Provide alternative options with compatibility notes
- Ambiguous damage: Request clarification or provide multiple scenarios
- Catalog errors: Gracefully fallback with explanation

Never proceed with incomplete or uncertain information.
```

## 📊 **Agent Workflow Logic**

### **Phase 1: Context Analysis**
```python
# Agent receives existing damage report data
input_data = {
    "vehicle_info": {...},      # From your existing phase 1
    "damaged_parts": [...],     # From your existing phase 2
    "images": [...]             # Original damage images
}
```

### **Phase 2: Intelligent Processing**
```python
# Agent reasoning process
def agent_process(input_data):
    # Step 1: Vehicle identification refinement
    vehicle = identify_vehicle_from_report(
        input_data["damaged_parts"], 
        input_data["vehicle_info"]
    )
    
    # Step 2: Catalog navigation
    manufacturer_id = get_manufacturer_id(vehicle["make"])
    variants = find_vehicle_variants(
        manufacturer_id, 
        vehicle["model"], 
        vehicle["year"]
    )
    
    # Step 3: Parts discovery
    parts = search_parts_for_damage(
        [v["id"] for v in variants],
        [p["name"] for p in input_data["damaged_parts"]]
    )
    
    # Step 4: Validation and enhancement
    validated_parts = validate_parts_compatibility(parts, variants[0])
    
    return structured_response(validated_parts)
```

### **Phase 3: Structured Output**
```python
# Agent returns enhanced parts list
{
    "repair_parts": [
        {
            "catalog_id": "8053250",
            "name": "Front Brake Pad Set", 
            "part_number": "VXH025001",
            "ean_number": "1234567890123",
            "oem_numbers": {
                "VAUXHALL": "13437123",
                "OPEL": "13437123"
            },
            "manufacturer": "VAUXHALL",
            "category": "Brake System",
            "product_group": "Brake Pads",
            "fits_vehicles": ["2018 Vauxhall Astra K 1.6L Turbo"],
            "variant_ids": ["127445"],
            "labour_hours": 1.5,
            "paint_hours": 0.0,
            "oem_only": false,
            "price_estimate": "£89.99",
            "availability": "in_stock",
            "supplier_info": {...},
            "related_parts": ["brake_cleaner", "copper_grease"],
            "confidence": 0.98,
            "reasoning": "Direct match for front brake damage on 2018 Astra variant 127445"
        }
    ],
    "metadata": {
        "total_parts": 5,
        "vehicle_match_confidence": 0.95,
        "catalog_coverage": "complete",
        "processing_time": "2.3s"
    }
}
```

## 🔧 **Tool Implementation Strategy**

### **Tool Development Priority**
1. **Vehicle Identifier** (Day 1) - Core vehicle matching logic
2. **Manufacturer Lookup** (Day 1) - Simple mapping table
3. **Parts Searcher** (Day 2-3) - Complex catalog querying
4. **Variant Finder** (Day 2-3) - Vehicle specification matching
5. **Parts Validator** (Day 4-5) - Compatibility checking

### **Google Cloud Storage Integration**
```python
from google.cloud import storage

class BucketManager:
    def __init__(self, bucket_name="car-parts-catalogue-yc"):
        self.client = storage.Client(project="rising-theater-466617-n8")
        self.bucket = self.client.bucket(bucket_name)
        self.cache = {}  # In-memory caching
    
    def load_json_file(self, file_path):
        """Load JSON file from bucket with caching"""
        if file_path in self.cache:
            return self.cache[file_path]
            
        blob = self.bucket.blob(file_path)
        if blob.exists():
            content = json.loads(blob.download_as_text())
            self.cache[file_path] = content
            return content
        return None
```

### **Error Handling Patterns**
```python
class AgentError:
    VEHICLE_NOT_FOUND = "Vehicle not found in catalog"
    PARTS_UNAVAILABLE = "No compatible parts available"
    CATALOG_ERROR = "Catalog access error"
    VALIDATION_FAILED = "Parts validation failed"

def handle_agent_error(error_type, context):
    """Graceful error handling with fallback options"""
    return {
        "success": False,
        "error": error_type,
        "fallback": get_fallback_response(context),
        "suggestions": get_alternative_options(context)
    }
```

## 📈 **Performance Optimization**

### **Caching Strategy**
- **File-level caching**: Cache frequently accessed JSON files
- **Query-level caching**: Cache common vehicle→parts mappings
- **Session-level caching**: Maintain cache during single damage report processing

### **Parallel Processing**
- **Concurrent tool calls**: Execute independent tools simultaneously
- **Batch queries**: Group related bucket operations
- **Async operations**: Non-blocking catalog access

### **Smart Querying**
- **Lazy loading**: Only query needed catalog sections
- **Smart indexing**: Build runtime indexes for frequent lookups
- **Query optimization**: Minimize bucket access calls

This architecture provides a robust, scalable foundation for intelligent parts discovery while maintaining compatibility with your existing system.
