.PHONY: test test-cov clean

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

# Clean up cache and coverage files
clean:
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete 