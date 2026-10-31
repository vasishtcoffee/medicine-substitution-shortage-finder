"""Idempotent MongoDB setup: collections with $jsonSchema validation and indexes. Re-running changes nothing.

Usage: python scripts/init_mongo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import mongo  # noqa: E402

if __name__ == "__main__":
    db = mongo.get_db()
    print(mongo.ensure_collections(db))
    for c in (mongo.INVENTORY_FEED, mongo.FEED_EVENTS):
        print(c, "indexes:", sorted(db[c].index_information().keys()))
