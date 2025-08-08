"""
Main Parts Discovery Agent using LangChain ReAct pattern.

This module implements the core agentic AI system for discovering OEM parts
from vehicle damage reports using advanced reasoning and tool orchestration.
"""

import os
import json
import re
from typing import Dict, List, Optional, Any
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from typing import Dict, List, Any
import json
import os
from dotenv import load_dotenv

# Import all tools
from .tools import all_tools
from .tools.vehicle_tools import identify_vehicle_from_report as _identify_vehicle
from .tools.vehicle_tools import validate_vehicle_in_catalog as _validate_vehicle
from .tools.vehicle_tools import find_matching_variants as _find_variants
from .tools.catalog_tools import map_components_to_categories as _map_components
from .tools.catalog_tools import load_categories_for_variant as _load_categories
from .tools.catalog_tools import search_parts_for_damage as _search_parts

# Create simplified wrapper tools for better ReAct compatibility
@tool
def identify_vehicle(input_text: str) -> Dict:
    """Extract vehicle info from damage report. Input: 'SEAT Ibiza 2020 with Brake Component damage'"""
    try:
        print(f"🔍 identify_vehicle called with: {input_text}")
        
        # The ReAct agent may send JSON string, parse it first
        try:
            # Try to parse as JSON first
            parsed_input = json.loads(input_text)
            if isinstance(parsed_input, dict) and 'input_text' in parsed_input:
                actual_input = parsed_input['input_text']
            else:
                actual_input = input_text
        except:
            # If parsing fails, use input as-is
            actual_input = input_text
            
        print(f"🔍 Processing: {actual_input}")
        
        # Parse the input text to extract vehicle and damage info
        parts = actual_input.split(' with ')
        vehicle_part = parts[0].strip()
        damage_part = parts[1].replace(' damage', '') if len(parts) > 1 else 'Unknown'
        
        # Extract make, model, year from vehicle part
        vehicle_words = vehicle_part.split()
        if len(vehicle_words) >= 3:
            make = vehicle_words[0]
            model = vehicle_words[1]
            year = int(vehicle_words[2]) if vehicle_words[2].isdigit() else 2020
        else:
            return {"success": False, "error": "Invalid input format"}
        
        # Create JSON strings for the actual tool
        damage_json = json.dumps([{"component": damage_part}])
        vehicle_json = json.dumps({"make": make, "model": model, "year": year})
        
        print(f"🔍 Calling _identify_vehicle with damage_json={damage_json}, vehicle_json={vehicle_json}")
        
        # Call the actual tool
        result = _identify_vehicle.func(damage_json, vehicle_json)
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def validate_vehicle_wrapper(manufacturer_id: str, model_name: str) -> Dict:
    """Validate vehicle in catalog. Input: manufacturer_id='117', model_name='Astra'"""
    try:
        result = _validate_vehicle.func(manufacturer_id, model_name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def find_variants_wrapper(manufacturer_id: str, model_name: str, year: int) -> Dict:
    """Find vehicle variants. Input: manufacturer_id='117', model_name='Astra', year=2018"""
    try:
        result = _find_variants.func(manufacturer_id, model_name, year)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def search_vehicle_parts(variant_id: str, component: str) -> Dict:
    """Search for parts. Input format: variant_id='10615', component='Brake Component'"""
    try:
        variant_json = json.dumps([variant_id])
        component_json = json.dumps([component])
        result = _search_parts.func(variant_json, component_json)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

class PartsDiscoveryAgent:
    """
    Main agentic AI system for discovering OEM parts from damage reports.
    Uses ReAct pattern to orchestrate multiple tools for intelligent parts discovery.
    
    The agent follows this workflow:
    1. Vehicle identification and validation
    2. Compatible variant discovery
    3. Component-to-category mapping
    4. Comprehensive parts search with relevance scoring
    5. Result validation and structured output
    """
    
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.2, max_iterations: int = 15):
        """
        Initialize the Parts Discovery Agent.
        
        Args:
            model_name: OpenAI model to use (default: gpt-4o)
            temperature: LLM temperature for reasoning (default: 0.2 for consistency)
            max_iterations: Maximum reasoning iterations (default: 15)
        """
        load_dotenv()
        
        # Initialize LLM with automotive-optimized settings
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY"),
            request_timeout=60,  # Allow time for complex reasoning
            max_retries=2
        )
        
        # Use the ORIGINAL tools - they work fine, the issue is with ReAct parsing
        self.tools = all_tools
        print(f"🔧 Agent initialized with {len(self.tools)} tools: {[tool.name for tool in self.tools]}")
        
        # Create specialized automotive agent prompt
        self.prompt = self._create_agent_prompt()
        
        # Use custom prompt with explicit tool input examples
        self.prompt = self._create_agent_prompt()
        print("🔧 Using custom ReAct prompt with tool input examples")
        
        # Use STRUCTURED_CHAT agent which properly handles multi-parameter tools
        from langchain.agents import initialize_agent, AgentType
        
        self.agent_executor = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10,
            max_execution_time=60,
            return_intermediate_steps=True
        )
        
        print("✅ Using STRUCTURED_CHAT agent for multi-parameter tools")
    
    def _custom_parsing_error_handler(self, error) -> str:
        """Custom handler for parsing errors to provide better guidance."""
        error_msg = str(error)
        
        # Common parsing issues and fixes
        if "Field required" in error_msg:
            if "vehicle_info_json" in error_msg:
                return "Error: Missing vehicle_info_json parameter. Use: {\"damage_report_json\": \"[...]\", \"vehicle_info_json\": \"{...}\"}"
            elif "damaged_components_json" in error_msg:
                return "Error: Missing damaged_components_json parameter. Use: {\"damaged_components_json\": \"[...]\"}"
        
        return f"Parsing error: {error_msg}. Please check the Action Input format matches the tool requirements exactly."
    
    def _create_agent_prompt(self) -> PromptTemplate:
        """Create the specialized automotive parts discovery prompt template."""
        
        template = """You are an expert automotive parts specialist AI agent. Find OEM replacement parts from damage reports.

You have access to the following tools:

{tools}

USE THIS EXACT FORMAT:

Question: the task
Thought: think about what to do
Action: tool name from [{tool_names}]
Action Input: {{"param1": "value1", "param2": "value2"}}
Observation: result
... (repeat as needed)
Thought: I now know the final answer
Final Answer: JSON result

TOOL INPUT EXAMPLES - USE THESE EXACT FORMATS:

1. identify_vehicle (Simple text input):
Action Input: {{"input_text": "SEAT Ibiza 2020 with Brake Component damage"}}

2. validate_vehicle_in_catalog:
Action Input: {{"manufacturer_id": "104", "model_name": "Ibiza"}}

3. find_matching_variants:
Action Input: {{"manufacturer_id": "104", "model_name": "Ibiza", "year": 2020}}

4. search_parts_for_damage (Include manufacturer_id):
Action Input: {{"variant_ids_json": "[\"10615\"]", "damaged_components_json": "[\"Brake Component\"]", "manufacturer_id": "117"}}

IMPORTANT:
- ALWAYS provide ALL required parameters for each tool
- Use the EXACT JSON format shown above
- Don't miss any required parameters

Workflow:
1. Use identify_vehicle_from_report (extract vehicle and damage info)
2. Use validate_vehicle_in_catalog (confirm vehicle exists)
3. Use find_matching_variants (get compatible variants)
4. Use search_parts_for_damage (find actual parts with manufacturer_id)

Final Answer format:
{{
    "success": true,
    "parts_found": [{{"component": "...", "part_name": "...", "part_number": "...", "relevance_score": 0.85}}],
    "vehicle_info": {{"make": "...", "model": "...", "year": "..."}},
    "confidence_score": 0.85
}}

Question: {input}
{agent_scratchpad}"""

        return PromptTemplate(
            input_variables=["tools", "tool_names", "input", "agent_scratchpad"],
            template=template
        )
    
    def process_damage_report(self, vehicle_info: Dict, damaged_parts: List[Dict]) -> Dict:
        """
        Main entry point for processing damage reports.
        
        Args:
            vehicle_info: Dict with vehicle make, model, year, etc.
            damaged_parts: List of damaged component dictionaries
            
        Returns:
            Dict with parts discovery results, reasoning, and confidence scores
        """
        try:
            print(f"🚗 Processing damage report for {vehicle_info.get('make', 'Unknown')} {vehicle_info.get('model', 'Unknown')}")
            print(f"🔧 Damaged components: {[part.get('component', str(part)) for part in damaged_parts]}")
            
            # Create a single input question for the ReAct agent
            input_question = f"""Analyze this vehicle damage report and find OEM replacement parts:
            
Vehicle: {vehicle_info.get('make', 'Unknown')} {vehicle_info.get('model', 'Unknown')} {vehicle_info.get('year', 'Unknown')}
Damaged Components: {[part.get('component', str(part)) for part in damaged_parts]}
            
Find the exact OEM parts needed for these damaged components."""
            
            # Execute agent reasoning
            result = self.agent_executor.invoke({
                "input": input_question
            })
            
            # Parse and structure the result
            return self._parse_agent_result(result, vehicle_info, damaged_parts)
            
        except Exception as e:
            print(f"❌ Agent processing error: {str(e)}")
            return {
                "error": f"Agent processing failed: {str(e)}",
                "success": False,
                "parts_found": [],
                "reasoning_steps": [f"Error occurred: {str(e)}"],
                "confidence_score": 0.0,
                "vehicle_info": vehicle_info,
                "search_summary": {
                    "total_parts_found": 0,
                    "components_searched": len(damaged_parts),
                    "variants_used": 0,
                    "categories_searched": 0
                }
            }
    
    def _parse_agent_result(self, result: Dict, vehicle_info: Dict, damaged_parts: List[Dict]) -> Dict:
        """Parse agent result into structured format with fallback extraction."""
        
        try:
            # Extract agent output
            agent_output = result.get("output", "")
            print(f"🤖 Agent output length: {len(agent_output)} characters")
            
            # Try to extract JSON from agent output
            structured_result = None
            if "{" in agent_output and "}" in agent_output:
                # Find JSON-like content in the output
                json_match = re.search(r'\{.*\}', agent_output, re.DOTALL)
                if json_match:
                    try:
                        structured_result = json.loads(json_match.group())
                        print("✅ Successfully parsed JSON from agent output")
                    except json.JSONDecodeError:
                        print("⚠️  JSON parsing failed, using fallback extraction")
            
            # Fallback: Extract information from intermediate steps
            if not structured_result:
                structured_result = self._extract_from_intermediate_steps(result, vehicle_info, damaged_parts)
            
            # Ensure required fields are present
            structured_result = self._ensure_result_structure(structured_result, vehicle_info, damaged_parts)
            
            return structured_result
            
        except Exception as e:
            print(f"❌ Result parsing error: {str(e)}")
            return {
                "error": f"Result parsing failed: {str(e)}",
                "success": False,
                "parts_found": [],
                "reasoning_steps": [f"Parsing error: {str(e)}"],
                "confidence_score": 0.0,
                "vehicle_info": vehicle_info,
                "search_summary": {
                    "total_parts_found": 0,
                    "components_searched": len(damaged_parts),
                    "variants_used": 0,
                    "categories_searched": 0
                }
            }
    
    def _extract_from_intermediate_steps(self, result: Dict, vehicle_info: Dict, damaged_parts: List[Dict]) -> Dict:
        """Extract structured data from intermediate tool execution steps."""
        
        intermediate_steps = result.get("intermediate_steps", [])
        
        # Initialize result structure
        extracted_result = {
            "success": False,
            "parts_found": [],
            "reasoning_steps": [],
            "vehicle_info": vehicle_info,
            "search_summary": {
                "total_parts_found": 0,
                "components_searched": len(damaged_parts),
                "variants_used": 0,
                "categories_searched": 0
            },
            "confidence_score": 0.0
        }
        
        found_parts = []
        vehicle_data = {}
        search_stats = {}
        
        # Process each intermediate step
        for step in intermediate_steps:
            action, observation = step
            tool_name = action.tool
            tool_input = action.tool_input
            
            # Log reasoning step
            extracted_result["reasoning_steps"].append(f"Action: {tool_name} with {str(tool_input)[:100]}...")
            
            # Extract vehicle information
            if tool_name == "identify_vehicle_from_report" and isinstance(observation, dict):
                if observation.get("success"):
                    vehicle_data.update(observation)
                    extracted_result["reasoning_steps"].append(f"✅ Vehicle identified: {observation.get('make')} {observation.get('model')}")
            
            # Extract parts search results
            elif tool_name == "search_parts_for_damage" and isinstance(observation, dict):
                if observation.get("success"):
                    parts = observation.get("parts", [])
                    found_parts.extend(parts)
                    search_stats = observation.get("search_stats", {})
                    extracted_result["reasoning_steps"].append(f"✅ Parts search: Found {len(parts)} parts")
                    extracted_result["success"] = True
        
        # Structure the found parts
        if found_parts:
            extracted_result["parts_found"] = [
                {
                    "component": part.get("matched_component", "Unknown"),
                    "part_name": part.get("name", "Unknown"),
                    "part_number": part.get("partNo", "N/A"),
                    "relevance_score": part.get("relevance_score", 0.0),
                    "manufacturer": part.get("manufacturer", "Unknown"),
                    "category_id": part.get("category_id", "Unknown"),
                    "variant_id": part.get("variant_id", "Unknown")
                }
                for part in found_parts[:20]  # Limit to top 20 parts
            ]
            
            # Update search summary
            extracted_result["search_summary"]["total_parts_found"] = len(found_parts)
            extracted_result["search_summary"]["variants_used"] = search_stats.get("variants_searched", 0)
            extracted_result["search_summary"]["categories_searched"] = search_stats.get("categories_searched", 0)
            
            # Calculate confidence score
            avg_relevance = sum(p.get("relevance_score", 0.0) for p in found_parts[:10]) / min(len(found_parts), 10)
            component_coverage = len(set(p.get("matched_component") for p in found_parts)) / len(damaged_parts)
            extracted_result["confidence_score"] = (avg_relevance + component_coverage) / 2
            
        # Update vehicle info with discovered data
        if vehicle_data:
            extracted_result["vehicle_info"].update(vehicle_data)
        
        return extracted_result
    
    def _ensure_result_structure(self, result: Dict, vehicle_info: Dict, damaged_parts: List[Dict]) -> Dict:
        """Ensure the result has all required fields with proper defaults."""
        
        # Required fields with defaults
        required_fields = {
            "success": False,
            "parts_found": [],
            "reasoning_steps": [],
            "confidence_score": 0.0,
            "vehicle_info": vehicle_info,
            "search_summary": {
                "total_parts_found": 0,
                "components_searched": len(damaged_parts),
                "variants_used": 0,
                "categories_searched": 0
            }
        }
        
        # Merge with existing result, ensuring all required fields are present
        for field, default_value in required_fields.items():
            if field not in result:
                result[field] = default_value
            elif field == "search_summary" and isinstance(result[field], dict):
                # Ensure search_summary has all required subfields
                for subfield, subdefault in default_value.items():
                    if subfield not in result[field]:
                        result[field][subfield] = subdefault
        
        return result

# Global instance for easy import
parts_agent = PartsDiscoveryAgent()
