# LLM Implementation Steps - Agentic Parts Discovery

## 🎯 **OVERVIEW**
This guide breaks down the agentic AI implementation into **small, manageable chunks** that any LLM can execute successfully. Each step is **self-contained**, **verifiable**, and builds incrementally toward the complete system.

---

## 📋 **STEP 1: ENVIRONMENT SETUP & VALIDATION**

### **Task**: Set up Google Cloud access and validate bucket connectivity
### **Estimated Time**: 15 minutes
### **Prerequisites**: Google Cloud service account JSON key

### **Instructions**:
1. Create `.env` file with Google Cloud credentials
2. Install required dependencies
3. Test bucket access with a simple script
4. Verify manufacturer data structure

### **Files to Create**:
- `.env` (environment variables)
- `test_bucket_access.py` (validation script)

### **Success Criteria**:
- ✅ Can list manufacturers in bucket
- ✅ Can load a sample manufacturer's models.json
- ✅ Can access variant and category files

### **Verification Command**:
```bash
python test_bucket_access.py
# Should output: "✅ Bucket access successful - Found 35 manufacturers"
```

### **Next Step**: Proceed to Step 2 only after verification passes

---

## 📋 **STEP 2: BUCKET MANAGER FOUNDATION**

### **Task**: Create core bucket manager for catalog access
### **Estimated Time**: 20 minutes  
### **Prerequisites**: Step 1 completed successfully

### **Instructions**:
1. Create `agents/bucket_manager.py` with basic file loading
2. Implement manufacturer mapping functionality
3. Add caching for frequently accessed data
4. Test with sample data loading

### **Files to Create**:
- `agents/bucket_manager.py`
- `agents/__init__.py`
- `test_bucket_manager.py`

### **Key Functions to Implement**:
```python
class BucketManager:
    def load_json_file(self, file_path: str) -> Dict
    def get_manufacturer_id(self, manufacturer_name: str) -> str
    def get_models_for_manufacturer(self, manufacturer_id: str) -> List[Dict]
```

### **Success Criteria**:
- ✅ Can map "VAUXHALL" → "117"
- ✅ Can load models for manufacturer 117
- ✅ Can cache loaded data

### **Verification Command**:
```bash
python test_bucket_manager.py
# Should output: "✅ BucketManager working - Loaded 45 models for VAUXHALL"
```

---

## 📋 **STEP 3: VEHICLE IDENTIFICATION TOOL**

### **Task**: Create first agent tool for vehicle identification
### **Estimated Time**: 15 minutes
### **Prerequisites**: Step 2 completed successfully

### **Instructions**:
1. Create `agents/tools/vehicle_tools.py`
2. Implement `identify_vehicle_from_report` tool
3. Add manufacturer name mapping logic
4. Test with sample damage report data

### **Files to Create**:
- `agents/tools/vehicle_tools.py`
- `agents/tools/__init__.py`
- `test_vehicle_tools.py`

### **Tool Implementation**:
```python
@tool
def identify_vehicle_from_report(damage_report_json: str, vehicle_info_json: str) -> Dict:
    """Extract and validate vehicle information from damage report"""
    # Implementation here
```

### **Success Criteria**:
- ✅ Can extract vehicle info from JSON
- ✅ Maps manufacturer names to IDs correctly
- ✅ Returns structured vehicle data

### **Test Data**:
```json
{"make": "Vauxhall", "model": "Astra", "year": 2018}
```

### **Verification Command**:
```bash
python test_vehicle_tools.py
# Should output: "✅ Vehicle identification working - Found manufacturer_id: 117"
```

---

## 📋 **STEP 4: VARIANT MATCHING TOOL**

### **Task**: Create tool to find matching vehicle variants
### **Estimated Time**: 20 minutes
### **Prerequisites**: Step 3 completed successfully

### **Instructions**:
1. Add `find_matching_variants` tool to `vehicle_tools.py`
2. Implement fuzzy matching for model names
3. Add year-based filtering logic
4. Test with real catalog data

### **Tool Implementation**:
```python
@tool
def find_matching_variants(manufacturer_id: str, model_name: str, year: int = None) -> List[Dict]:
    """Find compatible vehicle variants from catalog"""
    # Implementation here
```

### **Success Criteria**:
- ✅ Can find variants for "Astra" model
- ✅ Filters variants by year correctly
- ✅ Returns compatibility scores

### **Verification Command**:
```bash
python test_variant_matching.py
# Should output: "✅ Found 3 compatible variants for 2018 Astra"
```

---

## 📋 **STEP 5: PARTS SEARCH TOOL FOUNDATION**

### **Task**: Create basic parts search functionality
### **Estimated Time**: 25 minutes
### **Prerequisites**: Step 4 completed successfully

### **Instructions**:
1. Create `agents/tools/catalog_tools.py`
2. Implement component-to-category mapping
3. Create `search_parts_for_damage` tool skeleton
4. Test category mapping logic

### **Files to Create**:
- `agents/tools/catalog_tools.py`
- `test_catalog_tools.py`

### **Key Mapping**:
```python
COMPONENT_CATEGORY_MAPPING = {
    "Front Bumper Cover": ["100020"],  # Body Parts
    "Headlight Assembly": ["100021"],  # Lighting
    # Add 20+ common components
}
```

### **Success Criteria**:
- ✅ Maps components to correct categories
- ✅ Can load category files from bucket
- ✅ Basic search structure working

### **Verification Command**:
```bash
python test_catalog_tools.py
# Should output: "✅ Component mapping working - Front Bumper → Category 100020"
```

---

## 📋 **STEP 6: PARTS SEARCH IMPLEMENTATION**

### **Task**: Complete the parts search tool implementation
### **Estimated Time**: 30 minutes
### **Prerequisites**: Step 5 completed successfully

### **Instructions**:
1. Complete `search_parts_for_damage` tool implementation
2. Add parts relevance scoring logic
3. Implement duplicate removal
4. Test with real damage data

### **Tool Implementation**:
```python
@tool
def search_parts_for_damage(variant_ids_json: str, damaged_components_json: str) -> List[Dict]:
    """Search catalog for parts matching damaged components"""
    # Full implementation here
```

### **Success Criteria**:
- ✅ Can search parts for multiple variants
- ✅ Returns relevant parts with scores
- ✅ Removes duplicate parts correctly

### **Test Cases**:
- Front Bumper Cover damage
- Headlight Assembly damage  
- Multiple component damage

### **Verification Command**:
```bash
python test_parts_search.py
# Should output: "✅ Found 12 relevant parts for Front Bumper Cover"
```

---

## 📋 **STEP 7: AGENT FOUNDATION**

### **Task**: Create the main ReAct agent structure
### **Estimated Time**: 20 minutes
### **Prerequisites**: Step 6 completed successfully

### **Instructions**:
1. Create `agents/parts_agent.py`
2. Set up LangChain ReAct agent
3. Add all tools to agent
4. Create basic processing method

### **Files to Create**:
- `agents/parts_agent.py`
- `test_agent_setup.py`

### **Agent Structure**:
```python
class PartsDiscoveryAgent:
    def __init__(self):
        self.tools = [identify_vehicle_tool, find_variants_tool, search_parts_tool]
        self.agent = create_react_agent(llm, self.tools, prompt)
    
    def process_damage_report(self, vehicle_info: Dict, damaged_parts: List[Dict]) -> Dict:
        # Basic processing logic
```

### **Success Criteria**:
- ✅ Agent initializes with all tools
- ✅ Can invoke tools individually
- ✅ Basic ReAct pattern working

### **Verification Command**:
```bash
python test_agent_setup.py
# Should output: "✅ Agent created with 3 tools - Ready for processing"
```

---

## 📋 **STEP 8: AGENT REASONING LOGIC**

### **Task**: Implement the agent's reasoning and tool orchestration
### **Estimated Time**: 25 minutes
### **Prerequisites**: Step 7 completed successfully

### **Instructions**:
1. Complete `process_damage_report` method
2. Add reasoning step tracking
3. Implement error handling and fallbacks
4. Test with sample damage reports

### **Success Criteria**:
- ✅ Agent follows reasoning steps correctly
- ✅ Calls tools in logical sequence
- ✅ Returns structured parts list
- ✅ Handles errors gracefully

### **Test Case**:
```json
{
  "vehicle": {"make": "Vauxhall", "model": "Astra", "year": 2018},
  "damaged_parts": [{"component": "Front Bumper Cover", "severity": "moderate"}]
}
```

### **Verification Command**:
```bash
python test_agent_reasoning.py
# Should output: "✅ Agent completed reasoning - Found 8 relevant parts"
```

---

## 📋 **STEP 9: DAMAGE PROPAGATION LOGIC**

### **Task**: Add intelligent damage propagation capabilities
### **Estimated Time**: 20 minutes
### **Prerequisites**: Step 8 completed successfully

### **Instructions**:
1. Add `analyze_damage_propagation` method to agent
2. Implement propagation rules for common scenarios
3. Add secondary parts discovery
4. Test with various damage types

### **Propagation Rules**:
```python
PROPAGATION_RULES = {
    "front_collision": ["radiator", "headlights", "sensors"],
    "side_impact": ["door_mechanisms", "window_systems"],
    "water_damage": ["electrical_systems", "interior_components"]
}
```

### **Success Criteria**:
- ✅ Identifies related parts beyond primary damage
- ✅ Adds consumables and secondary components
- ✅ Works for different damage types

### **Verification Command**:
```bash
python test_damage_propagation.py
# Should output: "✅ Propagation working - Found 12 parts including secondary damage"
```

---

## 📋 **STEP 10: PIPELINE INTEGRATION**

### **Task**: Integrate agent into existing damage report pipeline
### **Estimated Time**: 20 minutes
### **Prerequisites**: Step 9 completed successfully

### **Instructions**:
1. Modify `generate_damage_report_staged.py`
2. Add agent integration in parts planning phase
3. Implement fallback to existing system
4. Test with real damage report data

### **Integration Point**:
```python
# In generate_damage_report_staged.py, replace parts planning phase:
try:
    agent_result = parts_agent.process_damage_report(vehicle_info, damaged_parts)
    parts_list = agent_result["parts_list"]
except Exception as e:
    # Fallback to existing system
    parts_list = existing_parts_planning_logic()
```

### **Success Criteria**:
- ✅ Agent integrates without breaking existing flow
- ✅ Fallback works if agent fails
- ✅ Real parts data appears in reports

### **Verification Command**:
```bash
python test_pipeline_integration.py
# Should output: "✅ Pipeline integration working - Generated report with real parts"
```

---

## 📋 **STEP 11: PERFORMANCE OPTIMIZATION**

### **Task**: Add caching and performance improvements
### **Estimated Time**: 15 minutes
### **Prerequisites**: Step 10 completed successfully

### **Instructions**:
1. Add manufacturer mapping cache
2. Implement model/variant caching
3. Add request batching for multiple parts
4. Test performance improvements

### **Caching Strategy**:
```python
class CachedBucketManager:
    def __init__(self):
        self.manufacturer_cache = {}
        self.model_cache = {}
        self.variant_cache = {}
```

### **Success Criteria**:
- ✅ Subsequent requests are faster
- ✅ Memory usage is reasonable
- ✅ Cache hit rates > 70%

### **Verification Command**:
```bash
python test_performance.py
# Should output: "✅ Performance optimized - 3x faster on repeat requests"
```

---

## 📋 **STEP 12: END-TO-END TESTING**

### **Task**: Comprehensive testing with real damage reports
### **Estimated Time**: 25 minutes
### **Prerequisites**: Step 11 completed successfully

### **Instructions**:
1. Create comprehensive test suite
2. Test various damage scenarios
3. Validate output format and quality
4. Performance testing under load

### **Test Scenarios**:
- Front-end collision (multiple manufacturers)
- Side impact damage
- Interior water damage
- Engine bay issues
- Multiple damage types

### **Success Criteria**:
- ✅ All damage types handled correctly
- ✅ Parts lists are comprehensive and accurate
- ✅ Performance is acceptable (<30s per report)
- ✅ No critical errors or failures

### **Verification Command**:
```bash
python test_end_to_end.py
# Should output: "✅ All 15 test scenarios passed - System ready for production"
```

---

## 📋 **STEP 13: WEB APP INTEGRATION & COMPREHENSIVE PARTS DISPLAY**

### **Task**: Integrate agentic system with React frontend and display comprehensive parts information
### **Estimated Time**: 35 minutes
### **Prerequisites**: Step 12 completed successfully

### **Instructions**:
1. Update backend to return comprehensive parts data with all identifiers
2. Modify frontend ReportViewer to display rich parts information
3. Add parts procurement interface with unique identifiers
4. Create parts validation and ordering features

### **Files to Modify**:
- `generate_damage_report_staged.py` (backend output format)
- `src/components/ReportViewer.tsx` (frontend parts display)
- `src/components/PartsListViewer.tsx` (new component)

### **Comprehensive Parts Output Format**:
```json
{
  "parts_list": {
    "primary_parts": [
      {
        "article_id": "8053250",
        "part_name": "Front Bumper Cover",
        "manufacturer_part_number": "VXH025001", 
        "ean_number": "1234567890123",
        "oem_numbers": ["13437123", "VX4421"],
        "part_manufacturer": "VAUXHALL",
        "category": "Body Parts",
        "product_group": "Front Body Components",
        "compatibility": {
          "vehicle_make": "VAUXHALL",
          "model": "Astra", 
          "year_range": "2016-2020",
          "engine_compatibility": ["1.4T", "1.6L", "2.0L"]
        },
        "procurement_info": {
          "supplier_part_number": "VXH025001",
          "estimated_price": "£145.99",
          "availability": "In Stock",
          "lead_time": "2-3 days"
        },
        "installation_info": {
          "labor_hours": 2.5,
          "skill_level": "Intermediate",
          "special_tools_required": false,
          "consumables_needed": ["Bumper Clips", "Adhesive"]
        },
        "damage_relationship": {
          "damage_type": "Primary",
          "caused_by": "Front Impact",
          "affects_components": ["Headlight Assembly", "Radiator"]
        }
      }
    ],
    "secondary_parts": [
      {
        "article_id": "8053251",
        "part_name": "Headlight Assembly - Right",
        "manufacturer_part_number": "VXH098001",
        "ean_number": "1234567890124", 
        "oem_numbers": ["13437124"],
        "damage_relationship": {
          "damage_type": "Secondary",
          "caused_by": "Impact Propagation",
          "likelihood": "High (85%)"
        },
        "procurement_info": {
          "estimated_price": "£89.99",
          "availability": "In Stock"
        }
      }
    ],
    "consumables": [
      {
        "item_name": "Bumper Mounting Clips",
        "part_number": "VXH999001",
        "quantity_needed": 8,
        "unit_price": "£2.99",
        "purpose": "Front Bumper Installation"
      }
    ],
    "agent_reasoning": {
      "steps": [
        "Identified vehicle as 2018 Vauxhall Astra",
        "Found 3 compatible variants in catalog",
        "Detected front-end collision damage pattern",
        "Searched body parts and lighting categories",
        "Applied damage propagation rules",
        "Validated parts compatibility"
      ],
      "confidence_score": 0.92,
      "total_parts_found": 12,
      "estimated_total_cost": "£445.97"
    }
  }
}
```

### **Frontend Components to Create**:

#### **1. Enhanced ReportViewer Integration**:
```typescript
// In ReportViewer.tsx - Add comprehensive parts display
const PartsSection = ({ partsData }) => {
  return (
    <div className="parts-analysis-section">
      <h3>🔧 Agentic Parts Analysis</h3>
      
      {/* Primary Parts */}
      <div className="primary-parts">
        <h4>Primary Replacement Parts</h4>
        {partsData.primary_parts.map(part => (
          <PartCard key={part.article_id} part={part} type="primary" />
        ))}
      </div>
      
      {/* Secondary Parts */}
      <div className="secondary-parts">
        <h4>Secondary/Related Parts</h4>
        {partsData.secondary_parts.map(part => (
          <PartCard key={part.article_id} part={part} type="secondary" />
        ))}
      </div>
      
      {/* Agent Reasoning */}
      <div className="reasoning-display">
        <h4>🧠 AI Reasoning Process</h4>
        <AgentReasoningViewer reasoning={partsData.agent_reasoning} />
      </div>
      
      {/* Procurement Summary */}
      <div className="procurement-summary">
        <ProcurementSummary parts={partsData} />
      </div>
    </div>
  );
};
```

#### **2. Detailed Part Card Component**:
```typescript
// New component: src/components/PartCard.tsx
interface PartCardProps {
  part: {
    article_id: string;
    part_name: string;
    manufacturer_part_number: string;
    ean_number: string;
    oem_numbers: string[];
    procurement_info: {
      estimated_price: string;
      availability: string;
    };
  };
  type: 'primary' | 'secondary';
}

const PartCard: React.FC<PartCardProps> = ({ part, type }) => {
  return (
    <div className={`part-card ${type}`}>
      <div className="part-header">
        <h5>{part.part_name}</h5>
        <span className="price">{part.procurement_info.estimated_price}</span>
      </div>
      
      <div className="part-identifiers">
        <div className="identifier">
          <label>Part Number:</label>
          <code>{part.manufacturer_part_number}</code>
          <button onClick={() => copyToClipboard(part.manufacturer_part_number)}>📋</button>
        </div>
        
        <div className="identifier">
          <label>EAN/Barcode:</label>
          <code>{part.ean_number}</code>
          <button onClick={() => copyToClipboard(part.ean_number)}>📋</button>
        </div>
        
        {part.oem_numbers.length > 0 && (
          <div className="identifier">
            <label>OEM Numbers:</label>
            <div className="oem-list">
              {part.oem_numbers.map(oem => (
                <code key={oem}>{oem}</code>
              ))}
            </div>
          </div>
        )}
      </div>
      
      <div className="part-actions">
        <button className="btn-order">🛒 Add to Order</button>
        <button className="btn-compare">🔍 Compare Prices</button>
        <button className="btn-details">📋 Full Details</button>
      </div>
    </div>
  );
};
```

#### **3. Procurement Summary Component**:
```typescript
// New component: src/components/ProcurementSummary.tsx
const ProcurementSummary = ({ parts }) => {
  const totalCost = parts.agent_reasoning.estimated_total_cost;
  const totalParts = parts.agent_reasoning.total_parts_found;
  
  return (
    <div className="procurement-summary">
      <h4>📊 Procurement Summary</h4>
      
      <div className="summary-stats">
        <div className="stat">
          <label>Total Parts Found:</label>
          <span>{totalParts}</span>
        </div>
        <div className="stat">
          <label>Estimated Total Cost:</label>
          <span className="cost">{totalCost}</span>
        </div>
        <div className="stat">
          <label>AI Confidence:</label>
          <span>{(parts.agent_reasoning.confidence_score * 100).toFixed(1)}%</span>
        </div>
      </div>
      
      <div className="export-options">
        <button className="btn-export">📄 Export Parts List</button>
        <button className="btn-email">📧 Email to Supplier</button>
        <button className="btn-csv">📊 Download CSV</button>
      </div>
    </div>
  );
};
```

### **Backend Integration**:
```python
# In generate_damage_report_staged.py - Enhanced output
def enhance_parts_output(agent_result):
    """Convert agent output to comprehensive web app format"""
    enhanced_output = {
        "parts_list": {
            "primary_parts": [],
            "secondary_parts": [],
            "consumables": [],
            "agent_reasoning": agent_result.get("reasoning", {})
        }
    }
    
    for part in agent_result["parts_list"]:
        enhanced_part = {
            "article_id": part.get("id"),
            "part_name": part.get("name"),
            "manufacturer_part_number": part.get("partNo"),
            "ean_number": part.get("ean"),
            "oem_numbers": part.get("oemNumbers", []),
            "part_manufacturer": part.get("manufacturer"),
            "category": part.get("categoryName"),
            "compatibility": {
                "vehicle_make": vehicle_info.get("make"),
                "model": vehicle_info.get("model"),
                "year_range": part.get("yearRange")
            },
            "procurement_info": {
                "supplier_part_number": part.get("partNo"),
                "estimated_price": f"£{part.get('price', 'TBC')}",
                "availability": "To be confirmed"
            },
            "damage_relationship": {
                "damage_type": part.get("damageType", "Primary"),
                "caused_by": part.get("causedBy", "Direct damage")
            }
        }
        
        if part.get("damageType") == "Secondary":
            enhanced_output["parts_list"]["secondary_parts"].append(enhanced_part)
        else:
            enhanced_output["parts_list"]["primary_parts"].append(enhanced_part)
    
    return enhanced_output
```

### **Success Criteria**:
- ✅ Frontend displays comprehensive parts information
- ✅ All part identifiers (EAN, OEM, part numbers) are visible and copyable
- ✅ Agent reasoning process is transparent to users
- ✅ Procurement summary shows total costs and part counts
- ✅ Parts can be exported for ordering
- ✅ Primary and secondary parts are clearly distinguished
- ✅ Consumables and installation info are included

### **Verification Command**:
```bash
python test_web_integration.py
# Should output: "✅ Web integration complete - Rich parts data displaying correctly"
```

### **User Experience Features**:
- **📋 One-click copying** of part numbers and EAN codes
- **🛒 Procurement integration** with supplier ordering
- **🔍 Parts comparison** across multiple suppliers
- **📊 Cost estimation** with breakdown by category
- **🧠 AI reasoning transparency** showing decision process
- **📄 Export capabilities** for procurement teams

### **Additional Frontend Enhancements**:
```typescript
// Enhanced damage report display with rich parts info
const EnhancedReportDisplay = () => {
  return (
    <div className="enhanced-report">
      {/* Existing damage detection display */}
      <DamageAnalysisSection />
      
      {/* NEW: Comprehensive parts analysis */}
      <PartsAnalysisSection partsData={report.parts_list} />
      
      {/* NEW: Procurement tools */}
      <ProcurementToolsSection />
      
      {/* NEW: Agent reasoning display */}
      <AgentReasoningSection reasoning={report.parts_list.agent_reasoning} />
    </div>
  );
};
```

---

## 🎯 **EXECUTION STRATEGY FOR LLM**

### **Critical Guidelines**:

1. **⚠️ NEVER skip verification steps** - Each step MUST pass before proceeding
2. **🔍 Test incrementally** - Run verification command after each step
3. **🛑 Stop if verification fails** - Debug and fix before continuing
4. **📝 Document issues** - Keep track of any problems encountered
5. **🔄 Iterate if needed** - Some steps may need refinement

### **Failure Recovery**:
- If a step fails verification, debug that specific step only
- Don't proceed to next step until current step passes
- Keep changes small and focused
- Test each function individually before integration

### **Progress Tracking**:
```
☐ Step 1: Environment Setup
☐ Step 2: Bucket Manager  
☐ Step 3: Vehicle Tools
☐ Step 4: Variant Matching
☐ Step 5: Parts Search Foundation
☐ Step 6: Parts Search Implementation
☐ Step 7: Agent Foundation
☐ Step 8: Agent Reasoning
☐ Step 9: Damage Propagation
☐ Step 10: Pipeline Integration
☐ Step 11: Performance Optimization
☐ Step 12: End-to-End Testing
☐ Step 13: Web App Integration & Parts Display
```

---

## 🚀 **EXPECTED OUTCOME**

After completing all 13 steps, you will have:

- ✅ **Fully functional agentic AI system**
- ✅ **Real parts catalog integration**
- ✅ **Dynamic damage detection for any scenario**
- ✅ **Seamless pipeline integration with fallback**
- ✅ **Performance optimized for production use**
- ✅ **Comprehensive test coverage**
- ✅ **Rich web app integration with comprehensive parts display**
- ✅ **All unique part identifiers (EAN, OEM, part numbers) visible and copyable**
- ✅ **Procurement-ready interface with cost estimation**
- ✅ **Transparent AI reasoning display for users**
- ✅ **Export capabilities for parts ordering**

**Each step is designed to be completed in 15-35 minutes with clear success criteria. No hallucination, just focused execution!** 🎯
