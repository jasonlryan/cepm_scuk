from flask import Flask, request, jsonify, redirect, url_for, send_from_directory, render_template_string
import os
from flask_cors import CORS
import logging
import sys
import secrets
import markdown
import uuid
from functools import wraps
from datetime import datetime, timedelta, timezone
from google.cloud import firestore

from cepm import personas as persona_service
from cepm import scoring, recommendations, storage as cepm_storage

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize Firestore client
try:
    db = firestore.Client()
    logger.info("Firestore client initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Firestore: {str(e)}")
    db = None

# OAuth configuration
CLIENT_ID = os.environ.get('CLIENT_ID', 'gpt-client')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', 'your-secret-here')

# Token lifetimes
ACCESS_TOKEN_LIFETIME = 30 * 24 * 3600  # 30 days in seconds
AUTH_CODE_LIFETIME = 10 * 60  # 10 minutes in seconds

# Firestore collections
OAUTH_STATES_COLLECTION = 'oauth_states'
AUTH_CODES_COLLECTION = 'auth_codes'
TOKENS_COLLECTION = 'tokens'
REFRESH_TOKENS_COLLECTION = 'refresh_tokens'


# ============================================================
# Auth decorator
# ============================================================

def require_auth(f):
    """Decorator that validates OAuth bearer tokens on protected endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header[7:]  # strip "Bearer "
        token_data = get_token(token)

        if not token_data:
            logger.warning(f"Invalid token used: {token[:10]}...")
            return jsonify({"error": "Invalid token"}), 401

        if isinstance(token_data.get('expires_at'), str):
            token_data['expires_at'] = datetime.fromisoformat(token_data['expires_at'])

        # Handle both naive and aware datetimes
        expires_at = token_data['expires_at']
        if expires_at.tzinfo is None:
            current_time = datetime.utcnow()
        else:
            current_time = datetime.now(timezone.utc)

        if expires_at < current_time:
            logger.warning(f"Expired token used: {token[:10]}...")
            return jsonify({"error": "Token expired"}), 401

        logger.info("Valid OAuth token received")
        request.token_data = token_data
        return f(*args, **kwargs)
    return decorated


# ============================================================
# OAuth storage helpers (existing)
# ============================================================

def store_state(state, data):
    """Store OAuth state in Firestore"""
    if not db:
        return False
    try:
        doc_ref = db.collection(OAUTH_STATES_COLLECTION).document(state)
        doc_ref.set({
            'client_id': data['client_id'],
            'redirect_uri': data['redirect_uri'],
            'created_at': data['created_at']
        })
        return True
    except Exception as e:
        logger.error(f"Error storing state in Firestore: {str(e)}")
        return False

def get_state(state):
    """Get OAuth state from Firestore"""
    if not db:
        return None
    try:
        doc_ref = db.collection(OAUTH_STATES_COLLECTION).document(state)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Error getting state from Firestore: {str(e)}")
        return None

def store_auth_code(code, data):
    """Store authorization code in Firestore"""
    if not db:
        return False
    try:
        firestore_data = data.copy()
        if isinstance(firestore_data['created_at'], datetime):
            firestore_data['created_at'] = firestore_data['created_at'].isoformat()
        if isinstance(firestore_data['expires_at'], datetime):
            firestore_data['expires_at'] = firestore_data['expires_at'].isoformat()
        doc_ref = db.collection(AUTH_CODES_COLLECTION).document(code)
        doc_ref.set(firestore_data)
        return True
    except Exception as e:
        logger.error(f"Error storing auth code in Firestore: {str(e)}")
        return False

def get_auth_code(code):
    """Get authorization code from Firestore"""
    if not db:
        return None
    try:
        doc_ref = db.collection(AUTH_CODES_COLLECTION).document(code)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Error getting auth code from Firestore: {str(e)}")
        return None

def delete_auth_code(code):
    """Delete authorization code from Firestore"""
    if not db:
        return False
    try:
        doc_ref = db.collection(AUTH_CODES_COLLECTION).document(code)
        doc_ref.delete()
        return True
    except Exception as e:
        logger.error(f"Error deleting auth code from Firestore: {str(e)}")
        return False

def store_token(token_type, token, data):
    """Store token in Firestore"""
    if not db:
        return False
    try:
        firestore_data = data.copy()
        if isinstance(firestore_data.get('created_at'), datetime):
            firestore_data['created_at'] = firestore_data['created_at'].isoformat()
        if 'expires_at' in firestore_data and isinstance(firestore_data.get('expires_at'), datetime):
            firestore_data['expires_at'] = firestore_data['expires_at'].isoformat()
        collection = TOKENS_COLLECTION if token_type == 'access' else REFRESH_TOKENS_COLLECTION
        doc_ref = db.collection(collection).document(token)
        doc_ref.set(firestore_data)
        return True
    except Exception as e:
        logger.error(f"Error storing token in Firestore: {str(e)}")
        return False

def get_token(token):
    """Get access token from Firestore"""
    if not db:
        return None
    try:
        doc_ref = db.collection(TOKENS_COLLECTION).document(token)
        doc = doc_ref.get()
        if doc.exists:
            token_data = doc.to_dict()
            if isinstance(token_data.get('created_at'), str):
                token_data['created_at'] = datetime.fromisoformat(token_data['created_at'])
            if 'expires_at' in token_data and isinstance(token_data.get('expires_at'), str):
                token_data['expires_at'] = datetime.fromisoformat(token_data['expires_at'])
            return token_data
        return None
    except Exception as e:
        logger.error(f"Error getting token from Firestore: {str(e)}")
        return None

def delete_token(token):
    """Delete access token from Firestore"""
    if not db:
        return False
    try:
        doc_ref = db.collection(TOKENS_COLLECTION).document(token)
        doc_ref.delete()
        return True
    except Exception as e:
        logger.error(f"Error deleting token from Firestore: {str(e)}")
        return False

def store_refresh_token(token, data):
    """Store refresh token in Firestore"""
    if not db:
        return False
    try:
        doc_ref = db.collection(REFRESH_TOKENS_COLLECTION).document(token)
        doc_ref.set({
            'client_id': data['client_id'],
            'created_at': data['created_at']
        })
        return True
    except Exception as e:
        logger.error(f"Error storing refresh token in Firestore: {str(e)}")
        return False

def get_refresh_token(token):
    """Get refresh token from Firestore"""
    if not db:
        return None
    try:
        doc_ref = db.collection(REFRESH_TOKENS_COLLECTION).document(token)
        doc = doc_ref.get()
        if doc.exists:
            token_data = doc.to_dict()
            if isinstance(token_data.get('created_at'), str):
                token_data['created_at'] = datetime.fromisoformat(token_data['created_at'])
            if 'expires_at' in token_data and isinstance(token_data.get('expires_at'), str):
                token_data['expires_at'] = datetime.fromisoformat(token_data['expires_at'])
            return token_data
        return None
    except Exception as e:
        logger.error(f"Error getting refresh token from Firestore: {str(e)}")
        return None


# ============================================================
# OAuth endpoints (existing)
# ============================================================

@app.route('/oauth/authorize', methods=['GET'])
def authorize():
    """OAuth authorization endpoint"""
    client_id = request.args.get('client_id')
    redirect_uri = request.args.get('redirect_uri')
    state = request.args.get('state')

    logger.info(f"Authorize request received with client_id: {client_id}, redirect_uri: {redirect_uri}, state: {state}")

    if not all([client_id, redirect_uri, state]):
        logger.error("Missing required OAuth parameters")
        return jsonify({"error": "Missing required parameters"}), 400

    if client_id != CLIENT_ID:
        logger.error(f"Invalid client_id: {client_id}")
        return jsonify({"error": "Invalid client_id"}), 401

    state_data = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'created_at': datetime.utcnow()
    }
    store_state(state, state_data)

    auth_code = secrets.token_urlsafe(32)
    auth_code_data = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'state': state,
        'created_at': datetime.utcnow(),
        'expires_at': datetime.utcnow() + timedelta(seconds=AUTH_CODE_LIFETIME)
    }
    store_auth_code(auth_code, auth_code_data)

    redirect_url = f"{redirect_uri}?code={auth_code}&state={state}"
    logger.info(f"Redirecting to: {redirect_url}")
    return redirect(redirect_url)


@app.route('/oauth/token', methods=['POST'])
def token():
    """OAuth token endpoint"""
    logger.info("Token request received")

    grant_type = request.form.get('grant_type')
    code = request.form.get('code')
    client_id = request.form.get('client_id')
    redirect_uri = request.form.get('redirect_uri')
    refresh_token = request.form.get('refresh_token')

    logger.info(f"Token request with grant_type: {grant_type}, client_id: {client_id}")

    if grant_type == 'authorization_code':
        if not all([code, client_id, redirect_uri]):
            return jsonify({"error": "Missing required parameters"}), 400
        if client_id != CLIENT_ID:
            return jsonify({"error": "Invalid client_id"}), 401

        auth_code_data = get_auth_code(code)
        if not auth_code_data:
            return jsonify({"error": "Invalid authorization code"}), 401

        if isinstance(auth_code_data['expires_at'], str):
            auth_code_data['expires_at'] = datetime.fromisoformat(auth_code_data['expires_at'])

        current_time = datetime.utcnow()
        if auth_code_data['expires_at'] < current_time:
            delete_auth_code(code)
            return jsonify({"error": "Authorization code expired"}), 401

        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)

        token_data = {
            'client_id': client_id,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(seconds=ACCESS_TOKEN_LIFETIME)
        }
        refresh_data = {
            'client_id': client_id,
            'created_at': datetime.utcnow()
        }

        store_token('access', access_token, token_data)
        store_token('refresh', refresh_token, refresh_data)
        delete_auth_code(code)

        return jsonify({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_LIFETIME,
            "refresh_token": refresh_token
        })

    if grant_type == 'refresh_token' and refresh_token:
        refresh_data = get_refresh_token(refresh_token)
        if not refresh_data:
            return jsonify({"error": "Invalid refresh token"}), 401

        access_token = secrets.token_urlsafe(32)
        token_data = {
            'client_id': refresh_data['client_id'],
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(seconds=ACCESS_TOKEN_LIFETIME)
        }
        store_token('access', access_token, token_data)

        return jsonify({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_LIFETIME,
            "refresh_token": refresh_token
        })

    return jsonify({"error": "Invalid grant type"}), 400


# ============================================================
# Original /add endpoint (preserved)
# ============================================================

@app.route('/add', methods=['POST'])
def add():
    try:
        auth_header = request.headers.get('Authorization')
        if auth_header:
            token_val = auth_header.replace('Bearer ', '')
            token_data = get_token(token_val)
            if not token_data:
                return jsonify({"error": "Invalid token"}), 401
            if isinstance(token_data['expires_at'], str):
                token_data['expires_at'] = datetime.fromisoformat(token_data['expires_at'])
            current_time = datetime.utcnow()
            if token_data['expires_at'] < current_time:
                return jsonify({"error": "Token expired"}), 401

        data = request.get_json()
        if data is None:
            return jsonify({"error": "Invalid JSON"}), 400

        a = data.get('a')
        b = data.get('b')
        if a is None or b is None:
            return jsonify({"error": "Missing 'a' or 'b' parameters"}), 400
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            return jsonify({"error": "Parameters must be numbers"}), 400

        result = a + b
        logger.info(f"Calculation performed: {a} + {b} = {result}")
        return jsonify({"result": result})

    except Exception as e:
        logger.error(f"Error in add endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============================================================
# CEPM Endpoints
# ============================================================

# --- Creative Analysis ---

@app.route('/analyze/creative', methods=['POST'])
@require_auth
def analyze_creative():
    """Analyze a creative asset against a donor persona."""
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400

    asset_type = data.get('asset_type')
    target_persona_id = data.get('target_persona')
    analysis_data = data.get('analysis_data')
    user_context = data.get('user_context', {})

    if not asset_type:
        return jsonify({"error": "Missing 'asset_type' (copy, image, or campaign)"}), 400
    if asset_type not in ('copy', 'image', 'campaign'):
        return jsonify({"error": "asset_type must be 'copy', 'image', or 'campaign'"}), 400
    if not target_persona_id:
        return jsonify({"error": "Missing 'target_persona'"}), 400
    if not analysis_data:
        return jsonify({"error": "Missing 'analysis_data'"}), 400

    persona = persona_service.get_persona(target_persona_id)
    if not persona:
        return jsonify({"error": f"Persona '{target_persona_id}' not found"}), 404

    # Score the creative
    scores = scoring.score_creative(analysis_data, persona, asset_type, user_context)

    # Generate recommendations
    recs = recommendations.generate_recommendations(
        scores, analysis_data, persona, asset_type, user_context
    )

    # Generate persona insights
    insights = recommendations.generate_persona_insights(scores, persona)

    # Store the analysis
    analysis_id = str(uuid.uuid4())
    cepm_storage.store_analysis(analysis_id, {
        'asset_type': asset_type,
        'target_persona': target_persona_id,
        'analysis_data': analysis_data,
        'user_context': user_context,
        'scores': scores,
        'recommendations': recs,
        'persona_insights': insights,
    })

    logger.info(f"Creative analysis completed: {analysis_id} (type={asset_type}, persona={target_persona_id}, overall={scores.get('overall')})")

    return jsonify({
        "analysis_id": analysis_id,
        "scores": scores,
        "recommendations": recs,
        "persona_insights": insights,
        "target_persona": persona.get('name', target_persona_id),
        "asset_type": asset_type
    })


# --- Persona Management ---

@app.route('/personas', methods=['GET'])
@require_auth
def list_personas():
    """List all donor personas."""
    all_personas = persona_service.list_personas()
    return jsonify({"personas": all_personas})


@app.route('/personas/<persona_id>', methods=['GET'])
@require_auth
def get_persona(persona_id):
    """Get a specific persona."""
    persona = persona_service.get_persona(persona_id)
    if not persona:
        return jsonify({"error": "Persona not found"}), 404
    return jsonify(persona)


@app.route('/personas', methods=['POST'])
@require_auth
def create_persona():
    """Create a new persona."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    persona_id = data.pop('id', None)
    if not persona_id:
        return jsonify({"error": "Missing 'id' field"}), 400

    result, error = persona_service.create_persona(persona_id, data)
    if error:
        return jsonify({"error": error}), 400
    return jsonify(result), 201


@app.route('/personas/<persona_id>', methods=['PUT'])
@require_auth
def update_persona(persona_id):
    """Update an existing persona."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    result, error = persona_service.update_persona(persona_id, data)
    if error:
        return jsonify({"error": error}), 404
    return jsonify(result)


@app.route('/personas/<persona_id>', methods=['DELETE'])
@require_auth
def delete_persona_endpoint(persona_id):
    """Delete a persona."""
    success, error = persona_service.delete_persona(persona_id)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"status": "deleted"}), 200


# --- Analysis History ---

@app.route('/analysis/history', methods=['GET'])
@require_auth
def analysis_history():
    """Retrieve analysis history with optional filters."""
    limit = request.args.get('limit', 20, type=int)
    persona_filter = request.args.get('persona')
    asset_type_filter = request.args.get('asset_type')

    results = cepm_storage.list_analyses(
        limit=min(limit, 100),
        persona_filter=persona_filter,
        asset_type_filter=asset_type_filter
    )
    return jsonify({"analyses": results, "count": len(results)})


@app.route('/analysis/<analysis_id>', methods=['GET'])
@require_auth
def get_analysis(analysis_id):
    """Retrieve a specific analysis result."""
    result = cepm_storage.get_analysis(analysis_id)
    if not result:
        return jsonify({"error": "Analysis not found"}), 404
    return jsonify(result)


# --- Seed Personas ---

@app.route('/personas/seed', methods=['POST'])
@require_auth
def seed_personas():
    """Seed default donor personas."""
    seeded = persona_service.seed_default_personas()
    return jsonify({"seeded": seeded, "count": len(seeded)})


# ============================================================
# Health check & utilities (existing)
# ============================================================

@app.route('/', methods=['GET'])
def health_check():
    logger.info("Health check endpoint called")
    firestore_status = "connected" if db else "not connected"
    return jsonify({
        "status": "healthy",
        "service": "CEPM - Creative Effectiveness Prediction Machine",
        "port": os.environ.get('PORT', '8080'),
        "firestore": firestore_status
    }), 200


@app.route('/privacy', methods=['GET'])
def privacy():
    """Serve the privacy policy"""
    try:
        with open('privacy.md', 'r') as f:
            content = f.read()
            html = markdown.markdown(content)
            return render_template_string('''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Privacy Policy - CEPM</title>
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                            line-height: 1.6;
                            max-width: 800px;
                            margin: 0 auto;
                            padding: 20px;
                            color: #333;
                        }
                        h1, h2 { color: #2c3e50; }
                        code { background: #f8f9fa; padding: 2px 5px; border-radius: 3px; }
                        a { color: #3498db; }
                        hr { border: 0; border-top: 1px solid #eee; margin: 20px 0; }
                    </style>
                </head>
                <body>
                    {{content|safe}}
                </body>
                </html>
            ''', content=html)
    except Exception as e:
        logger.error(f"Error serving privacy policy: {str(e)}")
        return jsonify({"error": "Privacy policy not found"}), 404


# Log startup
logger.info("CEPM Flask application starting up...")
logger.info(f"Python version: {sys.version}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
