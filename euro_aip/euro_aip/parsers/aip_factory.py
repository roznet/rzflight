from typing import Dict, Type, List
from .aip_base import AIPParser
import pandas as pd
from tabulate import tabulate

# Constants for authority codes
DEFAULT_AUTHORITY = 'DEFAULT'

class AIPParserFactory:
    """Factory for creating AIP parsers based on authority code."""
    
    _parsers: Dict[str, Type[AIPParser]] = {}
    
    @classmethod
    def register_parser(cls, authority: str, parser_class: Type[AIPParser]) -> None:
        """
        Register a parser for a specific authority.
        
        Args:
            authority: Authority code (e.g., 'LEC', 'LIC')
            parser_class: Parser class to register
        """
        cls._parsers[authority] = parser_class
    
    @classmethod
    def get_parser(cls, authority: str) -> AIPParser:
        """
        Get a parser for a specific authority.
        
        Args:
            authority: Authority code
            
        Returns:
            AIPParser instance
            
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
        
    @staticmethod
    def pretty_print_results(results: List[Dict[str, str]], show_alt: bool = True) -> None:
        """
        Pretty print parsing results in a table format.
        
        Args:
            results: List of dictionaries containing parsed data
            show_alt: Whether to show alt_field and alt_value columns
        """
        if not results:
            print("No results to display")
            return
            
        # Convert to DataFrame
        df = pd.DataFrame(results)
        
        # Select columns to display
        columns = ['ident', 'section', 'field', 'value']
        if show_alt:
            columns.extend(['alt_field', 'alt_value'])
            
        # Filter out rows where alt values are empty or None if not showing alt
        if not show_alt:
            df = df[df['alt_field'].isna() | (df['alt_field'] == '')]
            df = df[df['alt_value'].isna() | (df['alt_value'] == '')]
            
        # Select and reorder columns
        df = df[columns]
        
        # Print table
        print(tabulate(df, headers='keys', tablefmt='grid', showindex=False)) 