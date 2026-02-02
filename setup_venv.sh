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
echo "🔍 Verifying installation..."
source venv/bin/activate

VENV_PYTHON=$(which python)
echo "✓ Virtual environment Python: $VENV_PYTHON"

# Check tkinter
if python -c "import tkinter" 2>/dev/null; then
    echo "✓ tkinter is available (GUI will work)"
else
    echo "⚠️  tkinter is not available (GUI will not work)"
    echo "   Install with: sudo apt-get install python3-tk (Ubuntu/Debian)"
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
echo "  $ python lens_editor_gui.py    # GUI version"
echo "  $ python lens_editor.py        # CLI version"
echo ""
echo "To run tests:"
echo "  $ python tests/run_all_tests.py"
echo ""
echo "To deactivate when done:"
echo "  $ deactivate"
echo ""
