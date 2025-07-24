"""
BucketManager - Handles Google Cloud Storage operations for parts catalog
"""

import os
import json
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
from google.cloud import storage
from dotenv import load_dotenv
from difflib import SequenceMatcher

class BucketManager:
    """
    Manages Google Cloud Storage operations for the parts catalog with caching.
    """
    
    def __init__(self):
        """Initialize the bucket manager with GCS client and cache."""
        # Load environment variables
        load_dotenv(Path(__file__).parent.parent.parent / ".env")
        
        # Initialize GCS client
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.bucket_name = os.getenv("PARTS_CATALOG_BUCKET")
        
        if not self.project_id or not self.bucket_name:
            raise ValueError("Missing required environment variables: GOOGLE_CLOUD_PROJECT, PARTS_CATALOG_BUCKET")
        
        self.client = storage.Client(project=self.project_id)
        self.bucket = self.client.bucket(self.bucket_name)
        
        # Initialize cache (simple in-memory cache with size limit)
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_size_limit = 100
        self.cache_ttl = 3600  # 1 hour TTL
        
        # Load manufacturer mapping
        self.manufacturer_mapping = self._load_manufacturer_mapping()
        
        print(f"✅ BucketManager initialized - Project: {self.project_id}, Bucket: {self.bucket_name}")
    
    def _load_manufacturer_mapping(self) -> Dict[str, str]:
        """Load manufacturer name to ID mapping from JSON file."""
        try:
            mapping_file = Path(__file__).parent.parent / "manufacturer_mapping.json"
            if mapping_file.exists():
                with open(mapping_file, 'r') as f:
                    return json.load(f)
            else:
                print("⚠️  Warning: manufacturer_mapping.json not found")
                return {}
        except Exception as e:
            print(f"⚠️  Warning: Failed to load manufacturer mapping: {e}")
            return {}
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if exists and not expired."""
        if key in self.cache:
            timestamp = self.cache_timestamps.get(key, 0)
            if time.time() - timestamp < self.cache_ttl:
                return self.cache[key]
            else:
                # Remove expired cache entry
                del self.cache[key]
                del self.cache_timestamps[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Set value in cache with size limit."""
        # Clear old entries if cache is full
        if len(self.cache) >= self.cache_size_limit:
            # Remove oldest entry
            oldest_key = min(self.cache_timestamps.keys(), key=lambda k: self.cache_timestamps[k])
            del self.cache[oldest_key]
            del self.cache_timestamps[oldest_key]
        
        self.cache[key] = value
        self.cache_timestamps[key] = time.time()
    
    def _load_json_file(self, file_path: str) -> Optional[Dict]:
        """Load JSON file from Google Cloud Storage."""
        cache_key = f"json_file_{file_path}"
        
        # Check cache first
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            blob = self.bucket.blob(file_path)
            if blob.exists():
                content = blob.download_as_text()
                data = json.loads(content)
                
                # Cache the result
                self._set_cache(cache_key, data)
                return data
            else:
                print(f"⚠️  File not found: {file_path}")
                return None
        except Exception as e:
            print(f"❌ Error loading {file_path}: {e}")
            return None
    
    def get_manufacturer_id(self, manufacturer_name: str) -> Optional[str]:
        """
        Get manufacturer ID from name using fuzzy matching.
        
        Args:
            manufacturer_name: Name of manufacturer (e.g., "Vauxhall", "BMW")
            
        Returns:
            Manufacturer ID string or None if not found
        """
        if not manufacturer_name:
            return None
        
        # Normalize the input name
        normalized_name = manufacturer_name.upper().strip()
        
        # Direct lookup first
        if normalized_name in self.manufacturer_mapping:
            return self.manufacturer_mapping[normalized_name]
        
        # Fuzzy matching if direct lookup fails
        best_match = None
        best_score = 0.0
        
        for mapped_name, manufacturer_id in self.manufacturer_mapping.items():
            score = SequenceMatcher(None, normalized_name, mapped_name).ratio()
            if score > best_score and score > 0.8:  # 80% similarity threshold
                best_match = manufacturer_id
                best_score = score
        
        return best_match
    
    def get_models_for_manufacturer(self, manufacturer_id: str) -> Optional[List[Dict]]:
        """
        Load models for a specific manufacturer.
        
        Args:
            manufacturer_id: Manufacturer ID (e.g., "117")
            
        Returns:
            List of model dictionaries or None if not found
        """
        if not manufacturer_id:
            return None
        
        # Try to load models.json for this manufacturer
        models_file = f"manufacturers/{manufacturer_id}/models.json"
        return self._load_json_file(models_file)
    
    def get_articles_for_category(self, manufacturer_id: str, variant_id: str, category_id: str) -> Optional[List[Dict]]:
        """
        Load articles for a specific manufacturer, variant, and category.
        
        Args:
            manufacturer_id: Manufacturer ID (e.g., "117")
            variant_id: Variant ID (e.g., "12345")
            category_id: Category ID (e.g., "100001")
            
        Returns:
            List of article dictionaries or None if not found
        """
        if not all([manufacturer_id, variant_id, category_id]):
            return None
        
        # Look for articles file with pattern: articles_variant_category_*.json
        # The actual files have a third ID, so we need to search for matching files
        try:
            prefix = f"manufacturers/{manufacturer_id}/articles_{variant_id}_{category_id}_"
            blobs = self.bucket.list_blobs(prefix=prefix)
            
            for blob in blobs:
                if blob.name.endswith('.json'):
                    # Found matching file, load it
                    return self._load_json_file(blob.name)
            
            print(f"⚠️  No articles found for manufacturer {manufacturer_id}, variant {variant_id}, category {category_id}")
            return None
        except Exception as e:
            print(f"❌ Error loading articles: {e}")
            return None
    
    def list_manufacturer_articles(self, manufacturer_id: str) -> List[str]:
        """
        List all article files for a manufacturer.
        
        Args:
            manufacturer_id: Manufacturer ID (e.g., "117")
            
        Returns:
            List of article file names
        """
        if not manufacturer_id:
            return []
        
        try:
            prefix = f"manufacturers/{manufacturer_id}/articles_"
            blobs = self.bucket.list_blobs(prefix=prefix)
            
            article_files = []
            for blob in blobs:
                if blob.name.endswith('.json') and 'articles_' in blob.name:
                    article_files.append(blob.name)
            
            return article_files
        except Exception as e:
            print(f"❌ Error listing articles for manufacturer {manufacturer_id}: {e}")
            return []
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for debugging."""
        return {
            "cache_size": len(self.cache),
            "cache_limit": self.cache_size_limit,
            "cache_ttl": self.cache_ttl,
            "cached_keys": list(self.cache.keys())
        }
