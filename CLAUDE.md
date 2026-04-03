# CEPM — Creative Effectiveness Prediction Machine

## What this project is

CEPM scores charity marketing assets (copy, images, campaigns) against
donor personas. It predicts which donor types will respond best and
generates actionable recommendations to improve effectiveness.

## Architecture

```
cepm/                  Shared business logic (Python package)
  scoring.py           Rule-based scoring engine
  recommendations.py   Recommendation generator
  personas.py          Persona definitions + CRUD
  storage.py           Firestore abstraction

server.py              Flask API (ChatGPT plugin) — OAuth-protected
mcp_server.py          MCP server (Claude plugin) — stdio/SSE/HTTP
```

**Two interfaces, one engine:**
- Flask API at `/analyze/creative` for ChatGPT integration
- MCP server with `analyze_creative` tool for Claude integration
- Both use the same scoring/recommendation logic in `cepm/`

## MCP Tools available (via .mcp.json)

When the CEPM MCP server is connected, these tools are available:

- `analyze_creative` — Score copy/image/campaign against a persona
- `compare_across_personas` — Score against ALL personas, find best match
- `list_personas` / `get_persona` — Browse donor personas
- `create_persona` / `update_persona` / `delete_persona` — Manage personas
- `get_analysis_history` / `get_analysis` — Past results
- `seed_default_personas` — Create the 5 default personas

## Agents (in .claude/agents/)

- **copy-analyst** — Marketing copy analysis specialist
- **image-analyst** — Marketing image analysis specialist
- **campaign-strategist** — Full campaign analysis with strategic advice
- **persona-advisor** — Persona management and strategy

## Key concepts

**Personas** define donor types with:
- Emotional triggers (what makes them care)
- Communication preferences (tone, formality, length)
- Visual preferences (colours, imagery, style)
- Response patterns (urgency sensitivity, data vs story driven)

**Scoring** compares analysis data against persona preferences:
- Emotional impact (0-1)
- Clarity / readability match (0-1)
- Persona alignment (0-1)
- CTA effectiveness (0-1)
- Overall weighted score (0-1)

**Analysis flow:**
1. Claude/ChatGPT analyses the raw asset (multimodal)
2. Structures findings as JSON
3. Sends to scoring engine via tool/API
4. Engine scores against persona, generates recommendations

## Running locally

```bash
# Flask API
python server.py

# MCP server (stdio — for Claude Desktop/Code)
python mcp_server.py

# MCP server (SSE — for remote access)
python mcp_server.py --transport sse --port 8443
```

## Default personas

| ID | Name | Tone | Driven by |
|----|------|------|-----------|
| compassionate_supporter | Compassionate Supporter | warm | empathy, stories |
| impact_investor | Impact Investor | professional | data, outcomes |
| community_builder | Community Builder | inclusive | belonging, collective |
| legacy_giver | Legacy Giver | respectful | tradition, lasting impact |
| digital_activist | Digital Activist | bold | justice, authenticity |
