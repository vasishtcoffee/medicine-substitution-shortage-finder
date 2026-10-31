"""MongoDB access + idempotent collection setup (validation + indexes). MongoDB is NOT a source of truth."""
from pymongo import ASCENDING, MongoClient

from . import config

INVENTORY_FEED = "inventory_feed"
FEED_EVENTS = "feed_events"
SOURCES = ["sale", "receipt", "adjustment", "import"]

_client = None


def get_db():
    """Return the MongoDB database. Tests monkeypatch this function (e.g. with mongomock or a failing stub)."""
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=2000, tz_aware=True)
    return _client[config.MONGO_DATABASE]


_INT = ["int", "long"]

FEED_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["_id", "pharmacy_id", "medicine_id", "quantity", "reorder_level", "availability", "last_updated", "source"],
    "properties": {
        "_id": {"bsonType": "string", "pattern": "^ph[0-9]+:med[0-9]+$"},
        "pharmacy_id": {"bsonType": _INT, "minimum": 1},
        "medicine_id": {"bsonType": _INT, "minimum": 1},
        "quantity": {"bsonType": _INT, "minimum": 0},
        "reorder_level": {"bsonType": _INT, "minimum": 0},
        "availability": {"enum": ["In stock", "Low", "Out"]},
        "low_stock": {"bsonType": "bool"},
        "last_updated": {"bsonType": "date"},
        "source": {"bsonType": "string"},
        "metadata": {"bsonType": "object"},
        "notes": {"bsonType": "string"},
        "flags": {"bsonType": "array", "items": {"bsonType": "string"}},
    }}}

EVENT_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["_id", "source", "occurred_at", "payload"],
    "properties": {
        "_id": {"bsonType": "string"},
        "source": {"enum": SOURCES},
        "pharmacy_id": {"bsonType": _INT},
        "medicine_id": {"bsonType": _INT},
        "occurred_at": {"bsonType": "date"},
        "payload": {"bsonType": "object"},
        "notes": {"bsonType": "string"},
        "flags": {"bsonType": "array", "items": {"bsonType": "string"}},
    }}}


def ensure_collections(db) -> dict:
    """Create (or update) collections with $jsonSchema validation and indexes. Safe to run repeatedly."""
    existing = set(db.list_collection_names())
    done = {}
    for name, validator in ((INVENTORY_FEED, FEED_VALIDATOR), (FEED_EVENTS, EVENT_VALIDATOR)):
        if name not in existing:
            db.create_collection(name, validator=validator, validationLevel="strict", validationAction="error")
            done[name] = "created"
        else:
            db.command("collMod", name, validator=validator, validationLevel="strict", validationAction="error")
            done[name] = "validator updated"
    db[INVENTORY_FEED].create_index([("pharmacy_id", ASCENDING)], name="ix_feed_pharmacy")
    db[INVENTORY_FEED].create_index([("medicine_id", ASCENDING)], name="ix_feed_medicine")
    db[INVENTORY_FEED].create_index([("last_updated", ASCENDING)], name="ix_feed_last_updated")
    db[FEED_EVENTS].create_index([("source", ASCENDING)], name="ix_events_source")
    db[FEED_EVENTS].create_index([("occurred_at", ASCENDING)], name="ix_events_occurred")
    db[FEED_EVENTS].create_index([("pharmacy_id", ASCENDING), ("medicine_id", ASCENDING)], name="ix_events_ph_med")
    return done
