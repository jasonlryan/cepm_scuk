# Flask Addition Service with OAuth and Firestore

## Overview

This service provides a simple REST API endpoint that adds two numbers together, secured with OAuth 2.0 authentication and using Google Firestore for persistent token storage. It's designed to be deployed on Google Cloud Run and integrated with Custom GPTs, eliminating the need for constant verification prompts.

The service implements:

- A complete OAuth 2.0 authorization flow with authorization codes
- Access tokens with 30-day validity
- Refresh token support for seamless re-authentication
- Persistent token storage using Google Firestore
- A simple `/add` endpoint that performs number addition

## Project Structure

```
.
├── server.py        # Flask application with OAuth, Firestore and add endpoints
├── requirements.txt # Python dependencies
├── Dockerfile       # Container configuration for multi-arch support
├── deploy.sh        # Automated deployment script
├── privacy.md       # Privacy policy for GPT integration
├── openapi.json     # OpenAPI schema with OAuth configuration
└── instructions.md  # This documentation
```

## Local Setup

1. Create a Python virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Unix/macOS
   # OR
   .\venv\Scripts\activate  # On Windows
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up Firestore credentials:

   ```bash
   # Create a service account key file for local development
   gcloud iam service-accounts keys create key.json \
     --iam-account=flask-addition-service@YOUR_PROJECT_ID.iam.gserviceaccount.com

   # Set environment variable to point to the key file
   export GOOGLE_APPLICATION_CREDENTIALS=./key.json
   ```

4. Run the application locally:
   ```bash
   python server.py
   ```
   The server will start at http://localhost:8080

## Docker Setup

1. The Dockerfile is configured for multi-architecture support and Firestore integration:

   ```dockerfile
   FROM --platform=linux/amd64 python:3.9-slim

   WORKDIR /app

   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   COPY . .

   ENV PORT=8080
   ENV GOOGLE_APPLICATION_CREDENTIALS=/app/key.json

   CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "--log-level", "debug", "server:app"]
   ```

   Key points about the Dockerfile:

   - Uses `--platform=linux/amd64` to ensure compatibility with Cloud Run
   - Sets explicit Gunicorn configuration for better performance and debugging
   - Configures Firestore credentials path
   - Uses environment variable for port configuration

2. Build the Docker image:

   ```bash
   docker build --platform linux/amd64 -t flask-addition-service .
   ```

3. Run the container locally:
   ```bash
   docker run -p 8080:8080 -v $(pwd)/key.json:/app/key.json flask-addition-service
   ```

## Google Cloud Deployment

### Prerequisites

1. Install the Google Cloud SDK:

   - Visit https://cloud.google.com/sdk/docs/install
   - Follow the installation instructions for your operating system

2. Initialize Google Cloud:

   ```bash
   gcloud init
   ```

3. Set up authentication:

   ```bash
   gcloud auth login
   gcloud auth configure-docker
   ```

4. Enable required APIs:

   ```bash
   gcloud services enable run.googleapis.com containerregistry.googleapis.com firestore.googleapis.com
   ```

5. Create a dedicated service account for Firestore access:

   ```bash
   # Create service account
   gcloud iam service-accounts create flask-addition-service \
     --display-name="Flask Addition Service Account"

   # Grant Firestore access
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:flask-addition-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/datastore.user"
   ```

### Deployment Steps

#### Option 1: Automated Deployment (Recommended)

We provide a deployment script (`deploy.sh`) that automates the entire process and includes several safety checks:

1. Make the script executable (one-time setup):

   ```bash
   chmod +x deploy.sh
   ```

2. Run the deployment:
   ```bash
   ./deploy.sh
   ```

The script will automatically:

- Check for required tools (Docker, gcloud)
- Verify Google Cloud authentication
- Enable required APIs
- Configure Docker authentication
- Build the Docker image with proper platform settings
- Push to Google Container Registry
- Deploy to Cloud Run with appropriate settings and service account
- Verify the deployment and test the health check
- Provide next steps and helpful links

#### Option 2: Manual Deployment

If you prefer to run the commands manually:

1. Set your project ID:

   ```bash
   export PROJECT_ID=$(gcloud config get-value project)
   ```

2. Build and push the container:

   ```bash
   docker build --platform linux/amd64 -t gcr.io/$PROJECT_ID/flask-addition-service .
   docker push gcr.io/$PROJECT_ID/flask-addition-service
   ```

3. Deploy to Cloud Run with the service account:
   ```bash
   gcloud run deploy flask-addition-service \
     --image gcr.io/$PROJECT_ID/flask-addition-service \
     --platform managed \
     --region europe-west1 \
     --allow-unauthenticated \
     --timeout 300 \
     --service-account flask-addition-service@$PROJECT_ID.iam.gserviceaccount.com
   ```

## OAuth Implementation Details

### OAuth Flow

The service implements a standard OAuth 2.0 authorization code flow:

1. **Authorization Request**:

   - Client redirects to `/oauth/authorize` with client_id, redirect_uri, and state
   - Server generates an authorization code and redirects back to the client

2. **Token Exchange**:

   - Client sends authorization code to `/oauth/token` with grant_type=authorization_code
   - Server validates the code and returns access_token and refresh_token

3. **API Access**:

   - Client uses access_token in Authorization header to access `/add` endpoint
   - Server validates the token before processing the request

4. **Token Refresh**:
   - When access_token expires, client can use refresh_token to get a new access_token
   - Client sends refresh_token to `/oauth/token` with grant_type=refresh_token

### Token Lifetimes

- **Authorization Codes**: 10 minutes
- **Access Tokens**: 30 days
- **Refresh Tokens**: No expiration (can be revoked if needed)

### Firestore Collections

The service uses the following Firestore collections for token management:

- **oauth_states**: Stores OAuth state parameters during authorization
- **auth_codes**: Stores authorization codes with expiration times
- **tokens**: Stores access tokens with client information and expiration
- **refresh_tokens**: Stores refresh tokens for token renewal

## API Usage

### OpenAPI Schema

The service is configured with the following OpenAPI schema, which is used for ChatGPT actions:

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
      "url": "https://flask-addition-service-iuvapqijhq-ew.a.run.app"
    }
  ],
  "security": [
    {
      "oauth2": []
    }
  ],
  "components": {
    "schemas": {
      "AddRequest": {
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
      },
      "AddResponse": {
        "type": "object",
        "properties": {
          "result": {
            "type": "number",
            "description": "The sum of the two numbers"
          }
        }
      },
      "ErrorResponse": {
        "type": "object",
        "properties": {
          "error": {
            "type": "string",
            "description": "Error message"
          }
        }
      }
    },
    "securitySchemes": {
      "oauth2": {
        "type": "oauth2",
        "flows": {
          "authorizationCode": {
            "authorizationUrl": "https://flask-addition-service-iuvapqijhq-ew.a.run.app/oauth/authorize",
            "tokenUrl": "https://flask-addition-service-iuvapqijhq-ew.a.run.app/oauth/token",
            "refreshUrl": "https://flask-addition-service-iuvapqijhq-ew.a.run.app/oauth/token",
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
                "$ref": "#/components/schemas/AddRequest"
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
                  "$ref": "#/components/schemas/AddResponse"
                }
              }
            }
          },
          "400": {
            "description": "Invalid input",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ErrorResponse"
                }
              }
            }
          },
          "401": {
            "description": "Unauthorized",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ErrorResponse"
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

### API Endpoints

#### OAuth Endpoints

**Authorization Endpoint**

- **URL**: `/oauth/authorize`
- **Method**: GET
- **Parameters**:
  - `client_id`: Client identifier (default: 'gpt-client')
  - `redirect_uri`: URI to redirect after authorization
  - `state`: Random string for CSRF protection
- **Response**: Redirects to redirect_uri with authorization code

**Token Endpoint**

- **URL**: `/oauth/token`
- **Method**: POST
- **Parameters for Authorization Code Flow**:
  - `grant_type`: 'authorization_code'
  - `code`: Authorization code from previous step
  - `client_id`: Client identifier
  - `redirect_uri`: Must match the original redirect URI
- **Parameters for Refresh Token Flow**:
  - `grant_type`: 'refresh_token'
  - `refresh_token`: Refresh token from previous token response
  - `client_id`: Client identifier
- **Response**: JSON with access_token, refresh_token, token_type, and expires_in

#### Add Numbers Endpoint

**Endpoint:** `/add`  
**Method:** POST  
**Headers:**

- `Authorization: Bearer <access_token>`
- `Content-Type: application/json`

**Request Body:**

```json
{
    "a": number,  // First number to add
    "b": number   // Second number to add
}
```

**Success Response (200):**

```json
{
    "result": number  // The sum of the two numbers
}
```

**Error Response (400):**

```json
{
    "error": string  // Error message
}
```

**Error Response (401):**

```json
{
    "error": "Invalid token" or "Token expired"
}
```

#### Health Check Endpoint

**Endpoint:** `/`  
**Method:** GET

**Success Response (200):**

```json
{
  "status": "healthy",
  "port": "8080",
  "cwd": "/app",
  "firestore": "connected"
}
```

#### Privacy Policy Endpoint

**Endpoint:** `/privacy`  
**Method:** GET

**Response**: HTML-formatted privacy policy

## Integration with ChatGPT

### Setting Up OAuth in Your GPT

1. Create or edit your GPT in the GPT Builder
2. Go to the "Configure" tab
3. Select "Actions"
4. Import the OpenAPI schema from `openapi.json`
5. Under "Authentication", select "OAuth"
6. Configure the OAuth settings:
   - Client ID: `gpt-client` (or any value matching your server configuration)
   - Authorization URL: Your service URL + `/oauth/authorize`
   - Token URL: Your service URL + `/oauth/token`
   - Scope: Leave empty
   - Token Exchange Method: "Default (POST request)"
7. Save your GPT configuration

### Testing the Integration

1. Test the authorization flow:

   ```bash
   curl -v "https://your-service-url/oauth/authorize?client_id=gpt-client&redirect_uri=https://example.com&state=test123"
   ```

2. Exchange the authorization code for tokens:

   ```bash
   curl -v -X POST "https://your-service-url/oauth/token" \
     -d "grant_type=authorization_code&code=YOUR_AUTH_CODE&client_id=gpt-client&redirect_uri=https://example.com"
   ```

3. Test the API with the access token:

   ```bash
   curl -v -X POST "https://your-service-url/add" \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"a": 10, "b": 20}'
   ```

4. Test the refresh token flow:
   ```bash
   curl -v -X POST "https://your-service-url/oauth/token" \
     -d "grant_type=refresh_token&refresh_token=YOUR_REFRESH_TOKEN&client_id=gpt-client"
   ```

## Troubleshooting

### Common Issues

1. **Firestore Connection Issues**:

   - Check service account permissions
   - Verify GOOGLE_APPLICATION_CREDENTIALS is set correctly
   - Check Firestore API is enabled

2. **OAuth Flow Problems**:

   - Verify client_id matches between server and GPT configuration
   - Ensure redirect_uri is consistent throughout the flow
   - Check for proper URL encoding of parameters

3. **Token Validation Errors**:
   - Check for token expiration
   - Verify token format in Authorization header
   - Look for datetime comparison issues in logs

### Viewing Logs

```bash
# View Cloud Run logs
gcloud logs tail --project=YOUR_PROJECT_ID --service=flask-addition-service

# Filter for specific error types
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=flask-addition-service AND textPayload:ERROR" --project=YOUR_PROJECT_ID
```

## Security Considerations

1. **Token Security**:

   - Access tokens are valid for 30 days
   - Refresh tokens have no expiration but can be revoked
   - All tokens are generated using cryptographically secure methods

2. **Data Storage**:

   - No user data is stored beyond authentication tokens
   - Firestore collections are secured by service account permissions
   - No personal information is collected

3. **Privacy Policy**:
   - A privacy policy is provided at `/privacy`
   - This policy explains data handling practices
   - It satisfies ChatGPT's requirements for API integration

## Requirements

The service requires the following dependencies:

```
flask==3.0.2
gunicorn==21.2.0
flask-cors==4.0.0
markdown==3.5.2
google-cloud-firestore==2.15.0
```

## Extending for Complex Applications

While this implementation demonstrates a simple number addition service, the OAuth and Firestore infrastructure provides a robust foundation for more complex applications, such as marketing asset performance analysis algorithms.

### Architecture for Marketing Asset Analysis

The current architecture can be extended to support sophisticated marketing analytics by:

1. **Enhanced Endpoint Structure**:

   - Replace or supplement the `/add` endpoint with specialized endpoints like:
     - `/analyze/copy` - Analyze marketing copy effectiveness
     - `/analyze/image` - Evaluate image performance potential
     - `/analyze/campaign` - Assess full campaign performance metrics
     - `/analyze/audience` - Match content to target audience profiles

2. **Data Processing Pipeline**:

   - Implement a multi-stage processing pipeline:
     ```
     Input → Preprocessing → Feature Extraction → Model Inference → Post-processing → Response
     ```
   - Each stage can be modularized for easier maintenance and updates

3. **Model Integration**:

   - Integrate machine learning models for prediction:
     - Store models in Cloud Storage and load at startup
     - Use TensorFlow Serving or similar services for model hosting
     - Implement model versioning for A/B testing different algorithms

4. **Persistent Storage Patterns**:
   - Extend Firestore usage beyond authentication:
     - Store analysis results with user-specific collections
     - Track historical performance of assets
     - Maintain user preferences and settings
     - Cache frequent analyses for performance

### Implementation Example

Here's how you might extend the server.py file to support marketing asset analysis:

```python
# Add new dependencies
import tensorflow as tf
from google.cloud import storage
from PIL import Image
import io
import nltk
import pandas as pd

# Initialize ML models
def load_models():
    """Load ML models from Cloud Storage"""
    storage_client = storage.Client()
    bucket = storage_client.bucket('marketing-models')

    # Load text analysis model
    blob = bucket.blob('models/text_effectiveness_v2.h5')
    with io.BytesIO(blob.download_as_bytes()) as model_file:
        text_model = tf.keras.models.load_model(model_file)

    # Load image analysis model
    blob = bucket.blob('models/image_performance_v1.h5')
    with io.BytesIO(blob.download_as_bytes()) as model_file:
        image_model = tf.keras.models.load_model(model_file)

    return {
        'text': text_model,
        'image': image_model
    }

# Global models dictionary
MODELS = load_models()

# New endpoint for copy analysis
@app.route('/analyze/copy', methods=['POST'])
def analyze_copy():
    """Analyze marketing copy for performance potential"""
    # Validate OAuth token (same as in add endpoint)
    auth_header = request.headers.get('Authorization')
    if auth_header:
        token = auth_header.replace('Bearer ', '')
        token_data = get_token(token)

        if not token_data:
            return jsonify({"error": "Invalid token"}), 401

        # Convert string dates back to datetime objects if needed
        if isinstance(token_data['expires_at'], str):
            token_data['expires_at'] = datetime.fromisoformat(token_data['expires_at'])

        # Ensure we're comparing naive datetimes
        current_time = datetime.utcnow()
        if token_data['expires_at'] < current_time:
            return jsonify({"error": "Token expired"}), 401

    # Process the request
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400

    copy_text = data.get('copy')
    target_audience = data.get('audience', 'general')
    industry = data.get('industry', 'general')

    if not copy_text:
        return jsonify({"error": "Missing 'copy' parameter"}), 400

    # Preprocess text
    tokens = nltk.word_tokenize(copy_text.lower())

    # Extract features
    features = {
        'word_count': len(tokens),
        'avg_word_length': sum(len(word) for word in tokens) / len(tokens) if tokens else 0,
        'sentiment_score': analyze_sentiment(copy_text),
        'readability_score': calculate_readability(copy_text),
        'industry_relevance': calculate_industry_relevance(copy_text, industry)
    }

    # Make prediction using model
    input_vector = pd.DataFrame([features])
    prediction = MODELS['text'].predict(input_vector)

    # Process results
    scores = {
        'engagement_potential': float(prediction[0][0]),
        'conversion_potential': float(prediction[0][1]),
        'brand_alignment': float(prediction[0][2]),
        'emotional_impact': float(prediction[0][3])
    }

    # Generate recommendations
    recommendations = generate_copy_recommendations(copy_text, scores, target_audience)

    # Store analysis in Firestore for history
    if token_data:
        store_analysis_result(token_data['client_id'], 'copy', copy_text, scores, recommendations)

    return jsonify({
        "scores": scores,
        "recommendations": recommendations,
        "analyzed_text": copy_text
    })

# New endpoint for image analysis
@app.route('/analyze/image', methods=['POST'])
def analyze_image():
    """Analyze marketing image for performance potential"""
    # Token validation (same as above)
    # ...

    # Process the image file
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({"error": "Empty image file"}), 400

    # Process image
    img = Image.open(image_file)
    img = img.resize((224, 224))  # Resize for model input
    img_array = tf.keras.preprocessing.image.img_to_array(img)
    img_array = tf.expand_dims(img_array, 0)  # Create batch dimension

    # Make prediction
    prediction = MODELS['image'].predict(img_array)

    # Process results
    scores = {
        'visual_appeal': float(prediction[0][0]),
        'attention_grabbing': float(prediction[0][1]),
        'brand_consistency': float(prediction[0][2]),
        'conversion_potential': float(prediction[0][3])
    }

    # Generate recommendations
    recommendations = generate_image_recommendations(scores)

    # Store analysis result
    # ...

    return jsonify({
        "scores": scores,
        "recommendations": recommendations
    })

# Helper functions for analysis
def analyze_sentiment(text):
    """Analyze sentiment of text"""
    # Implementation using NLTK or similar
    pass

def calculate_readability(text):
    """Calculate readability score"""
    # Implementation using readability metrics
    pass

def calculate_industry_relevance(text, industry):
    """Calculate relevance to specific industry"""
    # Implementation using industry-specific keywords
    pass

def generate_copy_recommendations(text, scores, audience):
    """Generate recommendations for copy improvement"""
    recommendations = []

    if scores['engagement_potential'] < 0.5:
        recommendations.append("Consider using more engaging language to increase reader interest")

    # More recommendation logic

    return recommendations

def generate_image_recommendations(scores):
    """Generate recommendations for image improvement"""
    # Implementation
    pass

def store_analysis_result(client_id, analysis_type, content, scores, recommendations):
    """Store analysis result in Firestore"""
    if not db:
        logger.warning("Firestore not available, skipping result storage")
        return False

    try:
        doc_ref = db.collection('analysis_results').document()
        doc_ref.set({
            'client_id': client_id,
            'analysis_type': analysis_type,
            'content_hash': hash(str(content)),  # Store hash instead of full content
            'scores': scores,
            'recommendations': recommendations,
            'created_at': datetime.utcnow().isoformat()
        })
        return True
    except Exception as e:
        logger.error(f"Error storing analysis result in Firestore: {str(e)}")
        return False
```

### GPT Integration for Marketing Analysis

To integrate these advanced capabilities with a Custom GPT:

1. **Extended OpenAPI Schema**:

   - Update your OpenAPI schema to include the new endpoints
   - Define detailed request/response schemas for each analysis type
   - Include example requests for better GPT understanding

2. **Specialized GPT Instructions**:

   - Create a marketing-focused GPT with specific instructions
   - Define clear use cases and example prompts
   - Include knowledge about marketing principles and metrics

3. **Multi-modal Support**:

   - Configure the GPT to handle both text and image inputs
   - Set up file handling capabilities for image analysis
   - Create workflows that combine multiple analysis types

4. **Results Interpretation**:
   - Train the GPT to interpret analysis results meaningfully
   - Provide context for scores and recommendations
   - Suggest actionable next steps based on analysis

### Scaling Considerations

As your application grows in complexity:

1. **Performance Optimization**:

   - Implement caching for frequent analyses
   - Consider asynchronous processing for long-running analyses
   - Use Cloud Run's autoscaling for handling traffic spikes

2. **Advanced Security**:

   - Implement role-based access control for different analysis types
   - Add rate limiting to prevent abuse
   - Consider encryption for sensitive marketing data

3. **Infrastructure Evolution**:

   - For very complex workloads, consider migrating to Kubernetes
   - Implement a microservices architecture for independent scaling
   - Use Cloud Pub/Sub for event-driven processing

4. **Monitoring and Analytics**:
   - Implement detailed logging for analysis requests
   - Set up monitoring dashboards for system performance
   - Track usage patterns to guide feature development

By building on the OAuth and Firestore foundation established in this project, you can create sophisticated marketing analysis tools that integrate seamlessly with Custom GPTs, providing valuable insights while maintaining security and scalability.
