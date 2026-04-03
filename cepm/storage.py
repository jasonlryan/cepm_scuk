"""
Firestore storage layer for CEPM.

Manages the Firestore client and provides CRUD operations
for analysis results and other CEPM data.
"""

import logging
from datetime import datetime, timezone
from google.cloud import firestore

logger = logging.getLogger(__name__)

# Module-level Firestore client (initialized once)
_db = None


def get_db():
    """Get or initialize the Firestore client."""
    global _db
    if _db is None:
        try:
            _db = firestore.Client()
            logger.info("Firestore client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Firestore: {e}")
    return _db


# --- Analysis Results ---

ANALYSIS_COLLECTION = 'analysis_results'


def store_analysis(analysis_id, data):
    """Store an analysis result in Firestore."""
    db = get_db()
    if not db:
        return False
    try:
        doc_ref = db.collection(ANALYSIS_COLLECTION).document(analysis_id)
        doc_data = {**data, 'created_at': datetime.now(timezone.utc).isoformat()}
        doc_ref.set(doc_data)
        return True
    except Exception as e:
        logger.error(f"Error storing analysis: {e}")
        return False


def get_analysis(analysis_id):
    """Retrieve a single analysis result."""
    db = get_db()
    if not db:
        return None
    try:
        doc = db.collection(ANALYSIS_COLLECTION).document(analysis_id).get()
        if doc.exists:
            result = doc.to_dict()
            result['id'] = doc.id
            return result
        return None
    except Exception as e:
        logger.error(f"Error getting analysis: {e}")
        return None


def list_analyses(limit=20, persona_filter=None, asset_type_filter=None):
    """List analysis results with optional filters."""
    db = get_db()
    if not db:
        return []
    try:
        query = db.collection(ANALYSIS_COLLECTION)
        if persona_filter:
            query = query.where('target_persona', '==', persona_filter)
        if asset_type_filter:
            query = query.where('asset_type', '==', asset_type_filter)
        query = query.order_by('created_at', direction=firestore.Query.DESCENDING)
        query = query.limit(limit)

        results = []
        for doc in query.stream():
            item = doc.to_dict()
            item['id'] = doc.id
            results.append(item)
        return results
    except Exception as e:
        logger.error(f"Error listing analyses: {e}")
        return []


def delete_analysis(analysis_id):
    """Delete an analysis result."""
    db = get_db()
    if not db:
        return False
    try:
        db.collection(ANALYSIS_COLLECTION).document(analysis_id).delete()
        return True
    except Exception as e:
        logger.error(f"Error deleting analysis: {e}")
        return False


# --- Persona Storage ---

PERSONAS_COLLECTION = 'personas'


def store_persona(persona_id, data):
    """Store a persona definition in Firestore."""
    db = get_db()
    if not db:
        return False
    try:
        doc_ref = db.collection(PERSONAS_COLLECTION).document(persona_id)
        doc_ref.set(data)
        return True
    except Exception as e:
        logger.error(f"Error storing persona: {e}")
        return False


def get_persona(persona_id):
    """Retrieve a persona definition."""
    db = get_db()
    if not db:
        return None
    try:
        doc = db.collection(PERSONAS_COLLECTION).document(persona_id).get()
        if doc.exists:
            result = doc.to_dict()
            result['id'] = doc.id
            return result
        return None
    except Exception as e:
        logger.error(f"Error getting persona: {e}")
        return None


def list_personas():
    """List all persona definitions."""
    db = get_db()
    if not db:
        return []
    try:
        results = []
        for doc in db.collection(PERSONAS_COLLECTION).stream():
            item = doc.to_dict()
            item['id'] = doc.id
            results.append(item)
        return results
    except Exception as e:
        logger.error(f"Error listing personas: {e}")
        return []


def delete_persona(persona_id):
    """Delete a persona definition."""
    db = get_db()
    if not db:
        return False
    try:
        db.collection(PERSONAS_COLLECTION).document(persona_id).delete()
        return True
    except Exception as e:
        logger.error(f"Error deleting persona: {e}")
        return False
