#!/usr/bin/env python3

"""
Example script to create a sample Excel file for testing the approach pack functionality.
"""

import pandas as pd
import numpy as np

def create_example_excel():
    """Create an example Excel file for approach pack testing."""
    
    # Create navdata sheet
    navdata = pd.DataFrame({
        'Name': ['LFPO', 'RWY09', 'RWY27', 'FINAL09', 'FINAL27', 'MAP09', 'MAP27'],
        'Latitude': [48.7233, 48.7233, 48.7233, 48.7233, 48.7233, 48.7233, 48.7233],
        'Longitude': [2.3794, 2.3794, 2.3794, 2.3794, 2.3794, 2.3794, 2.3794],
        'Reference': ['', 'LFPO', 'LFPO', 'RWY09', 'RWY27', 'FINAL09', 'FINAL27'],
        'Bearing': [0, 90, 270, 90, 270, 90, 270],
        'Distance': [0, 0.5, 0.5, 5, 5, 0.5, 0.5],
        'Include': [1, 1, 1, 1, 1, 1, 1],
        'Description': [
            'Paris Orly Airport',
            'Runway 09 threshold',
            'Runway 27 threshold', 
            'Final approach fix for RWY 09',
            'Final approach fix for RWY 27',
            'Missed approach point for RWY 09',
            'Missed approach point for RWY 27'
        ]
    })
    
    # Create byop sheet (Build Your Own Procedure)
    byop = pd.DataFrame({
        'Procedure': ['ILS09', 'ILS27'],
        'Type': ['approach', 'approach'],
        'Runway': ['09', '27'],
        'Description': ['ILS approach to runway 09', 'ILS approach to runway 27']
    })
    
    # Save to Excel
    with pd.ExcelWriter('example_approach.xlsx') as writer:
        navdata.to_excel(writer, sheet_name='navdata', index=False)
        byop.to_excel(writer, sheet_name='byop', index=False)
    
    print("Created example_approach.xlsx")
    print("\nNavdata sheet contains:")
    print(navdata)
    print("\nByop sheet contains:")
    print(byop)
    print("\nTo test the approach pack functionality:")
    print("python example/foreflight.py example_approach -c approach")

if __name__ == '__main__':
    create_example_excel() 