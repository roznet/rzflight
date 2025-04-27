import re
import pandas as pd
import camelot
from io import StringIO, BytesIO
from typing import List, Dict, Any
from .base import AIPParser

class LECAIPParser(AIPParser):
    """Parser for LEC (France) AIP format."""
    
    def get_supported_authorities(self) -> List[str]:
        """Get list of supported authority codes."""
        return ['LEC']
    
    def parse(self, pdf_data: bytes, icao: str) -> List[Dict[str, Any]]:
        """
        Parse LEC AIP document data.
        
        Args:
            pdf_data: Raw PDF data
            icao: ICAO airport code
            
        Returns:
            List of dictionaries containing parsed data
        """
        # Convert PDF to text (this would be implemented using a PDF library)
        text = self._pdf_to_text(pdf_data)
        
        # Parse the text into sections
        chunks = self._parse_sections(text)
        
        # Process each section
        rv = []
        for (index, section) in zip(['2', '3', '4', '5'], ['admin', 'operational', 'handling', 'passenger']):
            if index not in chunks:
                continue
                
            df = chunks[index]
            for line in df.itertuples():
                (c1, c2) = (line[1], line[-1])
                processed = False
                remarks = False
                data = None
                
                if isinstance(c1, str):
                    res1 = re.match(r'^([\w\s]+):\s(.+)', c1)
                    if res1:
                        (field, value) = res1.groups()
                        data = {
                            'ident': icao,
                            'section': section,
                            'field': field,
                            'alt_field': field,
                            'value': value,
                            'alt_value': value
                        }
                        processed = True
                        
                if data and isinstance(c2, str):
                    res2 = re.match(r'^([\w\s]+):\s(.+)', c2)
                    if res2:
                        (alt_field, alt_value) = res2.groups()
                        if alt_field.lower().startswith('remarks'):
                            remarks = True
                        data['alt_field'] = alt_field
                        data['alt_value'] = alt_value
                
                if processed and not remarks:
                    rv.append(data)
        
        return rv
    
    def _pdf_to_text(self, pdf_data: bytes) -> tuple[list[str], list[str]]:
        """
        Convert PDF data to text, separating Spanish and English columns.
        
        Args:
            pdf_data: Raw PDF data
            
        Returns:
            Tuple of (spanish_texts, english_texts) where each is a list of strings,
            with each string containing all rows from a single table joined by newlines
        """
        # Create a BytesIO object from the PDF data
        pdf_file = BytesIO(pdf_data)
        
        # Extract tables from the PDF
        tables = camelot.read_pdf(pdf_file, pages='all', flavor='stream')
        
        # Initialize lists for Spanish and English text
        spanish_texts = []
        english_texts = []
        
        for i, table in enumerate(tables):
            try:
                print(f"Processing table {i+1}")
                
                # Ensure the table has at least 2 columns
                if len(table.df.columns) >= 2:
                    # Get the first column (Spanish) and second column (English)
                    spanish_col = table.df.iloc[:, 0].values
                    english_col = table.df.iloc[:, 1].values

                    for (spanish, english) in zip(spanish_col, english_col):
                        if 'customs' in english.lower() or 'Fuel' in english:
                            print(f">> {spanish} --- {english}")
                    # Create strings for this table's text
                    spanish_text = '\n'.join([str(text).strip() for text in spanish_col if str(text).strip()])
                    english_text = '\n'.join([str(text).strip() for text in english_col if str(text).strip()])
                    
                    # Add to respective lists
                    spanish_texts.append(spanish_text)
                    english_texts.append(english_text)
            except Exception as e:
                print(f"Error processing table {i+1}: {str(e)}")
                print(f"Table data: {table.df}")
                raise
        
        return spanish_texts, english_texts
    
    def _parse_sections(self, text: str) -> Dict[str, pd.DataFrame]:
        """
        Parse text into sections.
        
        Args:
            text: Text content
            
        Returns:
            Dictionary mapping section numbers to DataFrames
        """
        chunks = {}
        current = []
        section = None
        section_re = re.compile(r' +([0-9]+)\. +[A-Z]+')
        
        for line in text.splitlines():
            m = section_re.match(line)
            if m:
                if section and section in ['2', '3', '4', '5']:
                    if section not in chunks:
                        chunks[section] = pd.read_fwf(StringIO('\n'.join(current)))
                section = m.group(1)
                current = []
            else:
                current.append(line)
        
        return chunks 