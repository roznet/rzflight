"""
Base interpreter class for analyzing structured information from EuroAIP model.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from euro_aip.models.euro_aip_model import EuroAipModel

@dataclass
class InterpretationResult:
    """Result of an interpretation operation."""
    successful: Dict[str, Any]  # Successfully interpreted data
    failed: List[Dict[str, Any]]  # Failed interpretations with reasons
    missing: List[str]  # Airports with missing required data

class BaseInterpreter(ABC):
    """
    Base class for all field interpreters.
    
    This class provides the common interface and functionality for
    interpreting standardized AIP fields into structured information.
    """
    
    def __init__(self, model: EuroAipModel):
        """
        Initialize the interpreter with a EuroAIP model.
        
        Args:
            model: The EuroAIP model containing airport data
        """
        self.model = model
        self.successful = {}
        self.failed = []
        self.missing = []
    
    @abstractmethod
    def interpret_field_value(self, field_value: str, airport: Optional['Airport'] = None) -> Optional[Dict[str, Any]]:
        """
        Interpret a single field value into structured data.
        
        Args:
            field_value: The raw field value to interpret
            airport: Optional airport object for additional context
            
        Returns:
            Dictionary with structured information, or None if interpretation failed
        """
        pass
    
    @abstractmethod
    def get_structured_fields(self) -> List[str]:
        """
        Return list of structured fields this interpreter calculates.
        
        Returns:
            List of field names that this interpreter extracts
        """
        pass
    
    def get_standard_field_id(self) -> int:
        """
        Return the standard field ID this interpreter processes.
        
        Returns:
            Standard field ID (e.g., 302 for custom, 406 for maintenance)
        """
        pass
    
    def get_interpreter_name(self) -> str:
        """
        Return the name of this interpreter.
        
        Returns:
            Interpreter name (e.g., 'custom', 'maintenance')
        """
        return self.__class__.__name__.lower().replace('interpreter', '')
    
 