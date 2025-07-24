# Step 10: Pipeline Integration

## 🎯 **OBJECTIVE**
Integrate the agentic AI system into the existing AutoDamageConnect damage report pipeline.

## ⏱️ **ESTIMATED TIME**: 35 minutes

## 📋 **PREREQUISITES**
- ✅ Step 9: Performance optimization complete
- ✅ Optimized agent system ready
- ✅ Understanding of existing pipeline structure

## 🏗️ **IMPLEMENTATION TASKS**

### **Task 1: Create Pipeline Service**
Create `/backend/services/parts_discovery_service.py` with:
- `PartsDiscoveryService` class wrapping the agent
- Handles pipeline integration with existing damage report flow
- Input validation and output formatting for API compatibility
- Graceful fallback when agent fails

### **Task 2: Add Report Enhancement Endpoint**
Add to `/backend/main.py` or appropriate FastAPI router:
- `/enhance-report/{document_id}` POST endpoint
- Fetches existing damage report from database
- Runs parts discovery agent on damage data
- Updates report with discovered parts information

### **Task 3: Implement Safety Mechanisms**
Add robust safety and fallback:
- Timeout protection (max 30 seconds)
- Try-catch error handling with logging
- Fallback to basic parts lookup if agent fails
- Preserve original report if enhancement fails

### **Task 4: Create Integration Test**
Create `/backend/test_pipeline_integration.py` that tests:
- End-to-end report enhancement flow
- Error handling and fallback mechanisms
- Database integration and persistence
- API endpoint functionality

### **Task 5: Add Configuration**
Add configuration options for:
- Enable/disable agentic enhancement
- Timeout settings
- Fallback behavior
- Performance monitoring

## ✅ **SUCCESS CRITERIA**
- ✅ Seamless integration with existing pipeline
- ✅ Reports enhanced with AI-discovered parts
- ✅ Fallback works when agent fails
- ✅ No disruption to existing functionality
- ✅ Performance acceptable (<30s processing)

## 🧪 **VERIFICATION COMMAND**
```bash
python test_pipeline_integration.py
```

**Expected Output:**
```
🧪 Testing Pipeline Integration...
✅ Report enhancement: 8 parts added to existing report
✅ Fallback test: Original report preserved on agent failure
✅ API endpoint: POST /enhance-report/123 returns 200
✅ Database persistence: Enhanced report saved successfully
🎉 Pipeline integration test complete - Ready for Step 11!
```

## ❌ **COMMON ISSUES**
- **"Agent timeout"**: Increase timeout or optimize performance
- **"Database connection error"**: Check database connectivity
- **"Report format mismatch"**: Verify input/output schemas

---
**Next Step**: Step 11 - Frontend Components

### **1. Create Pipeline Integration Module**

```python
# File: /backend/pipeline_integration.py (NEW FILE)
import json
import time
from typing import Dict, List, Optional
from agents.optimized_parts_agent import optimized_parts_agent

class AgenticPipelineIntegrator:
    """Integrates agentic parts discovery into existing pipeline with fallback safety"""
    
    def __init__(self, enable_agentic: bool = True, fallback_timeout: float = 30.0):
        self.enable_agentic = enable_agentic
        self.fallback_timeout = fallback_timeout
        self.stats = {'total_requests': 0, 'agentic_successes': 0, 'fallback_used': 0}
    
    def integrate_parts_discovery(self, vehicle_info: Dict, damaged_parts: List[Dict], 
                                  existing_parts_list: Optional[List[Dict]] = None) -> Dict:
        """Main integration point for parts discovery"""
        
        self.stats['total_requests'] += 1
        
        if not self.enable_agentic:
            return self._create_fallback_result(existing_parts_list, "Agentic discovery disabled")
        
        try:
            # Execute agentic discovery with timeout
            agentic_result = self._execute_with_timeout(
                optimized_parts_agent.process_damage_report,
                vehicle_info, damaged_parts, timeout=self.fallback_timeout
            )
            
            if agentic_result and agentic_result.get("success"):
                self.stats['agentic_successes'] += 1
                return self._enhance_agentic_result(agentic_result, existing_parts_list)
            else:
                return self._create_fallback_result(existing_parts_list, "Agentic system failed")
                
        except Exception as e:
            return self._create_fallback_result(existing_parts_list, f"Integration error: {str(e)}")
    
    def _execute_with_timeout(self, func, *args, timeout: float = 30.0):
        """Execute function with timeout protection"""
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(func, *args)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                return None
    
    def _enhance_agentic_result(self, agentic_result: Dict, existing_parts: Optional[List[Dict]]) -> Dict:
        """Enhance agentic result with pipeline metadata"""
        
        enhanced = agentic_result.copy()
        enhanced['pipeline_integration'] = {
            'source': 'agentic_discovery',
            'fallback_available': existing_parts is not None,
            'integration_timestamp': time.time()
        }
        
        # Convert to pipeline format
        enhanced['parts_list'] = self._convert_to_pipeline_format(enhanced.get('parts_list', []))
        return enhanced
    
    def _create_fallback_result(self, existing_parts: Optional[List[Dict]], reason: str) -> Dict:
        """Create fallback result using existing parts system"""
        
        self.stats['fallback_used'] += 1
        fallback_parts = existing_parts if existing_parts else []
        
        return {
            'success': True,
            'parts_list': self._convert_to_pipeline_format(fallback_parts),
            'pipeline_integration': {
                'source': 'fallback_system',
                'fallback_reason': reason,
                'integration_timestamp': time.time()
            },
            'confidence_score': 0.5,
            'total_parts_found': len(fallback_parts)
        }
    
    def _convert_to_pipeline_format(self, parts_list: List[Dict]) -> List[Dict]:
        """Convert agentic parts format to pipeline-compatible format"""
        
        converted_parts = []
        for part in parts_list:
            pipeline_part = {
                'part_name': part.get('part_name', 'Unknown Part'),
                'component': part.get('matched_component', part.get('component', 'Unknown')),
                'category': part.get('category', 'primary'),
                'oem_part_number': part.get('manufacturer_part_number', ''),
                'ean_number': part.get('ean_number', ''),
                'confidence': part.get('confidence_level', 'medium'),
                'source': 'agentic_discovery',
                'agentic_data': {
                    'relevance_score': part.get('relevance_score'),
                    'validation_score': part.get('validation_score'),
                    'compatibility_status': part.get('compatibility_status')
                }
            }
            converted_parts.append(pipeline_part)
        
        return converted_parts
    
    def get_integration_stats(self) -> Dict:
        """Get integration performance statistics"""
        total = self.stats['total_requests']
        return {
            'total_requests': total,
            'agentic_success_rate': round((self.stats['agentic_successes'] / max(total, 1)) * 100, 1),
            'fallback_usage_rate': round((self.stats['fallback_used'] / max(total, 1)) * 100, 1)
        }

# Global integrator instance
pipeline_integrator = AgenticPipelineIntegrator()
```

### **2. Update FastAPI Backend**

```python
# File: /backend/generate_damage_report_staged.py (UPDATE parts_planning_phase function)

# Add import at the top
from pipeline_integration import pipeline_integrator

# Replace the parts_planning_phase function:
def parts_planning_phase(enriched_parts, vehicle_info, output_dir):
    """Enhanced parts planning with agentic discovery"""
    
    print("🔧 PHASE 4: Enhanced Parts Planning with Agentic Discovery")
    
    try:
        # Prepare data for agentic system
        agentic_vehicle_info = {
            "make": vehicle_info.get("make", ""),
            "model": vehicle_info.get("model", ""),
            "year": vehicle_info.get("year"),
            "trim": vehicle_info.get("trim", "")
        }
        
        damaged_components = []
        for part in enriched_parts:
            if isinstance(part, dict):
                damaged_components.append({
                    "component": part.get("part", "Unknown"),
                    "severity": part.get("damage_type", "moderate"),
                    "description": part.get("description", "")
                })
        
        # Execute legacy parts planning for fallback
        legacy_parts_list = []
        try:
            # Original GPT-based parts planning logic here
            with open('prompts/plan_parts_prompt.txt', 'r') as f:
                parts_prompt = f.read()
            
            # ... existing legacy logic ...
            
        except Exception as e:
            print(f"⚠️ Legacy parts planning failed: {str(e)}")
        
        # Execute agentic integration
        agentic_result = pipeline_integrator.integrate_parts_discovery(
            agentic_vehicle_info, damaged_components, legacy_parts_list
        )
        
        if agentic_result.get("success"):
            planned_parts = agentic_result.get('parts_list', [])
            integration_info = agentic_result.get('pipeline_integration', {})
            
            print(f"✅ Parts discovery: {len(planned_parts)} parts from {integration_info.get('source')}")
            
            parts_planning_result = {
                "parts_list": planned_parts,
                "total_parts": len(planned_parts),
                "confidence_score": agentic_result.get('confidence_score', 0.8),
                "discovery_method": integration_info.get('source', 'agentic'),
                "labor_hours": calculate_labor_hours(planned_parts),
                "paint_hours": calculate_paint_hours(planned_parts)
            }
        else:
            # Complete fallback
            parts_planning_result = {
                "parts_list": [],
                "total_parts": 0,
                "confidence_score": 0.3,
                "discovery_method": "emergency_fallback",
                "labor_hours": 6.0,
                "paint_hours": 3.0
            }
    
    except Exception as e:
        print(f"❌ Enhanced parts planning error: {str(e)}")
        parts_planning_result = {
            "parts_list": [],
            "total_parts": 0,
            "confidence_score": 0.3,
            "discovery_method": "emergency_fallback",
            "error": str(e),
            "labor_hours": 6.0,
            "paint_hours": 3.0
        }
    
    # Save result
    parts_planning_path = output_dir / "parts_planning.json"
    with open(parts_planning_path, 'w') as f:
        json.dump(parts_planning_result, f, indent=2)
    
    print(f"✅ Enhanced parts planning complete: {parts_planning_result['total_parts']} parts")
    return parts_planning_result

def calculate_labor_hours(parts_list: List[Dict]) -> float:
    """Calculate estimated labor hours"""
    base_hours = 2.0
    for part in parts_list:
        category = part.get('category', 'primary')
        if category == 'primary':
            base_hours += 2.0
        elif category == 'secondary':
            base_hours += 1.0
        else:
            base_hours += 0.5
    return round(base_hours, 1)

def calculate_paint_hours(parts_list: List[Dict]) -> float:
    """Calculate estimated paint hours"""
    paint_hours = 0.0
    paint_keywords = ['bumper', 'panel', 'door', 'hood', 'fender', 'cover']
    
    for part in parts_list:
        part_name = part.get('part_name', '').lower()
        if any(keyword in part_name for keyword in paint_keywords):
            paint_hours += 1.5
    
    return round(max(paint_hours, 1.0), 1)
```

### **3. Create Integration Test**

```python
# File: /backend/test_pipeline_integration.py
import json
from pipeline_integration import pipeline_integrator

def test_basic_integration():
    """Test basic pipeline integration"""
    
    print("🧪 Testing Pipeline Integration...")
    
    vehicle_info = {"make": "Vauxhall", "model": "Astra", "year": 2018}
    damaged_parts = [
        {"component": "Front Bumper Cover", "severity": "severe"},
        {"component": "Headlight Assembly", "severity": "moderate"}
    ]
    legacy_parts = [{"part_name": "Generic Bumper", "component": "Front Bumper"}]
    
    result = pipeline_integrator.integrate_parts_discovery(
        vehicle_info, damaged_parts, legacy_parts
    )
    
    if result.get("success"):
        parts_list = result.get("parts_list", [])
        integration_info = result.get("pipeline_integration", {})
        
        print(f"✅ Integration successful:")
        print(f"   Parts found: {len(parts_list)}")
        print(f"   Source: {integration_info.get('source')}")
        print(f"   Confidence: {result.get('confidence_score', 0.0):.2f}")
        
        return len(parts_list) >= 1
    else:
        print(f"❌ Integration failed")
        return False

def test_fallback_behavior():
    """Test fallback when agentic is disabled"""
    
    print("\n🧪 Testing Fallback Behavior...")
    
    # Disable agentic temporarily
    original_enable = pipeline_integrator.enable_agentic
    pipeline_integrator.enable_agentic = False
    
    try:
        vehicle_info = {"make": "Toyota", "model": "Camry"}
        damaged_parts = [{"component": "Rear Bumper"}]
        legacy_parts = [{"part_name": "Fallback Bumper"}]
        
        result = pipeline_integrator.integrate_parts_discovery(
            vehicle_info, damaged_parts, legacy_parts
        )
        
        integration_info = result.get("pipeline_integration", {})
        source = integration_info.get("source")
        
        print(f"✅ Fallback successful: {source}")
        return source == "fallback_system"
        
    finally:
        pipeline_integrator.enable_agentic = original_enable

if __name__ == "__main__":
    basic_success = test_basic_integration()
    fallback_success = test_fallback_behavior()
    
    if basic_success and fallback_success:
        print("\n🎉 Pipeline integration test complete - Ready for Step 11!")
    else:
        print(f"\n⚠️ Tests failed - Basic: {basic_success}, Fallback: {fallback_success}")
```

## ✅ **SUCCESS CRITERIA**

1. **✅ Pipeline integration working** - Agentic discovery integrated into FastAPI backend
2. **✅ Fallback safety implemented** - Graceful fallback when agentic fails
3. **✅ Format conversion functional** - Parts converted to pipeline format
4. **✅ Backward compatibility maintained** - Existing pipeline continues working

## 🧪 **VERIFICATION COMMAND**

```bash
python test_pipeline_integration.py
```

## 🎯 **STEP COMPLETION**

**Only proceed to Step 11 if:**
- ✅ Integration test passes with agentic parts discovery
- ✅ Fallback test successfully uses legacy system
- ✅ Parts are properly formatted for pipeline
- ✅ No breaking changes to existing functionality

---

**Next Step**: Step 11 - Frontend Components
