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
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

from agents.tools import all_tools

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
        
        # Set up all available tools
        self.tools = all_tools
        print(f"🔧 Agent initialized with {len(self.tools)} tools: {[tool.name for tool in self.tools]}")
        
        # Create specialized automotive agent prompt
        self.prompt = self._create_agent_prompt()
        
        # Use the official ReAct prompt template instead of custom one
        from langchain import hub
        try:
            # Get the standard ReAct prompt that works reliably
            react_prompt = hub.pull("hwchase17/react")
            self.prompt = react_prompt
            print("✅ Using official LangChain ReAct prompt")
        except:
            # Fallback to our custom prompt if hub is unavailable
            self.prompt = self._create_agent_prompt()
            print("⚠️  Using custom ReAct prompt (hub unavailable)")
        
        # Create ReAct agent
        self.agent = create_react_agent(self.llm, self.tools, self.prompt)
        
        # Create executor with robust error handling
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=max_iterations,
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )
    
    def _create_agent_prompt(self) -> PromptTemplate:
        """Create the specialized automotive parts discovery prompt template."""
        
        template = """You are an expert automotive parts specialist AI agent. Your task is to analyze vehicle damage reports and find exact OEM replacement parts from a comprehensive catalog.

You have access to the following tools:

{tools}

Use the following format:

Question: the vehicle damage analysis task
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer as a JSON object

FOLLOW THIS SYSTEMATIC APPROACH:

1. VEHICLE IDENTIFICATION: Use identify_vehicle_from_report
   Action Input: {{"damage_report_json": "[{{\"component\": \"Brake Component\"}}]", "vehicle_info_json": "{{\"make\": \"SEAT\", \"model\": \"Ibiza\", \"year\": 2020}}"}}

2. CATALOG VALIDATION: Use validate_vehicle_in_catalog
   Action Input: {{"manufacturer_id": "104", "model_name": "Ibiza"}}

3. VARIANT DISCOVERY: Use find_matching_variants
   Action Input: {{"manufacturer_id": "104", "model_name": "Ibiza", "year": 2020}}

4. COMPONENT MAPPING: Use map_components_to_categories
   Action Input: {{"damaged_components_json": "[\"Brake Component\"]"}}

5. PARTS SEARCH: Use search_parts_for_damage
   Action Input: {{"variant_ids_json": "[\"10615\"]", "damaged_components_json": "[\"Brake Component\"]"}}

FINAL ANSWER FORMAT - Return a JSON object:
{{
    "success": true/false,
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
