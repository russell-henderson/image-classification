#!/usr/bin/env python3
"""
Simple launcher for the Image Classification Desktop App.
"""

import sys
import os

def main():
    """Launch the application."""
    # Add the src directory to the Python path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(script_dir, 'src')
    
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    
    try:
        # Import and run the application
        from main import ImageClassifierApp
        
        print("Starting Image Classification Desktop App...")
        app = ImageClassifierApp()
        app.run()
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Please make sure all dependencies are installed:")
        print("pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"Error starting application: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()
