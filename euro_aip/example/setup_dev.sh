#!/bin/bash

# Create a virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install euro_aip in development mode (from parent directory)
pip install -e ../euro_aip

# Install development dependencies
pip install -e "../euro_aip[dev]" 