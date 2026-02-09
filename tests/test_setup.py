"""
Basic test script to verify the Image Classification App components.
Run this to check if the core functionality works.
"""

import sys
import os
import tempfile
import logging
from pathlib import Path

# Add src to path for importing
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

try:
    from core.database import DatabaseManager, ImageMetadata
    from core.image_handler import ImageHandler
    print("✓ Core modules imported successfully")
except ImportError as e:
    print(f"✗ Failed to import core modules: {e}")
    sys.exit(1)

def test_database():
    """Test database functionality."""
    print("\n--- Testing Database ---")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = DatabaseManager(db_path)
        print("✓ Database created successfully")
        
        # Test statistics
        stats = db.get_statistics()
        print(f"✓ Database statistics: {stats}")
        
        return True
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

def test_image_handler():
    """Test image handler functionality."""
    print("\n--- Testing Image Handler ---")
    
    try:
        handler = ImageHandler()
        print("✓ ImageHandler created successfully")
        
        # Test supported formats
        test_formats = ['.jpg', '.png', '.bmp', '.tiff']
        for fmt in test_formats:
            if handler.is_supported_image(f"test{fmt}"):
                print(f"✓ Format {fmt} is supported")
            else:
                print(f"✗ Format {fmt} not supported")
        
        return True
    except Exception as e:
        print(f"✗ ImageHandler test failed: {e}")
        return False

def test_config():
    """Test configuration loading."""
    print("\n--- Testing Configuration ---")
    
    config_path = os.path.join(REPO_ROOT, 'src', 'config', 'settings.json')
    
    if os.path.exists(config_path):
        try:
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
            print("✓ Configuration file loaded successfully")
            print(f"✓ Configuration keys: {list(config.keys())}")
            
            ollama_cfg = config.get('providers', {}).get('ollama', {})
            if ollama_cfg.get('enabled', False):
                print("✓ Ollama provider is enabled")
            else:
                print("! Ollama provider is disabled (enable in settings.json)")
            
            return True
        except Exception as e:
            print(f"✗ Configuration test failed: {e}")
            return False
    else:
        print(f"✗ Configuration file not found: {config_path}")
        return False

def test_dependencies():
    """Test required dependencies."""
    print("\n--- Testing Dependencies ---")
    
    required_modules = [
        ('tkinter', 'GUI framework'),
        ('PIL', 'Image processing'),
        ('json', 'JSON handling'),
        ('sqlite3', 'Database'),
        ('pathlib', 'Path handling'),
        ('logging', 'Logging'),
        ('asyncio', 'Async operations'),
    ]
    
    optional_modules = [
        ('customtkinter', 'Modern GUI (optional)'),
        ('cv2', 'Computer vision (optional)'),
        ('exifread', 'EXIF data (optional)'),
        ('numpy', 'Numerical operations (optional)'),
    ]
    
    all_good = True
    
    print("Required modules:")
    for module_name, description in required_modules:
        try:
            __import__(module_name)
            print(f"✓ {module_name}: {description}")
        except ImportError:
            print(f"✗ {module_name}: {description} - MISSING")
            all_good = False
    
    print("\nOptional modules:")
    for module_name, description in optional_modules:
        try:
            __import__(module_name)
            print(f"✓ {module_name}: {description}")
        except ImportError:
            print(f"! {module_name}: {description} - not installed")
    
    return all_good

def main():
    """Run all tests."""
    print("Image Classification Desktop App - Component Test")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    tests = [
        ("Dependencies", test_dependencies),
        ("Configuration", test_config),
        ("Database", test_database),
        ("Image Handler", test_image_handler),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name:15} : {status}")
        if result:
            passed += 1
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed! The application should work correctly.")
        print("\nTo start the application:")
        print("  Manual:  python src/main.py")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the issues above.")
        print("\nTo install missing dependencies:")
        print("  pip install -r requirements.txt")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
