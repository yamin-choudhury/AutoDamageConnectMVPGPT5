"""
Agent tools package for vehicle identification and parts discovery
"""

from .vehicle_tools import (
    identify_vehicle_from_report,
    validate_vehicle_in_catalog,
    find_matching_variants,
    vehicle_identification_tools
)

from .catalog_tools import (
    map_components_to_categories,
    load_categories_for_variant,
    catalog_tools
)

__all__ = [
    'identify_vehicle_from_report',
    'validate_vehicle_in_catalog', 
    'find_matching_variants',
    'vehicle_identification_tools',
    'map_components_to_categories',
    'load_categories_for_variant',
    'catalog_tools'
]
