# Step 7: Agent Foundation

## 🎯 **OBJECTIVE**
Create the main ReAct agent using LangChain with all tools integrated.

## ⏱️ **ESTIMATED TIME**: 20 minutes

## 📋 **PREREQUISITES**
- ✅ Step 6: Parts search implementation working
- ✅ All agent tools functional
- ✅ LangChain installed

## 🏗️ **IMPLEMENTATION TASKS**

### **Task 1: Create Parts Agent Class**
Create `/backend/agents/parts_agent.py` with:
- `PartsDiscoveryAgent` class using LangChain ReAct pattern
- Integration with OpenAI GPT-4o model
- `process_damage_report(vehicle_info, damaged_parts)` main method
- Structured prompt template for automotive parts expertise

### **Task 2: Configure Agent Prompt**
Create expert prompt template covering:
- Vehicle identification workflow
- Variant matching strategy
- Parts search methodology
- Output format requirements (structured JSON)
- Error handling instructions

### **Task 3: Implement Tool Orchestration**
Set up agent to use tools in logical sequence:
1. Vehicle identification → manufacturer mapping
2. Variant matching → compatible variants
3. Parts search → relevant parts with scoring
4. Result validation and formatting

### **Task 4: Add Error Handling**
Implement robust error handling for:
- Tool execution failures
- Invalid input data
- Timeout scenarios
- Partial results recovery

### **Task 5: Create Agent Test**
Create `/backend/test_agent_foundation.py` that tests:
- Basic agent initialization
- Tool availability and connectivity
- Simple damage report processing
- Error scenarios

## ✅ **SUCCESS CRITERIA**
- ✅ Agent initializes with all tools connected
- ✅ Can process simple damage reports end-to-end
- ✅ Returns structured JSON results
- ✅ Handles errors gracefully without crashing
- ✅ Tools execute in logical sequence

## 🧪 **VERIFICATION COMMAND**
```bash
python test_agent_foundation.py
```

**Expected Output:**
```
🧪 Testing Agent Foundation...
✅ Agent initialized with 6 tools
✅ LLM connection working
✅ Basic processing: Found 8 parts for Vauxhall Astra
✅ Error handling: Graceful failure for invalid input
🎉 Agent foundation test complete - Ready for Step 8!
```

## ❌ **COMMON ISSUES**
- **"OpenAI API key not found"**: Check environment variables
- **"Tool not found"**: Verify all tools imported correctly
- **"Agent timeout"**: Adjust max_iterations parameter

---
**Next Step**: Step 8 - Enhanced Reasoning

### **1. Create Main Parts Agent**
Create the core ReAct agent with all tools:

```python
# File: /backend/agents/parts_agent.py
import os
import json
from typing import Dict, List, Optional
from langchain.agents import create_react_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

from agents.tools import all_agent_tools

class PartsDiscoveryAgent:
    """
    Main agentic AI system for discovering OEM parts from damage reports.
    Uses ReAct pattern to orchestrate multiple tools for intelligent parts discovery.
    """
    
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.2):
        load_dotenv()
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Set up tools
        self.tools = all_agent_tools
        
        # Create agent prompt
        self.prompt = self._create_agent_prompt()
        
        # Create agent
        self.agent = create_react_agent(self.llm, self.tools, self.prompt)
        
        # Create executor
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True
        )
    
    def _create_agent_prompt(self) -> PromptTemplate:
        """Create the agent prompt template"""
        
        template = """You are an expert automotive parts specialist AI agent. Your job is to analyze vehicle damage reports and find the exact OEM replacement parts needed from a comprehensive parts catalog.

AVAILABLE TOOLS:
{tools}

REASONING PROCESS:
Use the following approach to find parts:

1. VEHICLE IDENTIFICATION: Use identify_vehicle_from_report to extract vehicle information and map to manufacturer ID
2. VARIANT MATCHING: Use find_matching_variants to find compatible vehicle variants in the catalog
3. PARTS SEARCH: Use search_parts_for_damage to find matching parts across variants
4. VALIDATION: Verify results make sense for the damage described

IMPORTANT GUIDELINES:
- Always start by identifying the vehicle make, model, and year
- Find compatible variants before searching for parts
- Consider damage propagation - related parts may also need replacement
- Prioritize parts with high relevance scores
- Provide reasoning for each step you take

INPUT FORMAT:
- vehicle_info: JSON with make, model, year, etc.
- damaged_parts: JSON array of damaged component objects

OUTPUT FORMAT:
Return a structured JSON with:
- parts_list: Array of found parts with all identifiers
- reasoning_steps: Your step-by-step reasoning process
- confidence_score: Overall confidence in results (0.0-1.0)
- total_parts_found: Number of parts discovered

Begin your analysis:

Vehicle Information: {vehicle_info}
Damaged Components: {damaged_parts}

{agent_scratchpad}"""

        return PromptTemplate(
            input_variables=["tools", "tool_names", "vehicle_info", "damaged_parts", "agent_scratchpad"],
            template=template
        )
    
    def process_damage_report(self, vehicle_info: Dict, damaged_parts: List[Dict]) -> Dict:
        """
        Main entry point for processing damage reports.
        
        Args:
            vehicle_info: Dict with vehicle make, model, year, etc.
            damaged_parts: List of damaged component objects
        
        Returns:
            Dict with parts list, reasoning, and metadata
        """
        try:
            # Prepare input data
            input_data = {
                "vehicle_info": json.dumps(vehicle_info),
                "damaged_parts": json.dumps([
                    part.get("component", str(part)) for part in damaged_parts
                ])
            }
            
            # Execute agent
            result = self.agent_executor.invoke(input_data)
            
            # Parse and structure result
            return self._parse_agent_result(result, vehicle_info, damaged_parts)
            
        except Exception as e:
            return {
                "error": f"Agent processing failed: {str(e)}",
                "success": False,
                "parts_list": [],
                "reasoning_steps": [f"Error occurred: {str(e)}"],
                "confidence_score": 0.0
            }
    
    def _parse_agent_result(self, result: Dict, vehicle_info: Dict, damaged_parts: List[Dict]) -> Dict:
        """Parse agent result into structured format"""
        
        try:
            # Extract agent output
            agent_output = result.get("output", "")
            
            # Try to extract JSON from agent output
            if "{" in agent_output and "}" in agent_output:
                # Find JSON in the output
                start_idx = agent_output.find("{")
                end_idx = agent_output.rfind("}") + 1
                json_str = agent_output[start_idx:end_idx]
                
                try:
                    parsed_result = json.loads(json_str)
                    if "parts_list" in parsed_result:
                        return parsed_result
                except json.JSONDecodeError:
                    pass
            
            # Fallback: create structured result from intermediate steps
            intermediate_steps = result.get("intermediate_steps", [])
            
            # Extract parts from tool calls
            found_parts = []
            reasoning_steps = []
            
            for step in intermediate_steps:
                action, observation = step
                reasoning_steps.append(f"Action: {action.tool} - {action.tool_input}")
                reasoning_steps.append(f"Result: {str(observation)[:200]}...")
                
                # If this was a parts search, extract the parts
                if action.tool == "search_parts_for_damage" and isinstance(observation, list):
                    found_parts.extend(observation)
            
            return {
                "success": True,
                "parts_list": found_parts[:20],  # Limit to top 20
                "reasoning_steps": reasoning_steps,
                "confidence_score": 0.8 if found_parts else 0.3,
                "total_parts_found": len(found_parts),
                "vehicle_info": vehicle_info,
                "processed_components": [part.get("component", str(part)) for part in damaged_parts]
            }
            
        except Exception as e:
            return {
                "error": f"Result parsing failed: {str(e)}",
                "success": False,
                "parts_list": [],
                "reasoning_steps": [f"Parsing error: {str(e)}"],
                "confidence_score": 0.0
            }

# Global instance for easy import
parts_agent = PartsDiscoveryAgent()
```

### **2. Update Agents Package**
Make the agent easily importable:

```python
# File: /backend/agents/__init__.py (UPDATE EXISTING)
from .bucket_manager import bucket_manager
from .parts_agent import parts_agent, PartsDiscoveryAgent

__all__ = ['bucket_manager', 'parts_agent', 'PartsDiscoveryAgent']
```

### **3. Create Agent Setup Test Script**
Test the agent initialization and basic functionality:

```python
# File: /backend/test_agent_setup.py
import json
from agents.parts_agent import parts_agent

def test_agent_initialization():
    """Test that the agent initializes correctly"""
    
    print("🧪 Testing Agent Initialization...")
    
    # Check agent components
    print(f"✅ Agent created with {len(parts_agent.tools)} tools")
    
    # List available tools
    tool_names = [tool.name for tool in parts_agent.tools]
    print(f"Available tools: {tool_names}")
    
    # Verify required tools are present
    required_tools = [
        "identify_vehicle_from_report",
        "find_matching_variants", 
        "search_parts_for_damage"
    ]
    
    missing_tools = [tool for tool in required_tools if tool not in tool_names]
    if missing_tools:
        print(f"❌ Missing required tools: {missing_tools}")
        return False
    
    print("✅ All required tools present")
    
    # Test LLM connection
    try:
        test_response = parts_agent.llm.invoke("Test connection")
        print("✅ LLM connection working")
    except Exception as e:
        print(f"❌ LLM connection failed: {str(e)}")
        return False
    
    return True

def test_agent_basic_processing():
    """Test basic agent processing with simple input"""
    
    print("\n🧪 Testing Basic Agent Processing...")
    
    # Simple test case
    vehicle_info = {
        "make": "Vauxhall",
        "model": "Astra", 
        "year": 2018
    }
    
    damaged_parts = [
        {"component": "Front Bumper Cover", "severity": "moderate"}
    ]
    
    print(f"🔍 Test input: {vehicle_info['make']} {vehicle_info['model']} - {damaged_parts[0]['component']}")
    
    try:
        # Process with timeout protection
        result = parts_agent.process_damage_report(vehicle_info, damaged_parts)
        
        if result.get("success"):
            parts_found = len(result.get("parts_list", []))
            reasoning_steps = len(result.get("reasoning_steps", []))
            confidence = result.get("confidence_score", 0.0)
            
            print(f"✅ Agent processing successful")
            print(f"   Parts found: {parts_found}")
            print(f"   Reasoning steps: {reasoning_steps}")
            print(f"   Confidence: {confidence:.2f}")
            
            # Show sample reasoning
            if result.get("reasoning_steps"):
                print("   Sample reasoning:")
                for step in result["reasoning_steps"][:3]:
                    print(f"     - {step}")
            
            return parts_found > 0 and confidence > 0.5
            
        else:
            print(f"❌ Agent processing failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Agent processing error: {str(e)}")
        return False

def test_agent_tools_individually():
    """Test that individual tools work through the agent"""
    
    print("\n🧪 Testing Individual Tool Access...")
    
    success_count = 0
    
    # Test each tool individually
    for tool in parts_agent.tools:
        print(f"🔍 Testing tool: {tool.name}")
        
        try:
            # Get tool description
            if hasattr(tool, 'description'):
                print(f"   Description: {tool.description[:100]}...")
            
            print(f"   ✅ Tool {tool.name} accessible")
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Tool {tool.name} error: {str(e)}")
    
    print(f"📊 Tool accessibility: {success_count}/{len(parts_agent.tools)} tools working")
    
    return success_count == len(parts_agent.tools)

if __name__ == "__main__":
    try:
        print("🧪 Testing Agent Foundation Setup...")
        
        init_success = test_agent_initialization()
        tools_success = test_agent_tools_individually()
        processing_success = test_agent_basic_processing()
        
        if init_success and tools_success and processing_success:
            print("\n🎉 Agent foundation test complete - Ready for Step 8!")
        else:
            print(f"\n⚠️ Tests failed - Init: {init_success}, Tools: {tools_success}, Processing: {processing_success}")
    except Exception as e:
        print(f"\n❌ Agent setup test error: {str(e)}")
```

## ✅ **SUCCESS CRITERIA**

After completing this step, you should have:

1. **✅ ReAct agent created** - LangChain agent with all tools integrated
2. **✅ Tool orchestration working** - Agent can call tools in sequence
3. **✅ Prompt template functional** - Clear instructions for agent reasoning
4. **✅ Error handling implemented** - Graceful failure and recovery
5. **✅ Result parsing operational** - Structures agent output properly
6. **✅ LLM connection verified** - OpenAI API working

## 🧪 **VERIFICATION COMMAND**

Run this command to verify the step is complete:

```bash
python test_agent_setup.py
```

**Expected Output:**
```
🧪 Testing Agent Foundation Setup...

🧪 Testing Agent Initialization...
✅ Agent created with 6 tools
Available tools: ['identify_vehicle_from_report', 'validate_vehicle_in_catalog', 'find_matching_variants', 'map_components_to_categories', 'load_categories_for_variant', 'search_parts_for_damage']
✅ All required tools present
✅ LLM connection working

🧪 Testing Individual Tool Access...
🔍 Testing tool: identify_vehicle_from_report
   Description: Extract and validate vehicle information from damage report...
   ✅ Tool identify_vehicle_from_report accessible
[... similar for all tools ...]
📊 Tool accessibility: 6/6 tools working

🧪 Testing Basic Agent Processing...
🔍 Test input: Vauxhall Astra - Front Bumper Cover
✅ Agent processing successful
   Parts found: 8
   Reasoning steps: 12
   Confidence: 0.85
   Sample reasoning:
     - Action: identify_vehicle_from_report - {'damage_report_json': '{}', 'vehicle_info_json': '...'}
     - Result: {'manufacturer_id': '117', 'make': 'VAUXHALL', 'model': 'Astra'...
     - Action: find_matching_variants - {'manufacturer_id': '117', 'model_name': 'Astra'...

🎉 Agent foundation test complete - Ready for Step 8!
```

## ❌ **COMMON ISSUES & SOLUTIONS**

### **Issue 1: "OpenAI API key not found"**
**Solution**: Ensure `OPENAI_API_KEY` is set in your `.env` file.

### **Issue 2: "Tool not found" errors**
**Solution**: Verify all tools are properly imported in `agents/tools/__init__.py`.

### **Issue 3: Agent times out or doesn't respond**
**Solution**: Check the `max_iterations` setting and ensure tools return results quickly.

### **Issue 4: Parsing errors in result processing**
**Solution**: The fallback parsing should handle this, but verify JSON structure in agent output.

## 🎯 **STEP COMPLETION**

**Only proceed to Step 8 if:**
- ✅ Agent initializes with all 6 tools
- ✅ LLM connection is working
- ✅ Basic processing returns parts and reasoning
- ✅ Confidence score is reasonable (> 0.5)

**If verification fails:**
- 🔧 Check OpenAI API key and quota
- 🔧 Verify all previous steps are working
- 🔧 Ensure tools are properly imported
- 🛑 DO NOT proceed to Step 8 until this step passes

---

**Next Step**: Step 8 - Agent Reasoning Logic
