"""
Module for handling SUPI to IP mapping information.

This module loads the mapping data from the JSON configuration file and provides
functions to access the mappings by SUPI.
"""

import json
import os
from typing import Dict, Any, Optional

# Get the directory where this module is located
module_dir = os.path.dirname(os.path.abspath(__file__))
# Path to the mapping configuration file
config_file_path = os.path.join(module_dir, "supi_to_ip_mapping_info.json")


# Load the mapping data
def _load_mapping_data() -> Dict[str, Any]:
    """Load mapping data from JSON file."""
    try:
        with open(config_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Mapping configuration file not found at {config_file_path}"
        )
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in mapping configuration file: {e}")


# Load the data when the module is imported
_mapping_data = _load_mapping_data()


# Get all mappings
def get_all_mappings() -> list:
    """Return all mappings from the configuration file."""
    return _mapping_data.get("mappings", [])


# Get mapping by SUPI
def get_mapping_by_supi(supi: str) -> Optional[Dict[str, Any]]:
    """
    Get the mapping object for a given SUPI.

    Args:
        supi (str): The SUPI to search for

    Returns:
        dict: The mapping object if found, None otherwise
    """
    mappings = get_all_mappings()
    for mapping in mappings:
        if mapping.get("supi") == supi:
            return mapping
    return None


# Get all available SUPIs
def get_all_supis() -> list:
    """Return list of all SUPIs in the mapping."""
    mappings = get_all_mappings()
    return [mapping["supi"] for mapping in mappings if "supi" in mapping]


# Get mapping data with cache keys
def get_cache_keys() -> list:
    """Return the cache keys defined in the configuration."""
    return _mapping_data.get("cacheKey", [])


# Get cache values
def get_cache_values() -> list:
    """Return the cache values defined in the configuration."""
    return _mapping_data.get("cacheValue", [])


# Get refresh triggers
def get_refresh_triggers() -> list:
    """Return the refresh triggers defined in the configuration."""
    return _mapping_data.get("refreshTriggers", [])
