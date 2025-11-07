# Building and Installing euro_aip Package

This guide explains how to build the `euro_aip` package and install it in other directories for testing.

## Prerequisites

Make sure you have the required build tools installed:

```bash
pip install build wheel setuptools
```

## Building the Package

### Option 1: Using the Makefile (Recommended)

From the `euro_aip` directory, run:

```bash
make build
```

This will create distribution packages in the `dist/` directory.

### Option 2: Using Python build directly

```bash
python -m build
```

This creates both:
- **Source distribution** (`.tar.gz`): `dist/euro_aip-0.1.0.tar.gz`
- **Wheel distribution** (`.whl`): `dist/euro_aip-0.1.0-py3-none-any.whl`

## Installing for Testing

### Method 1: Install from Local Wheel (Best for Testing)

1. Build the package (see above)
2. Navigate to your test directory (where you want to use the library)
3. Install the wheel:

```bash
pip install /path/to/euro_aip/dist/euro_aip-0.1.0-py3-none-any.whl
```

Or if you're in the `euro_aip` directory:

```bash
pip install dist/euro_aip-0.1.0-py3-none-any.whl
```

### Method 2: Install in Editable/Development Mode

This allows you to work on the package and have changes immediately available:

```bash
# From the euro_aip directory
pip install -e .
```

### Method 3: Install from Local Source Distribution

```bash
pip install /path/to/euro_aip/dist/euro_aip-0.1.0.tar.gz
```

## Testing the Installation

### Quick Test

Create a test script in your other directory:

```python
# test_import.py
import euro_aip
from euro_aip import Airport, NavPoint, DatabaseSource, AIPParserFactory

print(f"euro_aip version: {euro_aip.__version__}")
print("✓ All imports successful!")

# Test basic functionality
try:
    navpoint = NavPoint(latitude=48.8566, longitude=2.3522)
    print(f"✓ NavPoint created: {navpoint}")
except Exception as e:
    print(f"✗ NavPoint test failed: {e}")
```

Run it:

```bash
python test_import.py
```

### Comprehensive Test

See `test_installation.py` for a more comprehensive test script.

## Installing in a Virtual Environment (Recommended)

It's best practice to test in a clean virtual environment:

```bash
# Create a virtual environment
python -m venv test_env

# Activate it
# On macOS/Linux:
source test_env/bin/activate
# On Windows:
# test_env\Scripts\activate

# Install the package
pip install /path/to/euro_aip/dist/euro_aip-0.1.0-py3-none-any.whl

# Test it
python test_import.py

# When done, deactivate
deactivate
```

## Verifying Installation

Check that the package is installed correctly:

```bash
pip show euro_aip
pip list | grep euro_aip
```

## Uninstalling

If you need to uninstall:

```bash
pip uninstall euro_aip
```

## Troubleshooting

### Issue: Package not found after installation

- Make sure you're using the same Python interpreter
- Check virtual environment activation
- Verify installation: `pip list | grep euro_aip`

### Issue: Import errors

- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify the package structure is correct

### Issue: Changes not reflected

- If using editable install (`-e`), changes should be immediate
- If using wheel, rebuild and reinstall after changes

## Next Steps

Once you've verified the package works, you can:

1. **Publish to PyPI** (if desired):
   ```bash
   pip install twine
   twine upload dist/*
   ```

2. **Install from a git repository**:
   ```bash
   pip install git+https://github.com/yourusername/rzflight.git#subdirectory=euro_aip
   ```

3. **Use in your other projects**:
   Simply `pip install` the wheel or use one of the installation methods above.

