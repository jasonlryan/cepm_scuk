# Adding OAuth to Flask Addition Service

## Overview

This guide explains how to add OAuth authentication to the Flask Addition Service to avoid constant verification prompts in ChatGPT GPTs.

## Implementation Steps

### 1. Update server.py

Add the following OAuth endpoints and configuration to your existing Flask application:

```python
from flask import Flask, request, jsonify, redirect, url_for
import secrets
import os

# Add OAuth configuration
CLIENT_ID = os.environ.get('CLIENT_ID', 'your_client_id')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', 'your_client_secret')
OAUTH_STATES = set()

# Add new OAuth endpoints
@app.route('/oauth/authorize', methods=['GET'])
def authorize():
    """OAuth authorization endpoint"""
    state = secrets.token_urlsafe(32)
    OAUTH_STATES.add(state)

    logger.info(f"OAuth authorization request received with state: {state}")

    redirect_uri = request.args.get('redirect_uri', '')
    state = request.args.get('state', '')

    if not redirect_uri:
        return jsonify({"error": "Missing redirect_uri"}), 400

    auth_code = secrets.token_urlsafe(32)
    redirect_url = f"{redirect_uri}?code={auth_code}&state={state}"

    return redirect(redirect_url)

@app.route('/oauth/token', methods=['POST'])
def token():
    """OAuth token endpoint"""
    logger.info("Token request received")

    return jsonify({
        "access_token": secrets.token_urlsafe(32),
        "token_type": "Bearer",
        "expires_in": 3600
    })

# Update existing add endpoint to check for OAuth token
@app.route('/add', methods=['POST'])
def add():
    try:
        # Check for OAuth token
        auth_header = request.headers.get('Authorization')
        if auth_header:
            logger.info("Received request with OAuth token")
            # Validate token here in production

        # ... rest of existing add function ...
```

### 2. Updated OpenAPI Schema

Replace your existing schema with this OAuth-enabled version:

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "Number Addition API",
    "description": "A simple API to add two numbers",
    "version": "1.0.0"
  },
  "servers": [
    {
      "url": "https://your-service-url.a.run.app"
    }
  ],
  "security": [
    {
      "oauth2": []
    }
  ],
  "components": {
    "securitySchemes": {
      "oauth2": {
        "type": "oauth2",
        "flows": {
          "authorizationCode": {
            "authorizationUrl": "https://your-service-url.a.run.app/oauth/authorize",
            "tokenUrl": "https://your-service-url.a.run.app/oauth/token",
            "scopes": {}
          }
        }
      }
    }
  },
  "paths": {
    "/add": {
      "post": {
        "summary": "Add two numbers",
        "operationId": "addNumbers",
        "security": [
          {
            "oauth2": []
          }
        ],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "a": {
                    "type": "number",
                    "description": "First number to add"
                  },
                  "b": {
                    "type": "number",
                    "description": "Second number to add"
                  }
                },
                "required": ["a", "b"]
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Successful addition",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "result": {
                      "type": "number",
                      "description": "The sum of the two numbers"
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid input",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message"
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### 3. GPT Configuration

In your GPT's configuration:

1. Go to "Configure" → "Actions" tab
2. Import your updated OpenAPI schema
3. Under "Authentication":
   - Select "OAuth"
   - Client ID: `gpt-client` (or any value)
   - Client Secret: Generate a random string
   - Authorization URL: `https://your-service-url.a.run.app/oauth/authorize`
   - Token URL: `https://your-service-url.a.run.app/oauth/token`
   - Scope: Leave empty
4. Token Exchange Method: "Default (POST request)"

### 4. Deployment Steps

1. Update your server code:

   ```bash
   # Deploy updated server code
   ./deploy.sh
   ```

2. Test OAuth endpoints:

   ```bash
   # Test authorization endpoint
   curl "https://your-service-url.a.run.app/oauth/authorize?redirect_uri=https://example.com&state=test"

   # Test token endpoint
   curl -X POST "https://your-service-url.a.run.app/oauth/token"
   ```

3. Test in GPT:
   - Create a test GPT
   - Configure with the OAuth settings
   - Try the add operation

## Production Considerations

For production deployment, implement these security measures:

1. **Token Validation**

   ```python
   def validate_token(token):
       # Implement proper token validation
       pass
   ```

2. **Secure Client Storage**

   ```python
   # Use environment variables
   CLIENT_ID = os.environ['CLIENT_ID']
   CLIENT_SECRET = os.environ['CLIENT_SECRET']
   ```

3. **Rate Limiting**

   ```python
   from flask_limiter import Limiter

   limiter = Limiter(app)

   @app.route('/oauth/token', methods=['POST'])
   @limiter.limit("100 per hour")
   def token():
       # ... existing code ...
   ```

4. **Token Expiration**

   ```python
   from datetime import datetime, timedelta

   def generate_token():
       return {
           "access_token": secrets.token_urlsafe(32),
           "token_type": "Bearer",
           "expires_in": 3600,
           "expires_at": datetime.utcnow() + timedelta(hours=1)
       }
   ```

## Security Best Practices

1. Use HTTPS for all endpoints
2. Implement proper token validation
3. Store client credentials securely
4. Add rate limiting
5. Log authentication attempts
6. Implement token expiration
7. Use secure session management
8. Add request validation

## Troubleshooting

1. **OAuth Flow Issues**

   - Check redirect URI configuration
   - Verify state parameter handling
   - Ensure all URLs are HTTPS

2. **Token Issues**

   - Verify token format
   - Check expiration times
   - Validate scope handling

3. **GPT Integration**
   - Confirm OAuth configuration
   - Check endpoint URLs
   - Verify client credentials

## Additional Resources

1. [OAuth 2.0 Specification](https://oauth.net/2/)
2. [Flask OAuth Documentation](https://flask.palletsprojects.com/)
3. [ChatGPT OAuth Guidelines](https://platform.openai.com/docs)
