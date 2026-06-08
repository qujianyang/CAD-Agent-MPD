"""Put the repo root on sys.path so tests in this folder can do flat imports
(`from tiedown_engine import ...`) exactly as they did when they lived at root."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
