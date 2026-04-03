"""
CEPM MCP Server — Claude integration via Model Context Protocol.

Exposes the Creative Effectiveness Prediction Machine as MCP tools,
resources, and prompts for use with Claude Desktop, Claude Code,
and any MCP-compatible client.

Run locally:   python mcp_server.py
Run via stdio: Set as an MCP server in Claude Desktop config
"""

import json
import uuid
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from cepm import personas as persona_service
from cepm import scoring, recommendations, storage as cepm_storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the MCP server
mcp = FastMCP(
    "cepm",
    description="Creative Effectiveness Prediction Machine — analyse charity marketing assets against donor personas"
)


# ============================================================
# Tools
# ============================================================

@mcp.tool()
def analyze_creative(
    asset_type: str,
    target_persona: str,
    analysis_data: dict,
    campaign_goal: str = "",
    channel: str = ""
) -> dict:
    """
    Analyse a creative asset against a donor persona and get effectiveness scores.

    You (Claude) should first analyse the user's marketing asset (image or copy),
    then structure your analysis as a JSON dict and pass it here for scoring.

    Args:
        asset_type: Type of asset — "copy", "image", or "campaign"
        target_persona: Persona ID to score against (e.g. "compassionate_supporter")
        analysis_data: Your structured analysis of the asset. For copy, include keys like:
            tone (primary, secondary, formality), readability (score, grade_level, complexity),
            key_themes, cta_assessment (clarity, urgency, persuasiveness),
            emotional_tone (primary, secondary, intensity), sentiment (positive, negative, neutral).
            For image, include: visual_elements (dominant_colors, composition, subject_type),
            emotional_tone, audience_appeal, brand_consistency.
            For campaign, include both copy_analysis and image_analysis sub-dicts.
        campaign_goal: Optional — "fundraising", "awareness", or "engagement"
        channel: Optional — "email", "social_media", "web", "direct_mail", "mobile"

    Returns:
        Scores, recommendations, and persona insights
    """
    if asset_type not in ('copy', 'image', 'campaign'):
        return {"error": "asset_type must be 'copy', 'image', or 'campaign'"}

    persona = persona_service.get_persona(target_persona)
    if not persona:
        available = [p['id'] for p in persona_service.list_personas()]
        return {"error": f"Persona '{target_persona}' not found. Available: {available}"}

    user_context = {}
    if campaign_goal:
        user_context['campaign_goal'] = campaign_goal
    if channel:
        user_context['channel'] = channel

    scores = scoring.score_creative(analysis_data, persona, asset_type, user_context)
    recs = recommendations.generate_recommendations(
        scores, analysis_data, persona, asset_type, user_context
    )
    insights = recommendations.generate_persona_insights(scores, persona)

    analysis_id = str(uuid.uuid4())
    cepm_storage.store_analysis(analysis_id, {
        'asset_type': asset_type,
        'target_persona': target_persona,
        'analysis_data': analysis_data,
        'user_context': user_context,
        'scores': scores,
        'recommendations': recs,
        'persona_insights': insights,
    })

    return {
        "analysis_id": analysis_id,
        "target_persona": persona.get('name', target_persona),
        "asset_type": asset_type,
        "scores": scores,
        "recommendations": recs,
        "persona_insights": insights,
    }


@mcp.tool()
def list_personas() -> list[dict]:
    """
    List all available donor personas.

    Returns all persona definitions with their IDs, names,
    emotional triggers, and preferences.
    """
    return persona_service.list_personas()


@mcp.tool()
def get_persona(persona_id: str) -> dict:
    """
    Get the full definition of a specific donor persona.

    Args:
        persona_id: The persona identifier (e.g. "compassionate_supporter",
                    "impact_investor", "community_builder", "legacy_giver",
                    "digital_activist")

    Returns:
        Full persona definition including emotional triggers,
        communication preferences, visual preferences, and response patterns
    """
    result = persona_service.get_persona(persona_id)
    if not result:
        available = [p['id'] for p in persona_service.list_personas()]
        return {"error": f"Persona '{persona_id}' not found. Available: {available}"}
    return result


@mcp.tool()
def create_persona(
    persona_id: str,
    name: str,
    description: str,
    emotional_triggers: list[str],
    communication_preferences: dict,
    visual_preferences: dict,
    donation_motivations: list[str] = None,
    preferred_channels: list[str] = None,
    response_patterns: dict = None
) -> dict:
    """
    Create a new donor persona.

    Args:
        persona_id: Unique identifier (snake_case, e.g. "monthly_giver")
        name: Display name (e.g. "Monthly Giver")
        description: Brief description of this donor type
        emotional_triggers: List of emotional triggers (e.g. ["consistency", "trust", "belonging"])
        communication_preferences: Dict with tone, formality (0-1), message_length, preferred_language
        visual_preferences: Dict with colors, imagery, style
        donation_motivations: Optional list of what motivates donations
        preferred_channels: Optional list of preferred communication channels
        response_patterns: Optional dict with urgency_sensitivity, data_driven, story_driven, social_proof (all 0-1)

    Returns:
        The created persona or error
    """
    data = {
        'name': name,
        'description': description,
        'emotional_triggers': emotional_triggers,
        'communication_preferences': communication_preferences,
        'visual_preferences': visual_preferences,
    }
    if donation_motivations:
        data['donation_motivations'] = donation_motivations
    if preferred_channels:
        data['preferred_channels'] = preferred_channels
    if response_patterns:
        data['response_patterns'] = response_patterns

    result, error = persona_service.create_persona(persona_id, data)
    if error:
        return {"error": error}
    return result


@mcp.tool()
def update_persona(persona_id: str, updates: dict) -> dict:
    """
    Update an existing donor persona.

    Args:
        persona_id: The persona to update
        updates: Dict of fields to update (e.g. {"emotional_triggers": ["new", "triggers"]})

    Returns:
        The updated persona or error
    """
    result, error = persona_service.update_persona(persona_id, updates)
    if error:
        return {"error": error}
    return result


@mcp.tool()
def delete_persona(persona_id: str) -> dict:
    """
    Delete a donor persona.

    Args:
        persona_id: The persona to delete

    Returns:
        Confirmation or error
    """
    success, error = persona_service.delete_persona(persona_id)
    if error:
        return {"error": error}
    return {"status": "deleted", "persona_id": persona_id}


@mcp.tool()
def get_analysis_history(
    limit: int = 20,
    persona_filter: str = "",
    asset_type_filter: str = ""
) -> dict:
    """
    Retrieve past analysis results.

    Args:
        limit: Maximum number of results (default 20, max 100)
        persona_filter: Optional — filter by persona ID
        asset_type_filter: Optional — filter by asset type (copy/image/campaign)

    Returns:
        List of past analyses with scores and recommendations
    """
    results = cepm_storage.list_analyses(
        limit=min(limit, 100),
        persona_filter=persona_filter or None,
        asset_type_filter=asset_type_filter or None
    )
    return {"analyses": results, "count": len(results)}


@mcp.tool()
def get_analysis(analysis_id: str) -> dict:
    """
    Retrieve a specific past analysis by ID.

    Args:
        analysis_id: The analysis UUID

    Returns:
        Full analysis result with scores, recommendations, and insights
    """
    result = cepm_storage.get_analysis(analysis_id)
    if not result:
        return {"error": f"Analysis '{analysis_id}' not found"}
    return result


@mcp.tool()
def seed_default_personas() -> dict:
    """
    Seed the default set of charity donor personas.

    Creates 5 default personas if they don't already exist:
    compassionate_supporter, impact_investor, community_builder,
    legacy_giver, digital_activist.

    Returns:
        List of newly seeded persona IDs
    """
    seeded = persona_service.seed_default_personas()
    return {"seeded": seeded, "count": len(seeded)}


# ============================================================
# Resources
# ============================================================

@mcp.resource("persona://list")
def resource_persona_list() -> str:
    """List of all available donor personas."""
    personas = persona_service.list_personas()
    summary = []
    for p in personas:
        summary.append(f"- **{p.get('name', p['id'])}** (`{p['id']}`): {p.get('description', 'No description')}")
    return "# Available Donor Personas\n\n" + "\n".join(summary)


@mcp.resource("persona://{persona_id}")
def resource_persona(persona_id: str) -> str:
    """Full definition of a specific donor persona."""
    persona = persona_service.get_persona(persona_id)
    if not persona:
        return f"Persona '{persona_id}' not found."
    return json.dumps(persona, indent=2, default=str)


@mcp.resource("analysis://recent")
def resource_recent_analyses() -> str:
    """Recent analysis results."""
    results = cepm_storage.list_analyses(limit=10)
    if not results:
        return "No analyses found. Use the analyze_creative tool to analyse a marketing asset."
    lines = ["# Recent Analyses\n"]
    for r in results:
        overall = r.get('scores', {}).get('overall', 'N/A')
        lines.append(
            f"- `{r['id']}` | {r.get('asset_type', '?')} | "
            f"persona: {r.get('target_persona', '?')} | "
            f"overall: {overall} | {r.get('created_at', '')}"
        )
    return "\n".join(lines)


# ============================================================
# Prompts
# ============================================================

@mcp.prompt()
def analyze_fundraising_email(copy_text: str, target_persona: str = "compassionate_supporter") -> str:
    """Analyse a fundraising email for effectiveness against a donor persona."""
    return f"""Please analyse this fundraising email copy for effectiveness against the "{target_persona}" donor persona.

**Email copy to analyse:**
{copy_text}

**Instructions:**
1. First, read the persona definition using the `get_persona` tool with persona_id="{target_persona}"
2. Analyse the copy and structure your findings as JSON with these keys:
   - tone: {{primary, secondary, formality (0-1)}}
   - readability: {{score (0-100), grade_level, complexity (simple/moderate/complex)}}
   - key_themes: [list of themes]
   - cta_assessment: {{clarity (0-1), urgency (0-1), persuasiveness (0-1)}}
   - emotional_tone: {{primary, secondary, intensity (0-1)}}
   - sentiment: {{positive (0-1), negative (0-1), neutral (0-1)}}
3. Pass your analysis to the `analyze_creative` tool with asset_type="copy", target_persona="{target_persona}", and campaign_goal="fundraising"
4. Present the scores and recommendations in a clear, actionable format
"""


@mcp.prompt()
def analyze_social_media_image(image_description: str, target_persona: str = "digital_activist") -> str:
    """Analyse a social media marketing image for effectiveness."""
    return f"""Please analyse this social media marketing image for effectiveness against the "{target_persona}" donor persona.

**Image to analyse:**
{image_description}

**Instructions:**
1. First, read the persona definition using the `get_persona` tool with persona_id="{target_persona}"
2. Analyse the image and structure your findings as JSON with these keys:
   - visual_elements: {{dominant_colors: [], composition, subject_type, background_type}}
   - emotional_tone: {{primary, secondary, intensity (0-1)}}
   - audience_appeal: {{age_groups: [], gender_bias}}
   - brand_consistency: (0-1)
3. Pass your analysis to the `analyze_creative` tool with asset_type="image", target_persona="{target_persona}", and channel="social_media"
4. Present the scores and recommendations in a clear, actionable format
"""


@mcp.prompt()
def analyze_campaign(
    copy_text: str,
    image_description: str,
    target_persona: str = "compassionate_supporter",
    campaign_goal: str = "fundraising"
) -> str:
    """Analyse a full campaign (copy + image) for effectiveness."""
    return f"""Please analyse this full marketing campaign for effectiveness against the "{target_persona}" donor persona.

**Campaign copy:**
{copy_text}

**Campaign image:**
{image_description}

**Campaign goal:** {campaign_goal}

**Instructions:**
1. First, read the persona definition using the `get_persona` tool with persona_id="{target_persona}"
2. Analyse both the copy and image, then structure your findings as JSON with:
   - copy_analysis: {{tone, readability, key_themes, cta_assessment, emotional_tone, sentiment}}
   - image_analysis: {{visual_elements, emotional_tone, audience_appeal, brand_consistency}}
3. Pass your analysis to the `analyze_creative` tool with asset_type="campaign", target_persona="{target_persona}", and campaign_goal="{campaign_goal}"
4. Present the scores and recommendations, paying special attention to how well the copy and image work together
"""


@mcp.prompt()
def compare_personas(copy_text: str) -> str:
    """Analyse copy against all personas to find the best audience match."""
    return f"""Please analyse this marketing copy against ALL available donor personas to determine which audience it's most effective for.

**Copy to analyse:**
{copy_text}

**Instructions:**
1. First, use `list_personas` to get all available personas
2. Analyse the copy once and structure your findings (tone, readability, key_themes, cta_assessment, emotional_tone, sentiment)
3. Run `analyze_creative` for EACH persona with asset_type="copy"
4. Create a comparison table showing scores across all personas
5. Identify which persona this copy is best suited for and why
6. Recommend adjustments if the copy should target a different persona
"""


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    mcp.run()
