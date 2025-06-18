from typing import Dict, Type, List, Union, Optional
from .aip_base import AIPParser
from .aip_base import DEFAULT_AUTHORITY
from .aip_dual import DualFormatAIPParser
import pandas as pd
from tabulate import tabulate

class AIPParserFactory:
    """Factory for creating AIP parsers based on authority code."""
    
    _html_parsers: Dict[str, Type[AIPParser]] = {}
    _pdf_parsers: Dict[str, Type[AIPParser]] = {}
    
    @classmethod
    def register_html_parser(cls, authority: str, parser_class: Type[AIPParser]) -> None:
        """
        Register an HTML parser for a specific authority.
        
        Args:
            authority: Authority code (e.g., 'EGC', 'LFC')
            parser_class: HTML parser class to register
        """
        cls._html_parsers[authority] = parser_class
    
    @classmethod
    def register_pdf_parser(cls, authority: str, parser_class: Type[AIPParser]) -> None:
        """
        Register a PDF parser for a specific authority.
        
        Args:
            authority: Authority code (e.g., 'EGC', 'LFC')
            parser_class: PDF parser class to register
        """
        cls._pdf_parsers[authority] = parser_class
    
    @classmethod
    def get_parser(cls, authority: str, parser_type: str = 'auto') -> AIPParser:
        """
        Get a parser for a specific authority.
        
        Args:
            authority: Authority code
            parser_type: Type of parser to get ('html', 'pdf', 'dual', 'auto')
                        'auto' will return the best available parser
            
        Returns:
            AIPParser instance
            
        Raises:
            ValueError: If no parser is registered for the authority
        """
        if parser_type == 'html':
            parser = cls._get_html_parser(authority)
            if parser is None:
                raise ValueError(f"No HTML parser registered for authority: {authority}")
            return parser
        elif parser_type == 'pdf':
            parser = cls._get_pdf_parser(authority)
            if parser is None:
                raise ValueError(f"No PDF parser registered for authority: {authority}")
            return parser
        elif parser_type == 'dual':
            return cls._get_dual_parser(authority)
        elif parser_type == 'auto':
            return cls._get_auto_parser(authority)
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")
    
    @classmethod
    def _get_html_parser(cls, authority: str) -> Optional[AIPParser]:
        """Get HTML parser for authority."""
        parser_class = cls._html_parsers.get(authority)
        if parser_class is None:
            return None
        return parser_class()
    
    @classmethod
    def _get_pdf_parser(cls, authority: str) -> Optional[AIPParser]:
        """Get PDF parser for authority."""
        parser_class = cls._pdf_parsers.get(authority)
        if parser_class is None:
            # Fall back to default authority if no specific PDF parser
            parser_class = cls._pdf_parsers.get(DEFAULT_AUTHORITY)
            if parser_class is None:
                return None
        return parser_class()
    
    @classmethod
    def _get_dual_parser(cls, authority: str) -> DualFormatAIPParser:
        """Get dual parser for authority."""
        html_parser = cls._html_parsers.get(authority)
        pdf_parser = cls._pdf_parsers.get(authority)
        
        if html_parser is None and pdf_parser is None:
            raise ValueError(f"No HTML or PDF parser registered for authority: {authority}")
        
        return DualFormatAIPParser(authority, html_parser, pdf_parser)
    
    @classmethod
    def _get_auto_parser(cls, authority: str) -> AIPParser:
        """Get the best available parser for authority."""
        # Try to get HTML and PDF parsers (including fallbacks)
        html_parser = cls._get_html_parser(authority)
        pdf_parser = cls._get_pdf_parser(authority)
        
        # If both HTML and PDF parsers are available, use dual parser
        if html_parser is not None and pdf_parser is not None:
            return DualFormatAIPParser(authority, html_parser, pdf_parser)
        # If only HTML parser is available, use it
        elif html_parser is not None:
            return html_parser
        # If only PDF parser is available, use it
        elif pdf_parser is not None:
            return pdf_parser
        # No parser available
        else:
            raise ValueError(f"No parser registered for authority: {authority} and no default parser available")
    
    @classmethod
    def get_supported_authorities(cls) -> List[str]:
        """
        Get list of supported authority codes.
        
        Returns:
            List of supported authority codes
        """
        all_authorities = set()
        all_authorities.update(cls._html_parsers.keys())
        all_authorities.update(cls._pdf_parsers.keys())
        return list(all_authorities)
    
    @classmethod
    def get_parser_info(cls, authority: str) -> Dict[str, bool]:
        """
        Get information about available parsers for an authority.
        
        Args:
            authority: Authority code
            
        Returns:
            Dictionary with parser availability information
        """
        return {
            'html': authority in cls._html_parsers,
            'pdf': authority in cls._pdf_parsers,
            'dual': authority in cls._html_parsers and authority in cls._pdf_parsers
        }
        
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
            if 'alt_field' in df.columns:
                columns.extend(['alt_field'])
            if 'alt_value' in df.columns:
                columns.extend(['alt_value'])
            
        # Filter out rows where alt values are empty or None if not showing alt
        if not show_alt:
            if 'alt_field' in df.columns:
                df = df[df['alt_field'].isna() | (df['alt_field'] == '')]
            if 'alt_value' in df.columns:
                df = df[df['alt_value'].isna() | (df['alt_value'] == '')]
            
        # Select and reorder columns
        df = df[columns]
        
        # Print table
        print(tabulate(df, headers='keys', tablefmt='grid', showindex=False)) 