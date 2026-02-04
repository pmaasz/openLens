#!/bin/bash
# Launcher script for OpenLens with proper venv activation

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    # Launch the application
    echo "Launching OpenLens GUI..."
    python3 openlens.py
    
    # Deactivate when done
    deactivate
else
    echo "ERROR: Virtual environment not found!"
    echo "Please run setup_venv.sh first"
    exit 1
fi
