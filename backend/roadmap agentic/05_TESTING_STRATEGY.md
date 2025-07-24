# 🧪 Testing Strategy: Validation & Quality Assurance

## 📋 **Testing Phases Overview**

### **Phase 1: Unit Testing (Days 1-2)**
Test individual components in isolation:
- Bucket manager functionality
- Individual agent tools
- Manufacturer ID mapping
- Vehicle identification logic

### **Phase 2: Integration Testing (Days 3-4)**
Test component interactions:
- Agent tool coordination
- Pipeline integration
- Error handling
- Fallback mechanisms

### **Phase 3: End-to-End Testing (Days 5-7)**
Test complete workflow:
- Real damage reports processing
- Parts accuracy validation
- Performance benchmarking
- Edge case handling

## 🛠️ **Unit Testing Framework**

### **Setup Testing Environment**
```bash
cd /Users/yaminchoudhury/Documents/AutoDamageConnect/DamageReportMVP/backend

# Install testing dependencies
pip install pytest pytest-asyncio pytest-mock

# Create test directory structure
mkdir -p tests/{unit,integration,e2e}
mkdir -p tests/fixtures/{damage_reports,expected_results}
```

### **Test Configuration**
Create `tests/conftest.py`:
```python
#!/usr/bin/env python3
"""Testing configuration and fixtures."""

import pytest, json, os
from pathlib import Path
from unittest.mock import Mock, patch
from google.cloud import storage

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def mock_bucket_manager():
    """Mock bucket manager for testing without GCP access."""
    with patch('agents.utils.bucket_manager.PartsCatalogBucket') as mock:
        instance = mock.return_value
        
        # Mock manufacturer mapping
        instance.get_manufacturer_id.return_value = "117"  # Vauxhall
        
        # Mock models data
        instance.get_models_for_manufacturer.return_value = [
            {"id": "5624", "name": "Astra", "manufacturerId": "117"}
        ]
        
        # Mock variants data
        instance.get_variants_for_model.return_value = [
            {
                "id": "127445",
                "name": "Astra K 1.6 Turbo (2016-2019)",
                "modelId": "5624",
                "manufacturerId": "117",
                "engine": "1.6L Turbo",
                "years": "2016-2019"
            }
        ]
        
        # Mock parts data
        instance.get_articles_for_category.return_value = [
            {
                "id": "8053250",
                "name": "Front Brake Pad Set",
                "partNo": "VXH025001",
                "manufacturer": "VAUXHALL",
                "manufacturerId": "117",
                "variantId": "127445",
                "categoryId": "100006",
                "productGroupId": "100025",
                "techDetails": {
                    "EAN Numbers:": "1234567890123",
                    "OEM Numbers VAUXHALL:": "13437123"
                }
            }
        ]
        
        yield instance

@pytest.fixture
def sample_damage_report():
    """Sample damage report for testing."""
    return {
        "vehicle_info": {
            "make": "VAUXHALL",
            "model": "Astra",
            "year": 2018,
            "confidence": 0.9
        },
        "damaged_parts": [
            {
                "name": "Front brake pad",
                "damage_type": "worn",
                "severity": "high",
                "repair_method": "replace",
                "description": "Brake pads worn beyond safe limits"
            }
        ]
    }

@pytest.fixture
def expected_parts_result():
    """Expected parts discovery result."""
    return {
        "repair_parts": [
            {
                "catalog_id": "8053250",
                "name": "Front Brake Pad Set",
                "part_number": "VXH025001",
                "ean_number": "1234567890123",
                "oem_numbers": {"VAUXHALL": "13437123"},
                "manufacturer": "VAUXHALL",
                "category": "Brake System",
                "fits_vehicles": ["2018 Vauxhall Astra K 1.6L Turbo"],
                "labour_hours": 1.5,
                "confidence": 0.95
            }
        ],
        "processing_status": "success"
    }
```

### **Unit Tests for Core Components**

Create `tests/unit/test_bucket_manager.py`:
```python
#!/usr/bin/env python3
"""Unit tests for bucket manager."""

import pytest
from unittest.mock import Mock, patch
from agents.utils.bucket_manager import PartsCatalogBucket

class TestPartsCatalogBucket:
    """Test bucket manager functionality."""
    
    def test_manufacturer_id_lookup(self):
        """Test manufacturer name to ID conversion."""
        bucket = PartsCatalogBucket()
        
        assert bucket.get_manufacturer_id("VAUXHALL") == "117"
        assert bucket.get_manufacturer_id("BMW") == "16"
        assert bucket.get_manufacturer_id("UNKNOWN") is None
        
        # Test case insensitive
        assert bucket.get_manufacturer_id("vauxhall") == "117"
        assert bucket.get_manufacturer_id("Vauxhall") == "117"
    
    @patch('google.cloud.storage.Client')
    def test_json_file_loading(self, mock_storage):
        """Test JSON file loading with caching."""
        # Setup mock
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_text.return_value = '{"test": "data"}'
        mock_bucket.blob.return_value = mock_blob
        
        mock_storage.return_value.bucket.return_value = mock_bucket
        
        # Test
        bucket = PartsCatalogBucket()
        result = bucket.load_json_file("test.json")
        
        assert result == {"test": "data"}
        assert "json:test.json" in bucket.cache  # Check caching
    
    def test_models_retrieval(self, mock_bucket_manager):
        """Test models retrieval for manufacturer."""
        bucket = mock_bucket_manager
        models = bucket.get_models_for_manufacturer("117")
        
        assert len(models) == 1
        assert models[0]["name"] == "Astra"
        assert models[0]["manufacturerId"] == "117"
```

Create `tests/unit/test_vehicle_tools.py`:
```python
#!/usr/bin/env python3
"""Unit tests for vehicle identification tools."""

import pytest, json
from unittest.mock import patch
from agents.tools.vehicle_tools import identify_vehicle_from_report, find_matching_variants

class TestVehicleTools:
    """Test vehicle identification tools."""
    
    def test_vehicle_identification(self, mock_bucket_manager):
        """Test vehicle identification from damage report."""
        damage_report = json.dumps([
            {"name": "front_bumper", "damage_type": "cracked"}
        ])
        
        vehicle_info = json.dumps({
            "make": "VAUXHALL",
            "model": "Astra", 
            "year": 2018
        })
        
        with patch('agents.tools.vehicle_tools.bucket_manager', mock_bucket_manager):
            result = identify_vehicle_from_report.func(damage_report, vehicle_info)
        
        assert result["make"] == "VAUXHALL"
        assert result["model"] == "Astra"
        assert result["year"] == 2018
        assert result["manufacturer_id"] == "117"
        assert result["validated"] == True
        assert result["confidence"] > 0.8
    
    def test_variant_matching(self, mock_bucket_manager):
        """Test vehicle variant matching."""
        with patch('agents.tools.vehicle_tools.bucket_manager', mock_bucket_manager):
            variants = find_matching_variants.func("117", "Astra", 2018)
        
        assert len(variants) > 0
        assert variants[0]["name"] == "Astra K 1.6 Turbo (2016-2019)"
        assert variants[0]["manufacturerId"] == "117"
        assert "compatibility_score" in variants[0]
```

## 🔗 **Integration Testing**

### **Agent Integration Tests**
Create `tests/integration/test_parts_agent.py`:
```python
#!/usr/bin/env python3
"""Integration tests for parts discovery agent."""

import pytest
from unittest.mock import patch
from agents.parts_agent import PartsDiscoveryAgent

class TestPartsAgent:
    """Test complete agent functionality."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_processing(self, mock_bucket_manager, 
                                       sample_damage_report, 
                                       expected_parts_result):
        """Test complete damage report processing."""
        with patch('agents.parts_agent.PartsCatalogBucket', return_value=mock_bucket_manager):
            agent = PartsDiscoveryAgent()
            
            result = agent.process_damage_report(
                sample_damage_report["vehicle_info"],
                sample_damage_report["damaged_parts"]
            )
            
            assert result["processing_status"] == "success"
            assert len(result["repair_parts"]) > 0
            
            # Check first part
            first_part = result["repair_parts"][0]
            assert "catalog_id" in first_part
            assert "part_number" in first_part
            assert "ean_number" in first_part
            assert first_part["manufacturer"] == "VAUXHALL"
    
    def test_error_handling(self, mock_bucket_manager):
        """Test agent error handling."""
        # Mock bucket manager to raise exception
        mock_bucket_manager.get_manufacturer_id.side_effect = Exception("Bucket error")
        
        with patch('agents.parts_agent.PartsCatalogBucket', return_value=mock_bucket_manager):
            agent = PartsDiscoveryAgent()
            
            result = agent.process_damage_report(
                {"make": "UNKNOWN", "model": "TEST"},
                [{"name": "test_part"}]
            )
            
            assert result["processing_status"] == "error"
            assert "error" in result
            assert "fallback_info" in result
```

### **Pipeline Integration Tests**
Create `tests/integration/test_pipeline_integration.py`:
```python
#!/usr/bin/env python3
"""Test agent integration with existing pipeline."""

import pytest, json, tempfile
from pathlib import Path
from unittest.mock import patch, Mock

class TestPipelineIntegration:
    """Test agent integration with generate_damage_report_staged.py."""
    
    def test_agent_fallback_mechanism(self):
        """Test that pipeline falls back gracefully if agent fails."""
        # This would test the actual integration code
        # Import your modified generate_damage_report_staged.py
        # and test the Phase 3 modification
        pass
    
    def test_output_format_compatibility(self):
        """Test that agent output is compatible with existing PDF generation."""
        # Test that agent output format matches expected structure
        # for your existing PDF generation system
        pass
```

## 📊 **End-to-End Testing**

### **Real Data Testing**
Create `tests/e2e/test_real_damage_reports.py`:
```python
#!/usr/bin/env python3
"""End-to-end tests with real damage reports."""

import pytest, json
from pathlib import Path
from agents.parts_agent import create_parts_agent

class TestRealDamageReports:
    """Test with actual damage reports from your system."""
    
    @pytest.fixture
    def real_damage_reports(self):
        """Load real damage reports for testing."""
        # Load actual damage reports from your system
        reports_dir = Path("tests/fixtures/damage_reports")
        reports = []
        
        for report_file in reports_dir.glob("*.json"):
            with open(report_file) as f:
                reports.append(json.load(f))
        
        return reports
    
    @pytest.mark.slow
    def test_vauxhall_astra_brake_damage(self):
        """Test specific scenario: Vauxhall Astra brake damage."""
        damage_report = {
            "vehicle_info": {
                "make": "VAUXHALL",
                "model": "Astra",
                "year": 2018,
                "engine": "1.6L Turbo"
            },
            "damaged_parts": [
                {
                    "name": "Front brake pads",
                    "damage_type": "worn",
                    "severity": "high",
                    "repair_method": "replace"
                }
            ]
        }
        
        agent = create_parts_agent()
        result = agent.process_damage_report(
            damage_report["vehicle_info"],
            damage_report["damaged_parts"]
        )
        
        # Validate results
        assert result["processing_status"] == "success"
        assert len(result["repair_parts"]) > 0
        
        # Check for expected brake parts
        part_names = [p["name"].lower() for p in result["repair_parts"]]
        assert any("brake" in name and "pad" in name for name in part_names)
        
        # Validate part data quality
        for part in result["repair_parts"]:
            assert "part_number" in part
            assert "manufacturer" in part
            assert part["manufacturer"] == "VAUXHALL"
    
    @pytest.mark.slow  
    def test_multiple_manufacturers(self):
        """Test parts discovery across different manufacturers."""
        test_cases = [
            {"make": "BMW", "model": "3 Series", "year": 2020},
            {"make": "MERCEDES-BENZ", "model": "C-Class", "year": 2019},
            {"make": "FORD", "model": "Focus", "year": 2018}
        ]
        
        agent = create_parts_agent()
        
        for vehicle in test_cases:
            damage_report = {
                "vehicle_info": vehicle,
                "damaged_parts": [{"name": "Front bumper", "damage_type": "cracked"}]
            }
            
            result = agent.process_damage_report(
                damage_report["vehicle_info"],
                damage_report["damaged_parts"]
            )
            
            # Should handle all major manufacturers
            assert result["processing_status"] in ["success", "partial_success"]
```

## 📈 **Performance Testing**

### **Benchmark Tests**
Create `tests/performance/test_performance.py`:
```python
#!/usr/bin/env python3
"""Performance benchmarking tests."""

import pytest, time
from agents.parts_agent import create_parts_agent

class TestPerformance:
    """Performance and scalability tests."""
    
    @pytest.mark.performance
    def test_processing_time(self):
        """Test that damage report processing completes within time limit."""
        agent = create_parts_agent()
        
        damage_report = {
            "vehicle_info": {"make": "VAUXHALL", "model": "Astra", "year": 2018},
            "damaged_parts": [{"name": "Front brake pads", "damage_type": "worn"}]
        }
        
        start_time = time.time()
        result = agent.process_damage_report(
            damage_report["vehicle_info"],
            damage_report["damaged_parts"]
        )
        processing_time = time.time() - start_time
        
        # Should complete within 30 seconds
        assert processing_time < 30.0
        assert result["processing_status"] == "success"
    
    @pytest.mark.performance
    def test_concurrent_processing(self):
        """Test concurrent damage report processing."""
        import concurrent.futures
        
        agent = create_parts_agent()
        
        # Create multiple test cases
        test_cases = [
            {"make": "VAUXHALL", "model": "Astra", "damage": "brake pads"},
            {"make": "BMW", "model": "3 Series", "damage": "headlight"},
            {"make": "FORD", "model": "Focus", "damage": "bumper"}
        ] * 3  # 9 concurrent requests
        
        def process_single_report(test_case):
            return agent.process_damage_report(
                {"make": test_case["make"], "model": test_case["model"]},
                [{"name": test_case["damage"], "damage_type": "damaged"}]
            )
        
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(process_single_report, test_cases))
        total_time = time.time() - start_time
        
        # All should succeed
        assert all(r["processing_status"] in ["success", "partial_success"] for r in results)
        # Should handle concurrent load efficiently
        assert total_time < 60.0  # Less than 1 minute for 9 concurrent requests
```

## 🎯 **Quality Assurance Metrics**

### **Accuracy Testing**
Create `tests/quality/test_accuracy.py`:
```python
#!/usr/bin/env python3
"""Accuracy and quality validation tests."""

import pytest
from agents.parts_agent import create_parts_agent

class TestAccuracy:
    """Test parts identification accuracy."""
    
    def test_parts_accuracy_score(self):
        """Calculate parts identification accuracy against known results."""
        # Load test cases with manually verified correct parts
        test_cases = [
            {
                "vehicle": {"make": "VAUXHALL", "model": "Astra", "year": 2018},
                "damage": [{"name": "Front brake pads", "damage_type": "worn"}],
                "expected_parts": ["VXH025001", "brake fluid", "copper grease"]
            }
            # Add more test cases
        ]
        
        agent = create_parts_agent()
        correct_identifications = 0
        total_parts = 0
        
        for test_case in test_cases:
            result = agent.process_damage_report(
                test_case["vehicle"],
                test_case["damage"]
            )
            
            if result["processing_status"] == "success":
                identified_parts = [p.get("part_number") for p in result["repair_parts"]]
                
                for expected_part in test_case["expected_parts"]:
                    total_parts += 1
                    if any(expected_part in str(part) for part in identified_parts):
                        correct_identifications += 1
        
        accuracy = correct_identifications / total_parts if total_parts > 0 else 0
        
        # Should achieve >80% accuracy
        assert accuracy > 0.8, f"Accuracy too low: {accuracy:.2%}"
    
    def test_parts_completeness(self):
        """Test that agent finds all necessary parts for common damage scenarios."""
        # Test comprehensive parts discovery
        complex_damage = {
            "vehicle_info": {"make": "VAUXHALL", "model": "Astra", "year": 2018},
            "damaged_parts": [
                {"name": "Front collision", "damage_type": "impact", "severity": "high"}
            ]
        }
        
        agent = create_parts_agent()
        result = agent.process_damage_report(
            complex_damage["vehicle_info"],
            complex_damage["damaged_parts"]
        )
        
        # Should identify multiple related parts for front collision
        assert len(result["repair_parts"]) >= 3
        
        # Should include various categories
        categories = {p.get("category") for p in result["repair_parts"]}
        expected_categories = {"Body Parts", "Lighting", "Brake System"}
        assert len(categories & expected_categories) >= 2
```

## 🚀 **Testing Automation**

### **Continuous Testing Setup**
Create `.github/workflows/test.yml`:
```yaml
name: Agentic AI Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-mock
    
    - name: Run unit tests
      run: pytest tests/unit/ -v
    
    - name: Run integration tests
      run: pytest tests/integration/ -v
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    
    - name: Run performance tests
      run: pytest tests/performance/ -v -m performance
      if: github.ref == 'refs/heads/main'
```

### **Testing Commands**
```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v              # Unit tests only
pytest tests/integration/ -v       # Integration tests only
pytest tests/e2e/ -v -m slow      # End-to-end tests (slow)
pytest tests/performance/ -v -m performance  # Performance tests

# Run with coverage
pytest tests/ --cov=agents --cov-report=html

# Test specific functionality
pytest tests/unit/test_vehicle_tools.py::TestVehicleTools::test_vehicle_identification -v
```

This comprehensive testing strategy ensures your agentic AI system is reliable, accurate, and performant before deployment.
