"""
Donor persona definitions and management for CEPM.

Provides default charity donor personas and CRUD operations
that delegate to the storage layer.
"""

from cepm import storage

# Default donor personas for charity marketing
DEFAULT_PERSONAS = {
    "compassionate_supporter": {
        "name": "Compassionate Supporter",
        "description": "Driven by empathy and personal connection. Responds strongly to individual stories and emotional appeals.",
        "emotional_triggers": ["empathy", "connection", "hope", "personal_stories", "gratitude"],
        "communication_preferences": {
            "tone": "warm",
            "formality": 0.3,
            "message_length": "medium",
            "preferred_language": ["inclusive", "personal", "heartfelt"]
        },
        "visual_preferences": {
            "colors": ["warm", "earth_tones", "soft"],
            "imagery": ["human_faces", "emotional_moments", "close_ups"],
            "style": "authentic"
        },
        "donation_motivations": ["helping_individuals", "making_a_difference", "emotional_fulfillment"],
        "preferred_channels": ["email", "direct_mail"],
        "response_patterns": {
            "urgency_sensitivity": 0.6,
            "data_driven": 0.3,
            "story_driven": 0.9,
            "social_proof": 0.5
        }
    },
    "impact_investor": {
        "name": "Impact Investor",
        "description": "Wants measurable outcomes and accountability. Treats donations as investments and expects clear ROI reporting.",
        "emotional_triggers": ["achievement", "progress", "accountability", "efficiency", "scale"],
        "communication_preferences": {
            "tone": "professional",
            "formality": 0.8,
            "message_length": "concise",
            "preferred_language": ["data_driven", "precise", "outcome_focused"]
        },
        "visual_preferences": {
            "colors": ["cool", "corporate", "clean"],
            "imagery": ["infographics", "data_visualizations", "before_after"],
            "style": "polished"
        },
        "donation_motivations": ["measurable_outcomes", "efficiency", "systemic_change"],
        "preferred_channels": ["email", "reports", "web"],
        "response_patterns": {
            "urgency_sensitivity": 0.4,
            "data_driven": 0.9,
            "story_driven": 0.3,
            "social_proof": 0.7
        }
    },
    "community_builder": {
        "name": "Community Builder",
        "description": "Motivated by belonging and collective action. Values being part of a movement and shared purpose.",
        "emotional_triggers": ["belonging", "togetherness", "shared_purpose", "pride", "solidarity"],
        "communication_preferences": {
            "tone": "inclusive",
            "formality": 0.5,
            "message_length": "medium",
            "preferred_language": ["collective", "we_focused", "empowering"]
        },
        "visual_preferences": {
            "colors": ["bright", "vibrant", "warm"],
            "imagery": ["group_photos", "community_events", "diverse_faces"],
            "style": "energetic"
        },
        "donation_motivations": ["collective_action", "being_part_of_something", "community_impact"],
        "preferred_channels": ["social_media", "events", "email"],
        "response_patterns": {
            "urgency_sensitivity": 0.5,
            "data_driven": 0.4,
            "story_driven": 0.6,
            "social_proof": 0.9
        }
    },
    "legacy_giver": {
        "name": "Legacy Giver",
        "description": "Focused on lasting impact and enduring values. Often older donors who want their contribution to outlive them.",
        "emotional_triggers": ["tradition", "lasting_impact", "values", "legacy", "dignity"],
        "communication_preferences": {
            "tone": "respectful",
            "formality": 0.8,
            "message_length": "detailed",
            "preferred_language": ["dignified", "thoughtful", "enduring"]
        },
        "visual_preferences": {
            "colors": ["classic", "muted", "dignified"],
            "imagery": ["heritage", "generational", "institutional"],
            "style": "traditional"
        },
        "donation_motivations": ["leaving_a_legacy", "honoring_values", "long_term_impact"],
        "preferred_channels": ["direct_mail", "phone", "in_person"],
        "response_patterns": {
            "urgency_sensitivity": 0.3,
            "data_driven": 0.5,
            "story_driven": 0.7,
            "social_proof": 0.4
        }
    },
    "digital_activist": {
        "name": "Digital Activist",
        "description": "Young, socially conscious, digitally native. Driven by justice and authenticity. Shares causes online.",
        "emotional_triggers": ["justice", "urgency", "change", "authenticity", "outrage"],
        "communication_preferences": {
            "tone": "bold",
            "formality": 0.2,
            "message_length": "short",
            "preferred_language": ["direct", "punchy", "authentic"]
        },
        "visual_preferences": {
            "colors": ["bold", "high_contrast", "neon"],
            "imagery": ["raw", "authentic", "dynamic", "user_generated"],
            "style": "edgy"
        },
        "donation_motivations": ["social_change", "awareness", "viral_impact", "peer_influence"],
        "preferred_channels": ["social_media", "mobile", "web"],
        "response_patterns": {
            "urgency_sensitivity": 0.9,
            "data_driven": 0.4,
            "story_driven": 0.7,
            "social_proof": 0.8
        }
    }
}


def seed_default_personas():
    """Seed default personas into Firestore if they don't exist."""
    existing = storage.list_personas()
    existing_ids = {p['id'] for p in existing}

    seeded = []
    for persona_id, persona_data in DEFAULT_PERSONAS.items():
        if persona_id not in existing_ids:
            storage.store_persona(persona_id, persona_data)
            seeded.append(persona_id)

    return seeded


def get_persona(persona_id):
    """Get a persona by ID, falling back to defaults if Firestore unavailable."""
    result = storage.get_persona(persona_id)
    if result:
        return result
    if persona_id in DEFAULT_PERSONAS:
        return {"id": persona_id, **DEFAULT_PERSONAS[persona_id]}
    return None


def list_personas():
    """List all personas, falling back to defaults if Firestore unavailable."""
    results = storage.list_personas()
    if results:
        return results
    return [{"id": k, **v} for k, v in DEFAULT_PERSONAS.items()]


def create_persona(persona_id, data):
    """Create a new persona."""
    if storage.get_persona(persona_id):
        return None, "Persona already exists"
    required = ['name', 'emotional_triggers', 'communication_preferences', 'visual_preferences']
    missing = [f for f in required if f not in data]
    if missing:
        return None, f"Missing required fields: {', '.join(missing)}"
    storage.store_persona(persona_id, data)
    return {"id": persona_id, **data}, None


def update_persona(persona_id, data):
    """Update an existing persona."""
    existing = storage.get_persona(persona_id)
    if not existing:
        return None, "Persona not found"
    existing.pop('id', None)
    existing.update(data)
    storage.store_persona(persona_id, existing)
    return {"id": persona_id, **existing}, None


def delete_persona(persona_id):
    """Delete a persona."""
    existing = storage.get_persona(persona_id)
    if not existing:
        return False, "Persona not found"
    storage.delete_persona(persona_id)
    return True, None
