#!/usr/bin/env python3
"""
Class Schedule Generator
Easy-to-run script for Windows users

Usage: python run.py
Then open browser to: http://127.0.0.1:5000
"""

import sys
import os
import subprocess

def install_requirements():
    """Install required packages"""
    print("Installing required packages...")
    try:
        # Install packages individually with --user flag for better compatibility
        packages = ['Flask==2.3.3', 'pandas==2.1.3', 'WeasyPrint==60.2']
        
        for package in packages:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package, '--user'])
        
        print("✓ All packages installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error installing packages: {e}")
        print("You may need to install packages manually:")
        print("pip install Flask pandas WeasyPrint")
        return False

def main():
    print("=" * 50)
    print("   CLASS SCHEDULE GENERATOR")
    print("=" * 50)
    print()
    
    # Check if requirements.txt exists
    if not os.path.exists('requirements.txt'):
        print("✗ requirements.txt not found!")
        return
    
    # Install requirements
    if not install_requirements():
        print("\nPress Enter to exit...")
        input()
        return
    
    print("\n" + "=" * 50)
    print("Starting Flask application...")
    print("Open your browser to: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    print()
    
    # Import and run the Flask app
    try:
        from app import app
        app.run(debug=False, host='127.0.0.1', port=5000)
    except KeyboardInterrupt:
        print("\n\nServer stopped by user.")
    except Exception as e:
        print(f"\n✗ Error starting application: {e}")
        print("\nPress Enter to exit...")
        input()

if __name__ == '__main__':
    main()