#!/bin/bash
# openlens Setup Script
# Automates the virtual environment setup process

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║              openlens - Virtual Environment Setup                ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed or not in PATH"
    echo "   Please install Python 3.6 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✓ Found Python $PYTHON_VERSION"
echo ""

# Check if venv already exists
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment 'venv' already exists"
    read -p "   Remove and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "   Removing existing venv..."
        rm -rf venv
    else
        echo "   Keeping existing venv"
        echo ""
        echo "To activate the existing venv, run:"
        echo "   source venv/bin/activate"
        exit 0
    fi
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

if [ ! -d "venv" ]; then
    echo "❌ Error: Failed to create virtual environment"
    exit 1
fi

echo "✓ Virtual environment created"
echo ""

# Activate and verify
echo "🔍 Installing dependencies..."
source venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies from requirements.txt
if [ -f "requirements.txt" ]; then
    echo "⬇️  Installing from requirements.txt..."
    pip install -r requirements.txt
    echo "✓ Dependencies installed"
else
    echo "⚠️  requirements.txt not found, skipping dependency installation"
fi

echo ""
echo "🔍 Verifying installation..."
VENV_PYTHON=$(which python)
echo "✓ Virtual environment Python: $VENV_PYTHON"

# Check PySide6 (Primary GUI)
if python -c "import PySide6" 2>/dev/null; then
    echo "✓ PySide6 is available (Primary GUI will work)"
else
    echo "⚠️  PySide6 is not available"
fi

# Check scientific stack
if python -c "import numpy, matplotlib" 2>/dev/null; then
    echo "✓ numpy and matplotlib are available"
else
    echo "⚠️  Scientific stack (numpy/matplotlib) missing"
fi

# Check optional advanced features
if python -c "import scipy, PIL" 2>/dev/null; then
    echo "✓ scipy and Pillow are available (Advanced features enabled)"
else
    echo "ℹ️  scipy or Pillow missing (Advanced features will be disabled)"
fi

deactivate

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To activate the virtual environment:"
echo "  $ source venv/bin/activate"
echo ""
echo "To run the application:"
echo "  $ python openlens.py           # GUI version"
echo "  $ python -m src.lens_editor    # CLI version"
echo ""
echo "To run tests:"
echo "  $ python tests/run_all_tests.py"
echo ""
echo "To deactivate when done:"
echo "  $ deactivate"
echo ""
