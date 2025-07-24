# Essential Context - Agentic Parts Discovery Implementation

## 🎯 **PROJECT OVERVIEW**
Replace generic GPT-based parts planning in AutoDamageConnect with intelligent agentic AI that queries real OEM parts catalog from Google Cloud Storage.

## 📊 **CURRENT PROGRESS**
```
☐ Step 1: Environment Setup & Validation
☐ Step 2: Bucket Manager Foundation  
☐ Step 3: Vehicle Identification Tool
☐ Step 4: Variant Matching Tool
☐ Step 5: Parts Search Foundation
☐ Step 6: Parts Search Implementation
☐ Step 7: Agent Foundation
☐ Step 8: Agent Reasoning Logic
☐ Step 9: Damage Propagation Logic
☐ Step 10: Pipeline Integration
☐ Step 11: Performance Optimization
☐ Step 12: End-to-End Testing
☐ Step 13: Web App Integration
```

## 🔧 **TECHNICAL FOUNDATION**

### **Key Infrastructure**:
- **Google Cloud Project**: `rising-theater-466617-n8`
- **Parts Catalog Bucket**: `car-parts-catalogue-yc`
- **Bucket Structure**: `manufacturers/{id}/models_{id}.json`, `variants_{id}.json`, `articles_{variant}_{category}_{group}.json`
- **Integration Point**: Enhance `generate_damage_report_staged.py` parts planning phase

### **Core Architecture**:
- **Single ReAct Agent** with multiple specialized tools
- **Tool 1**: `identify_vehicle_from_report` - Maps damage report to vehicle info
- **Tool 2**: `find_matching_variants` - Finds compatible vehicle variants in catalog  
- **Tool 3**: `search_parts_for_damage` - Searches catalog for matching parts
- **Integration**: Replace generic parts planning with agent output + fallback

### **Catalog Data Structure**:
```json
{
  "article_id": "8053250",
  "part_name": "Front Bumper Cover", 
  "manufacturer_part_number": "VXH025001",
  "ean_number": "1234567890123",
  "oem_numbers": ["13437123"],
  "manufacturer_id": "117",
  "variant_id": "127445",
  "category_id": "100020"
}
```

## 🏗️ **CURRENT PROJECT STRUCTURE**
```
/backend/
├── generate_damage_report_staged.py  # Main pipeline (to be enhanced)
├── agents/                           # To be created
│   ├── bucket_manager.py            # Core catalog access
│   ├── parts_agent.py               # Main ReAct agent
│   └── tools/                       # Agent tools
│       ├── vehicle_tools.py         # Vehicle identification
│       └── catalog_tools.py         # Parts searching
└── tests/                           # Verification scripts
```

## 📋 **COMPLETED COMPONENTS**
*None yet - starting from Step 1*

## 🎯 **CURRENT OBJECTIVE**
Complete the next step in the implementation sequence, ensuring verification passes before proceeding.

---

*This context file updates after each completed step to maintain minimal but essential information for the LLM.*
