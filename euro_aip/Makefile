.PHONY: test test-cov clean build install install-dev uninstall

# Run all tests
test:
	pytest -v

# Run tests with coverage report
test-cov:
	pytest --cov=euro_aip --cov-report=term-missing

# Run tests with coverage report and HTML output
test-cov-html:
	pytest --cov=euro_aip --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

# Build the package (creates dist/ directory with wheel and source distribution)
build:
	python -m build
	@echo "Package built successfully! Check dist/ directory for wheel and source distribution."

# Install the package in editable/development mode
install-dev:
	pip install -e .

# Install the package from built wheel (requires build first)
install: build
	pip install dist/euro_aip-*.whl

# Uninstall the package
uninstall:
	pip uninstall -y euro_aip

# Clean up cache, coverage files, and build artifacts
clean:
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete 