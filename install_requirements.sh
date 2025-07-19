#!/bin/bash

# Install requirements for Class Schedule Generator
echo "Installing Python packages for Class Schedule Generator..."

# Try different Python/pip combinations
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3.7 or higher."
    exit 1
fi

echo "Using Python command: $PYTHON_CMD"

# Install packages individually to avoid dependency issues
echo "Installing Flask..."
$PYTHON_CMD -m pip install Flask==2.3.3 --user

echo "Installing pandas..."
$PYTHON_CMD -m pip install pandas==2.1.3 --user

echo "Installing WeasyPrint..."
$PYTHON_CMD -m pip install WeasyPrint==60.2 --user

echo "All packages installed successfully!"
echo ""
echo "To run the application:"
echo "1. $PYTHON_CMD app.py"
echo "2. Open browser to: http://127.0.0.1:5000"