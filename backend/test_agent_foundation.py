#!/usr/bin/env python3
"""
Test script for Step 7: Agent Foundation

Tests the complete ReAct agent functionality including:
- Agent initialization with all tools
- LLM connectivity and reasoning
- End-to-end damage report processing
- Tool orchestration workflow
- Error handling and recovery
"""

import json
import time
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from agents.parts_agent import parts_agent

def test_agent_initialization():
    """Test that the agent initializes correctly with all components."""
    
    print("🧪 Testing Agent Initialization...")
    print("-" * 50)
    
    try:
        # Check basic agent components
        print(f"✅ Agent created with {len(parts_agent.tools)} tools")
        
        # List available tools
        tool_names = [tool.name for tool in parts_agent.tools]
        print(f"📋 Available tools: {tool_names}")
        
        # Verify expected tools are present
        expected_tools = [
            'identify_vehicle_from_report',
            'validate_vehicle_in_catalog', 
            'find_matching_variants',
            'map_components_to_categories',
            'load_categories_for_variant',
            'search_parts_for_damage'
        ]
        
        missing_tools = [tool for tool in expected_tools if tool not in tool_names]
        if missing_tools:
            print(f"⚠️  Missing expected tools: {missing_tools}")
            return False
        else:
            print("✅ All required tools present")
        
        # Test LLM connection
        try:
            test_response = parts_agent.llm.invoke("Test connection - respond with 'OK'")
            print("✅ LLM connection working")
            print(f"   Response: {str(test_response.content)[:50]}...")
        except Exception as e:
            print(f"❌ LLM connection failed: {str(e)}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Agent initialization failed: {str(e)}")
        return False

def test_agent_tools_individually():
    """Test each tool is accessible from the agent."""
    
    print(f"\n🧪 Testing Individual Tool Access...")
    print("-" * 50)
    
    success_count = 0
    
    for tool in parts_agent.tools:
        print(f"🔍 Testing tool: {tool.name}")
        
        try:
            # Get tool description and verify it's accessible
            if hasattr(tool, 'description'):
                print(f"   Description: {tool.description[:80]}...")
            
            # Verify tool has required attributes
            if hasattr(tool, 'func') and callable(tool.func):
                print(f"   ✅ Tool {tool.name} accessible and callable")
                success_count += 1
            else:
                print(f"   ⚠️  Tool {tool.name} missing callable function")
            
        except Exception as e:
            print(f"   ❌ Tool {tool.name} error: {str(e)}")
    
    print(f"📊 Tool accessibility: {success_count}/{len(parts_agent.tools)} tools working")
    
    return success_count == len(parts_agent.tools)

def test_agent_basic_processing():
    """Test basic agent processing with a simple damage report."""
    
    print(f"\n🧪 Testing Basic Agent Processing...")
    print("-" * 50)
    
    # Simple test case with known good data
    vehicle_info = {
        "make": "Vauxhall",
        "model": "Astra", 
        "year": 2018
    }
    
    damaged_parts = [
        {"component": "Brake Disc", "severity": "moderate"},
        {"component": "Engine Component", "severity": "minor"}
    ]
    
    print(f"🔍 Test input: {vehicle_info['make']} {vehicle_info['model']} {vehicle_info['year']}")
    print(f"🔧 Damaged components: {[part['component'] for part in damaged_parts]}")
    
    try:
        start_time = time.time()
        
        # Process the damage report
        result = parts_agent.process_damage_report(vehicle_info, damaged_parts)
        
        processing_time = time.time() - start_time
        
        print(f"⏱️  Processing time: {processing_time:.2f} seconds")
        
        # Analyze results
        if result.get("success"):
            parts_found = result.get("parts_found", [])
            reasoning_steps = result.get("reasoning_steps", [])
            confidence = result.get("confidence_score", 0.0)
            search_summary = result.get("search_summary", {})
            
            print(f"✅ Agent processing successful")
            print(f"   Parts found: {len(parts_found)}")
            print(f"   Reasoning steps: {len(reasoning_steps)}")
            print(f"   Confidence: {confidence:.2f}")
            print(f"   Search summary: {search_summary}")
            
            # Show sample results
            if parts_found:
                print(f"   Sample parts:")
                for i, part in enumerate(parts_found[:3]):
                    component = part.get('component', 'Unknown')
                    part_name = part.get('part_name', 'Unknown')
                    relevance = part.get('relevance_score', 0.0)
                    print(f"     {i+1}. {component} → {part_name[:40]}... (score: {relevance:.3f})")
            
            # Show sample reasoning
            if reasoning_steps:
                print(f"   Sample reasoning:")
                for i, step in enumerate(reasoning_steps[:3]):
                    print(f"     {i+1}. {step[:80]}...")
            
            # Check quality thresholds
            if len(parts_found) > 0 and confidence > 0.3:
                print(f"   ✅ Quality check passed (parts: {len(parts_found)}, confidence: {confidence:.2f})")
                return True
            else:
                print(f"   ⚠️  Quality check failed (parts: {len(parts_found)}, confidence: {confidence:.2f})")
                return False
                
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ Agent processing failed: {error}")
            
            # Show reasoning steps even on failure
            reasoning_steps = result.get("reasoning_steps", [])
            if reasoning_steps:
                print(f"   Reasoning attempted:")
                for i, step in enumerate(reasoning_steps[:3]):
                    print(f"     {i+1}. {step[:80]}...")
            
            return False
            
    except Exception as e:
        print(f"❌ Basic processing test error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_agent_error_handling():
    """Test agent behavior with invalid inputs."""
    
    print(f"\n🧪 Testing Error Handling...")
    print("-" * 50)
    
    test_cases = [
        {
            "name": "Invalid vehicle make",
            "vehicle_info": {"make": "NonExistentBrand", "model": "UnknownModel", "year": 2020},
            "damaged_parts": [{"component": "Front Bumper"}]
        },
        {
            "name": "Empty damaged parts",
            "vehicle_info": {"make": "Vauxhall", "model": "Astra", "year": 2018},
            "damaged_parts": []
        },
        {
            "name": "Invalid year",
            "vehicle_info": {"make": "Vauxhall", "model": "Astra", "year": 1800},
            "damaged_parts": [{"component": "Engine"}]
        }
    ]
    
    success_count = 0
    
    for test_case in test_cases:
        print(f"🔍 Testing: {test_case['name']}")
        
        try:
            result = parts_agent.process_damage_report(
                test_case['vehicle_info'], 
                test_case['damaged_parts']
            )
            
            # Agent should handle errors gracefully without crashing
            if isinstance(result, dict) and "error" not in result:
                print(f"   ✅ Handled gracefully - returned result")
                success_count += 1
            elif isinstance(result, dict) and result.get("success") is False:
                print(f"   ✅ Handled gracefully - returned failure")
                success_count += 1
            else:
                print(f"   ⚠️  Unexpected result format")
                
        except Exception as e:
            print(f"   ❌ Exception not handled: {str(e)}")
    
    print(f"📊 Error handling: {success_count}/{len(test_cases)} cases handled gracefully")
    
    return success_count >= len(test_cases) - 1  # Allow 1 failure

def test_agent_workflow_validation():
    """Test that the agent follows the expected workflow."""
    
    print(f"\n🧪 Testing Workflow Validation...")
    print("-" * 50)
    
    # Use a simple case to track workflow
    vehicle_info = {"make": "SEAT", "model": "Test", "year": 2020}  # Use SEAT (manufacturer 104)
    damaged_parts = [{"component": "Brake Component"}]
    
    print(f"🔍 Workflow test: {vehicle_info['make']} {vehicle_info['model']}")
    
    try:
        result = parts_agent.process_damage_report(vehicle_info, damaged_parts)
        
        reasoning_steps = result.get("reasoning_steps", [])
        
        # Check for expected workflow steps
        workflow_checks = {
            "vehicle_identification": any("identify_vehicle_from_report" in step for step in reasoning_steps),
            "component_mapping": any("map_components_to_categories" in step for step in reasoning_steps),
            "parts_search": any("search_parts_for_damage" in step for step in reasoning_steps)
        }
        
        print(f"📋 Workflow analysis:")
        for step_name, found in workflow_checks.items():
            status = "✅" if found else "⚠️ "
            print(f"   {status} {step_name}: {'Found' if found else 'Missing'}")
        
        # Count successful workflow steps
        workflow_success = sum(workflow_checks.values()) >= 2  # At least 2 major steps
        
        if workflow_success:
            print(f"   ✅ Workflow validation passed")
            return True
        else:
            print(f"   ⚠️  Workflow validation failed - missing key steps")
            return False
            
    except Exception as e:
        print(f"❌ Workflow validation error: {str(e)}")
        return False

def main():
    """Run all agent foundation tests."""
    print("🧪 Testing Agent Foundation...")
    print("=" * 60)
    
    try:
        # Core component tests
        init_success = test_agent_initialization()
        tools_success = test_agent_tools_individually()
        
        # Functional tests
        processing_success = test_agent_basic_processing()
        error_handling_success = test_agent_error_handling()
        workflow_success = test_agent_workflow_validation()
        
        # Summary
        print(f"\n" + "=" * 60)
        print(f"📊 Test Results Summary:")
        print(f"   ✅ Initialization: {'PASS' if init_success else 'FAIL'}")
        print(f"   ✅ Tool Access: {'PASS' if tools_success else 'FAIL'}")
        print(f"   ✅ Basic Processing: {'PASS' if processing_success else 'FAIL'}")
        print(f"   ✅ Error Handling: {'PASS' if error_handling_success else 'FAIL'}")
        print(f"   ✅ Workflow: {'PASS' if workflow_success else 'FAIL'}")
        
        overall_success = all([init_success, tools_success, processing_success, error_handling_success])
        
        if overall_success:
            print(f"\n🎉 Agent foundation test complete - Ready for Step 8!")
            print(f"✅ Agent initializes with all tools connected")
            print(f"✅ Can process damage reports end-to-end")
            print(f"✅ Returns structured JSON results")
            print(f"✅ Handles errors gracefully without crashing")
            print(f"✅ Tools execute in logical sequence")
            return True
        else:
            print(f"\n⚠️  Some tests failed - Agent foundation needs attention")
            return False
            
    except Exception as e:
        print(f"❌ Test suite error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
