from typing import Dict, Type, List
from .procedure import ProcedureParser

# Constants for authority codes
DEFAULT_AUTHORITY = 'DEFAULT'

class ProcedureParserFactory:
    """Factory for creating procedure parsers based on authority code."""
    
    _parsers: Dict[str, Type[ProcedureParser]] = {}
    
    @classmethod
    def register_parser(cls, authority: str, parser_class: Type[ProcedureParser]) -> None:
        """
        Register a parser for a specific authority.
        
        Args:
            authority: Authority code (e.g., 'LEC', 'LIC')
            parser_class: Parser class to register
        """
        cls._parsers[authority] = parser_class
    
    @classmethod
    def get_parser(cls, authority: str) -> ProcedureParser:
        """
        Get a parser for a specific authority.
        
        Args:
            authority: Authority code
            
        Returns:
            ProcedureParser instance
            
        Raises:
            ValueError: If no parser is registered for the authority
        """
        parser_class = cls._parsers.get(authority)
        if parser_class is None:
            # If no specific parser is found, use the default parser
            parser_class = cls._parsers.get(DEFAULT_AUTHORITY)
            if parser_class is None:
                raise ValueError(f"No parser registered for authority: {authority} and no default parser available")
        return parser_class()
    
    @classmethod
    def get_supported_authorities(cls) -> List[str]:
        """
        Get list of supported authority codes.
        
        Returns:
            List of supported authority codes
        """
        return list(cls._parsers.keys()) 