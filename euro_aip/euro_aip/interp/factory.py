"""
Factory for creating interpreters.
"""

from typing import Dict, Type, List
from .base import BaseInterpreter
from .interp_custom import CustomInterpreter
from .interp_maintenance import MaintenanceInterpreter
from euro_aip.models.euro_aip_model import EuroAipModel

class InterpreterFactory:
    """Factory for creating interpreters."""
    
    # Registry of available interpreters
    _interpreters: Dict[str, Type[BaseInterpreter]] = {
        'custom': CustomInterpreter,
        'maintenance': MaintenanceInterpreter,
    }
    
    @classmethod
    def get_available_interpreters(cls) -> List[str]:
        """
        Get list of available interpreter types.
        
        Returns:
            List of interpreter names
        """
        return list(cls._interpreters.keys())
    
    @classmethod
    def create_interpreter(cls, interpreter_type: str, model: EuroAipModel) -> BaseInterpreter:
        """
        Create an interpreter of the specified type.
        
        Args:
            interpreter_type: Type of interpreter to create
            model: EuroAIP model to use
            
        Returns:
            Interpreter instance
            
        Raises:
            ValueError: If interpreter type is not supported
        """
        if interpreter_type not in cls._interpreters:
            available = ', '.join(cls.get_available_interpreters())
            raise ValueError(f"Unknown interpreter type '{interpreter_type}'. Available: {available}")
        
        interpreter_class = cls._interpreters[interpreter_type]
        return interpreter_class(model)
    
    @classmethod
    def register_interpreter(cls, name: str, interpreter_class: Type[BaseInterpreter]):
        """
        Register a new interpreter type.
        
        Args:
            name: Name for the interpreter
            interpreter_class: Interpreter class to register
        """
        cls._interpreters[name] = interpreter_class 