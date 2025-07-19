"""
Runway surface classification utilities.

This module provides functions to classify runway surfaces into different categories
(hard, soft, water, snow) based on surface type strings.
"""

from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

# Surface classification patterns
SURFACE_PATTERNS = {
    'hard': {
        'exact': ['hard', 'paved', 'pem', 'asfalt', 'tarmac', 'asfalto', 'ashpalt', 'ashphalt', 'surface paved', 'tar'],
        'contains': ['asphalt', 'concrete', 'cement'],
        'startswith': ['asp', 'con', 'apsh', 'bit', 'pav', 'tar']
    },
    'soft': {
        'exact': ['graas', 'soft'],
        'contains': ['turf', 'grass', 'dirt', 'gravel', 'soil', 'sand', 'earth'],
        'startswith': ['turf', 'grv', 'grav', 'grass', 'san', 'cla', 'grs', 'gra', 'gre']
    },
    'water': {
        'startswith': ['wat']
    },
    'snow': {
        'startswith': ['sno']
    }
}

def classify_runway_surface(surface: Optional[str]) -> Optional[str]:
    """
    Classify a runway surface into hard, soft, water, or snow.
    
    Args:
        surface: Surface type string (e.g., 'ASP', 'GRASS', 'WATER')
        
    Returns:
        Classification string ('hard', 'soft', 'water', 'snow') or None if unknown
    """
    if not surface:
        return None
    
    # Normalize the surface string
    surface_lower = surface.lower().strip()
    
    # Check each category
    for category, patterns in SURFACE_PATTERNS.items():
        # Check exact matches
        if 'exact' in patterns and surface_lower in patterns['exact']:
            return category
        
        # Check contains patterns
        if 'contains' in patterns:
            for pattern in patterns['contains']:
                if pattern in surface_lower:
                    return category
        
        # Check startswith patterns
        if 'startswith' in patterns:
            for pattern in patterns['startswith']:
                if surface_lower.startswith(pattern):
                    return category
    
    # If no match found, log for debugging
    logger.debug(f"Unknown runway surface type: '{surface}'")
    return None

def is_hard_surface(surface: Optional[str]) -> bool:
    """
    Check if a runway surface is classified as hard.
    
    Args:
        surface: Surface type string
        
    Returns:
        True if the surface is classified as hard, False otherwise
    """
    return classify_runway_surface(surface) == 'hard'

def is_soft_surface(surface: Optional[str]) -> bool:
    """
    Check if a runway surface is classified as soft.
    
    Args:
        surface: Surface type string
        
    Returns:
        True if the surface is classified as soft, False otherwise
    """
    return classify_runway_surface(surface) == 'soft'

def is_water_surface(surface: Optional[str]) -> bool:
    """
    Check if a runway surface is classified as water.
    
    Args:
        surface: Surface type string
        
    Returns:
        True if the surface is classified as water, False otherwise
    """
    return classify_runway_surface(surface) == 'water'

def is_snow_surface(surface: Optional[str]) -> bool:
    """
    Check if a runway surface is classified as snow.
    
    Args:
        surface: Surface type string
        
    Returns:
        True if the surface is classified as snow, False otherwise
    """
    return classify_runway_surface(surface) == 'snow'

def get_surface_statistics(surfaces: List[Optional[str]]) -> Dict[str, int]:
    """
    Get statistics about surface classifications for a list of surfaces.
    
    Args:
        surfaces: List of surface type strings
        
    Returns:
        Dictionary with counts for each surface category
    """
    stats = {
        'hard': 0,
        'soft': 0,
        'water': 0,
        'snow': 0,
        'unknown': 0,
        'total': len(surfaces)
    }
    
    for surface in surfaces:
        classification = classify_runway_surface(surface)
        if classification:
            stats[classification] += 1
        else:
            stats['unknown'] += 1
    
    return stats 