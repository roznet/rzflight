from typing import List, Dict, Any
from .field_mapper import FieldMapper
from ..models.aip_entry import AIPEntry
import logging

logger = logging.getLogger(__name__)

class FieldStandardizationService:
    """
    Service for standardizing AIP field data using field mapper.
    
    This service provides methods to convert raw AIP field data into
    standardized field data using the field mapper.
    """
    
    def __init__(self, field_mapper: FieldMapper = None):
        """
        Initialize the field standardization service.
        
        Args:
            field_mapper: FieldMapper instance. If None, creates a new one.
        """
        self.field_mapper = field_mapper or FieldMapper()
    
    def standardize_aip_entries(self, entries: List[AIPEntry]) -> List[AIPEntry]:
        """
        Standardize a list of AIP entries by adding standardized field information.
        
        Args:
            entries: List of AIPEntry objects to standardize
            
        Returns:
            List of AIPEntry objects with standardized field information added
        """
        for entry in entries:
            mapping = self.field_mapper.map_field(entry.field, entry.section)
            if mapping['mapped']:
                entry.std_field = mapping['mapped_field_name']
                entry.std_field_id = mapping['mapped_field_id']
                entry.mapping_score = mapping['similarity_score']
                logger.debug(f"Standardized field '{entry.field}' -> '{entry.std_field}' (score: {entry.mapping_score:.2f})")
            else:
                logger.debug(f"No mapping found for field '{entry.field}' in section '{entry.section}'")
        
        return entries
    
    def standardize_field_data(self, field_data: Dict[str, str], source_name: str) -> Dict[str, str]:
        """
        Standardize field data dictionary using field mapper.
        
        Args:
            field_data: Dictionary of field_name -> value
            source_name: Name of the source for logging
            
        Returns:
            Dictionary with standardized field names (original names kept if no mapping found)
        """
        standardized_data = {}
        
        for field_name, value in field_data.items():
            mapping = self.field_mapper.map_field(field_name)
            if mapping['mapped']:
                standardized_data[mapping['mapped_field_name']] = value
                logger.debug(f"[{source_name}] Standardized field '{field_name}' -> '{mapping['mapped_field_name']}' (score: {mapping['similarity_score']:.2f})")
            else:
                # Keep original field name if not mapped
                standardized_data[field_name] = value
                logger.debug(f"[{source_name}] No mapping found for field '{field_name}', keeping original")
        
        return standardized_data
    
    def create_aip_entries_from_parsed_data(self, icao: str, parsed_data: List[Dict[str, Any]]) -> List[AIPEntry]:
        """
        Create AIPEntry objects from parsed data and standardize them.
        
        Args:
            icao: ICAO airport code
            parsed_data: List of parsed data dictionaries with 'field', 'value', 'section' keys
            
        Returns:
            List of standardized AIPEntry objects
        """
        entries = []
        
        for item in parsed_data:
            field_name = item.get('field', '')
            value = item.get('value', '')
            section = item.get('section', '')
            
            if field_name and value:
                entry = AIPEntry(
                    ident=icao,
                    section=section,
                    field=field_name,
                    value=value,
                    alt_field=item.get('alt_field', ''),
                    alt_value=item.get('alt_value', '')
                )
                entries.append(entry)
        
        # Standardize the entries
        return self.standardize_aip_entries(entries)
    
    def get_mapping_statistics(self, entries: List[AIPEntry]) -> Dict[str, Any]:
        """
        Get statistics about field mapping for a list of AIP entries.
        
        Args:
            entries: List of AIPEntry objects
            
        Returns:
            Dictionary with mapping statistics
        """
        total_fields = len(entries)
        mapped_fields = len([e for e in entries if e.std_field is not None])
        unmapped_fields = total_fields - mapped_fields
        
        # Calculate average mapping score
        mapped_entries = [e for e in entries if e.mapping_score is not None]
        avg_score = sum(e.mapping_score for e in mapped_entries) / len(mapped_entries) if mapped_entries else 0.0
        
        # Count by section
        section_counts = {}
        for entry in entries:
            section = entry.section or 'unknown'
            section_counts[section] = section_counts.get(section, 0) + 1
        
        return {
            'total_fields': total_fields,
            'mapped_fields': mapped_fields,
            'unmapped_fields': unmapped_fields,
            'mapping_rate': mapped_fields / total_fields if total_fields > 0 else 0.0,
            'average_mapping_score': avg_score,
            'section_counts': section_counts
        } 