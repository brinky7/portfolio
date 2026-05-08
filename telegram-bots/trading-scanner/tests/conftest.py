"""
Pytest configuration and fixtures for scanner tests.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import core modules
scanner_root = Path(__file__).parent.parent
sys.path.insert(0, str(scanner_root))
