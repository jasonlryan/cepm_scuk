"""
CEPM MCP Server — Claude integration via Model Context Protocol.

Exposes the Creative Effectiveness Prediction Machine as MCP tools,
resources, and prompts for use with Claude Desktop, Claude Code,
and any MCP-compatible client.

Transports:
  stdio (default):  python mcp_server.py
  SSE (remote):     python mcp_server.py --transport sse --port 8443
  HTTP (remote):    python mcp_server.py --transport http --port 8443
"""

import json
import uuid
import logging
import sys
import os
import argparse
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from cepm import personas as persona_service
from cepm import scoring, recommendations, storage as cepm_storage

# ============================================================
# Logging — stderr only (stdout reserved for JSON-RPC in stdio mode)
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger("cepm-mcp")


# ============================================================
# Lifespan — initialise Firestore + seed personas on startup
# ============================================================

@asynccontextmanager
async def cepm_lifespan(server):
    """Initialise shared resources when the MCP server starts."""
    logger.info("CEPM MCP server starting up")

    # Ensure Firestore client is ready
    db = cepm_storage.get_db()
    if db:
        logger.info("Firestore connected")
        # Auto-seed default personas on first run
        seeded = persona_service.seed_default_personas()
        if seeded:
            logger.info(f"Seeded default personas: {seeded}")
    else:
        logger.warning("Firestore unavailable — using in-memory persona defaults")

    yield {}

    logger.info("CEPM MCP server shutting down")


# ============================================================
# Server
# ============================================================

mcp = FastMCP(
    "cepm",
    description=(
        "Creative Effectiveness Prediction Machine (CEPM) for SCUK. "
        "Analyse charity marketing assets (copy, images, campaigns) against "
        "donor personas. Scores effectiveness, generates recommendations, "
        "and tracks analysis history."
    ),
    lifespan=cepm_lifespan,
)


# ============================================================
# Tools — Analysis
# ============================================================

@mcp.tool()
def analyze_creative(
    asset_type: str,
    target_persona: str,
    analysis_data: dict,
    campaign_goal: str = "",
    channel: str = "",
) -> dict:
    """
    Score a creative asset against a donor persona.

    You (Claude) should first analyse the user's marketing asset, then
    structure your analysis as JSON and pass it here for scoring.

    Args:
        asset_type: "copy", "image", or "campaign"
        target_persona: Persona ID (e.g. "compassionate_supporter")
        analysis_data: Your structured analysis. For copy include:
            tone {primary, secondary, formality 0-1},
            readability {score 0-100, grade_level, complexity},
            key_themes [], cta_assessment {clarity, urgency, persuasiveness 0-1},
            emotional_tone {primary, secondary, intensity 0-1},
            sentiment {positive, negative, neutral 0-1}.
            For image include: visual_elements {dominant_colors, composition,
            subject_type, background_type}, emotional_tone, audience_appeal,
            brand_consistency 0-1.
            For campaign include copy_analysis and image_analysis sub-dicts.
        campaign_goal: Optional — "fundraising", "awareness", or "engagement"
        channel: Optional — "email", "social_media", "web", "direct_mail", "mobile"

    Returns:
        Effectiveness scores (0-1), actionable recommendations, persona insights
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

    logger.info(
        f"Analysis {analysis_id}: type={asset_type} persona={target_persona} "
        f"overall={scores.get('overall')}"
    )

    return {
        "analysis_id": analysis_id,
        "target_persona": persona.get('name', target_persona),
        "asset_type": asset_type,
        "scores": scores,
        "recommendations": recs,
        "persona_insights": insights,
    }


@mcp.tool()
def compare_across_personas(
    asset_type: str,
    analysis_data: dict,
    campaign_goal: str = "",
    channel: str = "",
) -> dict:
    """
    Score a creative asset against ALL personas to find the best audience match.

    Runs the scoring engine for every persona and returns a comparison table.

    Args:
        asset_type: "copy", "image", or "campaign"
        analysis_data: Your structured analysis (same format as analyze_creative)
        campaign_goal: Optional campaign goal
        channel: Optional distribution channel

    Returns:
        Comparison table with scores per persona, ranked by overall score
    """
    all_personas = persona_service.list_personas()
    user_context = {}
    if campaign_goal:
        user_context['campaign_goal'] = campaign_goal
    if channel:
        user_context['channel'] = channel

    results = []
    for persona in all_personas:
        scores = scoring.score_creative(analysis_data, persona, asset_type, user_context)
        results.append({
            "persona_id": persona['id'],
            "persona_name": persona.get('name', persona['id']),
            "overall": scores.get('overall', 0),
            "emotional_impact": scores.get('emotional_impact', 0),
            "persona_alignment": scores.get('persona_alignment', 0),
            "scores": scores,
        })

    results.sort(key=lambda r: r['overall'], reverse=True)

    best = results[0] if results else None
    worst = results[-1] if results else None

    return {
        "comparison": results,
        "best_match": {
            "persona": best['persona_name'],
            "overall_score": best['overall'],
        } if best else None,
        "worst_match": {
            "persona": worst['persona_name'],
            "overall_score": worst['overall'],
        } if worst else None,
        "asset_type": asset_type,
    }


# ============================================================
# Tools — Persona Management
# ============================================================

@mcp.tool()
def list_personas() -> list[dict]:
    """
    List all available donor personas.

    Returns all persona definitions with their IDs, names,
    emotional triggers, and preferences. Default personas include:
    compassionate_supporter, impact_investor, community_builder,
    legacy_giver, digital_activist.
    """
    return persona_service.list_personas()


@mcp.tool()
def get_persona(persona_id: str) -> dict:
    """
    Get the full definition of a donor persona.

    Args:
        persona_id: e.g. "compassionate_supporter", "impact_investor",
                    "community_builder", "legacy_giver", "digital_activist"

    Returns:
        Full persona: emotional triggers, communication preferences,
        visual preferences, donation motivations, response patterns
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
    response_patterns: dict = None,
) -> dict:
    """
    Create a new donor persona.

    Args:
        persona_id: Unique snake_case identifier (e.g. "monthly_giver")
        name: Display name (e.g. "Monthly Giver")
        description: Brief description of this donor type
        emotional_triggers: e.g. ["consistency", "trust", "belonging"]
        communication_preferences: {tone, formality 0-1, message_length, preferred_language []}
        visual_preferences: {colors [], imagery [], style}
        donation_motivations: Optional list
        preferred_channels: Optional list (email, social_media, web, direct_mail, mobile)
        response_patterns: Optional {urgency_sensitivity, data_driven, story_driven, social_proof} all 0-1
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
    logger.info(f"Created persona: {persona_id}")
    return result


@mcp.tool()
def update_persona(persona_id: str, updates: dict) -> dict:
    """
    Update an existing donor persona.

    Args:
        persona_id: The persona to update
        updates: Fields to update, e.g. {"emotional_triggers": ["new", "triggers"]}
    """
    result, error = persona_service.update_persona(persona_id, updates)
    if error:
        return {"error": error}
    logger.info(f"Updated persona: {persona_id}")
    return result


@mcp.tool()
def delete_persona(persona_id: str) -> dict:
    """Delete a donor persona."""
    success, error = persona_service.delete_persona(persona_id)
    if error:
        return {"error": error}
    logger.info(f"Deleted persona: {persona_id}")
    return {"status": "deleted", "persona_id": persona_id}


# ============================================================
# Tools — History
# ============================================================

@mcp.tool()
def get_analysis_history(
    limit: int = 20,
    persona_filter: str = "",
    asset_type_filter: str = "",
) -> dict:
    """
    Retrieve past analysis results.

    Args:
        limit: Max results (default 20, max 100)
        persona_filter: Optional — filter by persona ID
        asset_type_filter: Optional — "copy", "image", or "campaign"
    """
    results = cepm_storage.list_analyses(
        limit=min(limit, 100),
        persona_filter=persona_filter or None,
        asset_type_filter=asset_type_filter or None,
    )
    return {"analyses": results, "count": len(results)}


@mcp.tool()
def get_analysis(analysis_id: str) -> dict:
    """
    Retrieve a specific past analysis by ID.

    Args:
        analysis_id: The analysis UUID
    """
    result = cepm_storage.get_analysis(analysis_id)
    if not result:
        return {"error": f"Analysis '{analysis_id}' not found"}
    return result


@mcp.tool()
def seed_default_personas() -> dict:
    """
    Seed the 5 default charity donor personas if they don't already exist.

    Creates: compassionate_supporter, impact_investor, community_builder,
    legacy_giver, digital_activist.
    """
    seeded = persona_service.seed_default_personas()
    logger.info(f"Seeded personas: {seeded}")
    return {"seeded": seeded, "count": len(seeded)}


# ============================================================
# Resources
# ============================================================

@mcp.resource("cepm://personas")
def resource_persona_list() -> str:
    """Overview of all available donor personas."""
    personas = persona_service.list_personas()
    lines = ["# CEPM Donor Personas\n"]
    for p in personas:
        triggers = ", ".join(p.get('emotional_triggers', [])[:4])
        lines.append(
            f"## {p.get('name', p['id'])} (`{p['id']}`)\n"
            f"{p.get('description', 'No description')}\n"
            f"- Triggers: {triggers}\n"
            f"- Tone: {p.get('communication_preferences', {}).get('tone', '?')}\n"
            f"- Channels: {', '.join(p.get('preferred_channels', []))}\n"
        )
    return "\n".join(lines)


@mcp.resource("cepm://persona/{persona_id}")
def resource_persona(persona_id: str) -> str:
    """Full JSON definition of a specific donor persona."""
    persona = persona_service.get_persona(persona_id)
    if not persona:
        return f"Persona '{persona_id}' not found."
    return json.dumps(persona, indent=2, default=str)


@mcp.resource("cepm://history")
def resource_recent_analyses() -> str:
    """Summary of the 10 most recent analyses."""
    results = cepm_storage.list_analyses(limit=10)
    if not results:
        return "No analyses yet. Use the analyze_creative tool to get started."
    lines = ["# Recent CEPM Analyses\n"]
    for r in results:
        overall = r.get('scores', {}).get('overall', 'N/A')
        strengths = ", ".join(r.get('persona_insights', {}).get('strengths', [])[:2])
        lines.append(
            f"- **{r['id'][:8]}...** | {r.get('asset_type', '?')} | "
            f"persona: {r.get('target_persona', '?')} | "
            f"overall: {overall} | strengths: {strengths}"
        )
    return "\n".join(lines)


@mcp.resource("cepm://guide")
def resource_user_guide() -> str:
    """Quick-start guide for using CEPM with Claude."""
    return """# CEPM Quick-Start Guide

## What is CEPM?
The Creative Effectiveness Prediction Machine scores your charity marketing
assets against donor personas. It tells you how well your copy, images, or
campaigns resonate with specific donor types.

## How to use it

### 1. Analyse marketing copy
Share your email, ad, or social post text. Claude will:
- Assess tone, readability, emotional impact, and CTA strength
- Score it against your chosen donor persona
- Give you specific recommendations

### 2. Analyse an image
Share or describe your marketing image. Claude will:
- Assess visual elements, emotional tone, and audience appeal
- Score it against your chosen persona's visual preferences
- Suggest improvements

### 3. Full campaign analysis
Share both copy and image for a holistic score including
copy-image coherence.

### 4. Compare across personas
Not sure who your audience is? Run your asset against all 5
personas to find the best match.

## Available personas
- `compassionate_supporter` — empathy-driven, responds to stories
- `impact_investor` — data-driven, wants measurable outcomes
- `community_builder` — motivated by belonging and collective action
- `legacy_giver` — values tradition and lasting impact
- `digital_activist` — young, bold, authenticity-driven

## Tips
- Be specific about your campaign goal (fundraising/awareness/engagement)
- Mention the distribution channel (email/social/web/direct_mail)
- Use `compare_across_personas` when targeting is unclear
- Check `get_analysis_history` to track improvements over time
"""


# ============================================================
# Prompts
# ============================================================

@mcp.prompt()
def analyze_fundraising_email(
    copy_text: str,
    target_persona: str = "compassionate_supporter",
) -> str:
    """Analyse a fundraising email for effectiveness against a donor persona."""
    return f"""Analyse this fundraising email for effectiveness against the "{target_persona}" persona.

**Email copy:**
{copy_text}

**Steps:**
1. Use `get_persona` to load the "{target_persona}" persona definition
2. Analyse the copy — assess tone, readability, emotional resonance, themes, CTA
3. Structure your analysis as JSON and call `analyze_creative` with asset_type="copy",
   target_persona="{target_persona}", campaign_goal="fundraising"
4. Present the scores as a clear summary table
5. List the recommendations in priority order with specific rewording suggestions
"""


@mcp.prompt()
def analyze_social_image(
    image_description: str,
    target_persona: str = "digital_activist",
) -> str:
    """Analyse a social media marketing image."""
    return f"""Analyse this social media image for effectiveness against the "{target_persona}" persona.

**Image:**
{image_description}

**Steps:**
1. Use `get_persona` to load the "{target_persona}" persona definition
2. Analyse visual elements, emotional tone, composition, colours, subject
3. Structure as JSON and call `analyze_creative` with asset_type="image",
   target_persona="{target_persona}", channel="social_media"
4. Present scores and visual improvement recommendations
"""


@mcp.prompt()
def analyze_full_campaign(
    copy_text: str,
    image_description: str,
    target_persona: str = "compassionate_supporter",
    campaign_goal: str = "fundraising",
) -> str:
    """Analyse a full campaign (copy + image) for coherence and effectiveness."""
    return f"""Analyse this complete campaign for effectiveness against the "{target_persona}" persona.

**Copy:** {copy_text}
**Image:** {image_description}
**Goal:** {campaign_goal}

**Steps:**
1. Load the persona with `get_persona`
2. Analyse copy and image separately, then structure as:
   {{"copy_analysis": {{...}}, "image_analysis": {{...}}}}
3. Call `analyze_creative` with asset_type="campaign",
   target_persona="{target_persona}", campaign_goal="{campaign_goal}"
4. Focus your summary on copy-image coherence and overall persona fit
"""


@mcp.prompt()
def find_best_audience(copy_text: str) -> str:
    """Find which donor persona this copy resonates with most."""
    return f"""Determine which donor persona this marketing copy is most effective for.

**Copy:** {copy_text}

**Steps:**
1. Analyse the copy (tone, readability, themes, CTA, emotional tone, sentiment)
2. Call `compare_across_personas` with asset_type="copy" and your analysis
3. Present a comparison table: persona | overall | emotional_impact | alignment
4. Explain WHY the top persona is the best match
5. If the copy should target a different persona, suggest specific rewrites
"""


@mcp.prompt()
def improve_for_persona(
    copy_text: str,
    target_persona: str,
) -> str:
    """Get specific rewrite suggestions to improve copy for a persona."""
    return f"""Analyse this copy and provide specific rewrite suggestions to improve it for the "{target_persona}" persona.

**Copy:** {copy_text}

**Steps:**
1. Load the persona with `get_persona`
2. Analyse and score with `analyze_creative`
3. For EACH recommendation, provide:
   - The original line/phrase
   - A rewritten version optimised for this persona
   - Why the change works better for this persona type
4. Show projected score improvement if the changes were applied
"""


# ============================================================
# Entry point
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="CEPM MCP Server")
    parser.add_argument(
        "--transport", choices=["stdio", "sse", "http"],
        default="stdio",
        help="Transport protocol (default: stdio)"
    )
    parser.add_argument("--port", type=int, default=8443, help="Port for SSE/HTTP transport")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE/HTTP transport")
    args = parser.parse_args()

    if args.transport == "stdio":
        logger.info("Starting CEPM MCP server (stdio transport)")
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        logger.info(f"Starting CEPM MCP server (SSE on {args.host}:{args.port})")
        mcp.run(transport="sse", host=args.host, port=args.port)
    elif args.transport == "http":
        logger.info(f"Starting CEPM MCP server (HTTP on {args.host}:{args.port})")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
