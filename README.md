# Creative Effectiveness Prediction Machine (CEPM) for SCUK

The Creative Effectiveness Prediction Machine (CEPM) is a specialized system designed for charities to analyze and predict the effectiveness of marketing assets. By leveraging ChatGPT's multimodal capabilities and OAuth infrastructure, the CEPM helps charities understand donor motivations, predict ad effectiveness, and optimize marketing strategies through data-driven insights.

## Overview

This implementation provides a functional prototype that focuses on:

- Analyzing marketing assets (images and copy) using ChatGPT's multimodal capabilities
- Scoring effectiveness based on predefined donor personas
- Providing actionable recommendations to improve marketing materials
- Storing analysis history for comparison and learning

## Installation

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
   # Create a service account key file
   gcloud iam service-accounts keys create key.json \
     --iam-account=flask-addition-service@YOUR_PROJECT_ID.iam.gserviceaccount.com

   # Set environment variable to point to the key file
   export GOOGLE_APPLICATION_CREDENTIALS=./key.json
   ```

4. Run the application:
   ```bash
   python server.py
   ```

## Usage

### Asset Analysis

1. Upload marketing assets (images or copy) through the ChatGPT interface
2. Specify target persona and campaign context
3. Receive detailed analysis with effectiveness scores and recommendations
4. Compare with previous analyses and make improvements

### API Endpoints

The system provides several API endpoints:

- `/analyze/image` - Analyze image-based marketing assets
- `/analyze/copy` - Analyze text-based marketing assets
- `/personas` - Manage donor personas
- `/analysis/history` - Retrieve previous analyses

## Features

- **Multimodal Analysis**: Evaluates both visual and textual marketing materials
- **Persona-Based Scoring**: Tailors analysis to specific donor personas
- **Recommendation Engine**: Provides actionable suggestions for improvement
- **OAuth Authentication**: Secures all API endpoints
- **Firestore Integration**: Maintains analysis history and persona definitions
- **ChatGPT Integration**: Leverages AI for natural language interaction

## Architecture

The CEPM follows this high-level architecture:

1. **Input Layer (ChatGPT)**: Users upload assets through ChatGPT interface
2. **Processing Layer (Flask Server)**: Applies scoring algorithms based on predefined personas
3. **Storage Layer (Firestore)**: Stores persona definitions and analysis history
4. **Authentication Layer (OAuth)**: Secures all API endpoints

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 