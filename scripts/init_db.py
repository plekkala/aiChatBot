#!/usr/bin/env python
"""
Run this once to initialise the database:
  python scripts/init_db.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.models import init_db

if __name__ == "__main__":
    print("Initialising database and running migrations...")
    init_db()
    print("Done.")
