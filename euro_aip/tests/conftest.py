import pytest
from pathlib import Path
import json

@pytest.fixture
def test_assets_dir() -> Path:
    """Return the path to the test assets directory."""
    return Path(__file__).parent / 'assets'

@pytest.fixture
def test_cache_dir(tmp_path) -> Path:
    """Return a temporary directory for cache testing."""
    return tmp_path / 'cache'

@pytest.fixture
def test_pdfs(test_assets_dir) -> dict[str, Path]:
    """Return a dictionary of test PDF files by airport code."""
    pdf_dir = test_assets_dir / 'pdfs'
    return {
        pdf.stem: pdf 
        for pdf in pdf_dir.glob('*.pdf')
    }

@pytest.fixture
def expected_results(test_assets_dir) -> dict[str, dict]:
    """Return expected parsing results for each test PDF."""
    results_file = test_assets_dir / 'expected_results.json'
    if results_file.exists():
        with open(results_file) as f:
            return json.load(f)
    return {} 