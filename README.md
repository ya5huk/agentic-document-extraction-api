# Agentic Document Extraction API

An AI-powered FastAPI service that autonomously discovers and downloads PDF documents from procurement websites (California eCal, SourceWell) using browser automation (Browser Use + Gemini/OpenAI), then uploads them to AWS S3.

> For my & project's progression story click [here](/claude-progression/Claude%20Code%20Progression.md).

## Features

- **AI-Powered Browser Automation**: Uses Browser Use library with Gemini Latest Flash model (default) or GPT-4o (if you choose so) for intelligent web navigation
- **Autonomous PDF Discovery**: Agent autonomously finds and downloads all PDFs from complex procurement websites
- **AWS S3 Integration**: Automatic upload of extracted PDFs to S3 with configurable bucket and prefix
- **RESTful API**: Simple HTTP API for triggering extraction tasks
- **Dockerized**: Fully containerized application ready for deployment
- **Multi-Model Support**: Switch between Gemini and OpenAI models via environment variable
- **Website Authentication**: Supports login-protected websites using credentials from environment variables

## Supported Platforms

- **California eProcurement (eCal)**: https://caleprocure.ca.gov
- **SourceWell Procurement Portal**: https://proportal.sourcewell-mn.gov

## Prerequisites

- **Docker & Docker Compose** (recommended) OR
- **Python 3.12+** (for local development)
- **AWS Account** with S3 access
- **API Keys, at least one of the following**:
  - Gemini API key (if using Gemini model) - Get from [Google AI Studio](https://aistudio.google.com/app/apikey)
  - OpenAI API key (if using OpenAI model) - Get from [OpenAI Platform](https://platform.openai.com/api-keys)

## Quick Start (Docker - Recommended)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd agentic-document-extraction-api
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your actual credentials
```

Required environment variables:

```bash
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here

# Gemini API Configuration (if using Gemini model)
GEMINI_API_KEY=your_gemini_api_key_here

# OpenAI API Configuration (if using OpenAI model)
OPENAI_API_KEY=your_openai_api_key_here

# (Optional - defaults to "gemini") Browser Model Selection
# Options: "gemini" or "openai"
BROWSER_MODEL=gemini

# Website Authentication (Optional - only needed for login-protected sites)
# For example - SourceWell Procurement Portal (https://proportal.sourcewell-mn.gov)
SITE_USERNAME=your_username_here
SITE_PASSWORD=your_password_here
```

### 3. Build and Run with Docker Compose

```bash
# Build and start the container
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build
```

The API will be available at: http://localhost:8000

### 4. Test the API

Visit the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Or test with curl:

```bash
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://caleprocure.ca.gov/event/0850/0000036230",
    "s3_bucket": "your-bucket-name",
    "s3_prefix": "procurement-docs/"
  }'
```

## Local Development (Without Docker)

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Configure Environment

Create `.env` file as described in Docker setup above.

### 3. Run the API

```bash
python main.py
```

The API will be available at: http://localhost:8000

## API Documentation

### Health Check

```http
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-11-22T10:30:00.000000"
}
```

### Extract PDFs

```http
POST /extract
```

**Request Body:**

```json
{
  "url": "https://caleprocure.ca.gov/event/0850/0000036230",
  "s3_bucket": "my-documents-bucket",
  "s3_prefix": "procurement-docs/"
}
```

**Parameters:**

- `url` (required): URL of the procurement page containing PDFs
- `s3_bucket` (required): AWS S3 bucket name for uploads
- `s3_prefix` (optional): S3 key prefix for organizing files (default: "")

**Response (Success):**

```json
{
  "status": "success",
  "message": "Successfully extracted and uploaded 3 PDF(s)",
  "files_uploaded": 3,
  "s3_uris": [
    "s3://my-documents-bucket/procurement-docs/RFP_Document.pdf",
    "s3://my-documents-bucket/procurement-docs/Specifications.pdf",
    "s3://my-documents-bucket/procurement-docs/Terms_Conditions.pdf"
  ]
}
```

**Response (No PDFs Found):**

```json
{
  "status": "success",
  "message": "No PDF files found at the provided URL",
  "files_uploaded": 0,
  "s3_uris": []
}
```

**Response (Error):**

```json
{
  "detail": "Failed to extract PDFs from https://...: [error details]"
}
```

## Usage Examples

### Example 1: California eCal Event

```bash
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://caleprocure.ca.gov/event/0850/0000036230",
    "s3_bucket": "procurement-documents",
    "s3_prefix": "ecal/event-0000036230/"
  }'
```

### Example 2: SourceWell Tender

```bash
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/68914ced-5e07-409d-b301-b10001e4bbb0/#Document",
    "s3_bucket": "procurement-documents",
    "s3_prefix": "sourcewell/tender-68914ced/"
  }'
```

### Example 3: Using Python Requests

```python
import requests

response = requests.post(
    "http://localhost:8000/extract",
    json={
        "url": "https://caleprocure.ca.gov/event/0850/0000036230",
        "s3_bucket": "my-bucket",
        "s3_prefix": "docs/"
    }
)

data = response.json()
print(f"Status: {data['status']}")
print(f"Files uploaded: {data['files_uploaded']}")
for uri in data['s3_uris']:
    print(f"  - {uri}")
```

## Switching AI Models

The service supports two AI models for browser automation:

### Gemini (Default)

```bash
# In .env file
BROWSER_MODEL=gemini
GEMINI_API_KEY=your_gemini_api_key_here
```

- **Model**: gemini-flash-latest
- **Provider**: Google AI
- **Pros**: Cost-effective, fast, good vision capabilities
- **API**: [Google AI Studio](https://aistudio.google.com/app/apikey)

### OpenAI

```bash
# In .env file
BROWSER_MODEL=openai
OPENAI_API_KEY=your_openai_api_key_here
```

- **Model**: gpt-4o
- **Provider**: OpenAI
- **Pros**: High accuracy, excellent reasoning
- **API**: [OpenAI Platform](https://platform.openai.com/api-keys)

Simply change `BROWSER_MODEL` in your `.env` file and restart the service.

## Docker Commands

```bash
# Build the image
docker-compose build

# Start the service
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down

# Rebuild and restart
docker-compose up --build

# Remove containers and volumes
docker-compose down -v
```

## Project Structure

```
agentic-document-extraction-api/
├── Dockerfile                  # Docker container configuration
├── docker-compose.yml          # Docker Compose orchestration
├── .dockerignore              # Docker build exclusions
├── .env.example               # Environment variable template
├── .gitignore                 # Git exclusions
├── requirements.txt           # Python dependencies
├── main.py                    # FastAPI application entry point
├── app/
│   ├── __init__.py           # App package initialization
│   └── models.py             # Pydantic request/response models
├── services/
│   ├── __init__.py           # Services package initialization
│   ├── browser_service.py    # Browser automation with AI
│   └── s3_service.py         # AWS S3 upload functionality
└── downloads/                 # Temporary PDF storage (auto-cleaned)
```

## Troubleshooting

### Issue: "Gemini API key is required"

**Solution**: Ensure `GEMINI_API_KEY` is set in your `.env` file if using `BROWSER_MODEL=gemini`.

### Issue: "OpenAI API key is required"

**Solution**: Ensure `OPENAI_API_KEY` is set in your `.env` file if using `BROWSER_MODEL=openai`.

### Issue: No PDFs downloaded

**Possible Causes**:

1. Website structure changed
2. PDFs are behind authentication (configure `SITE_USERNAME` and `SITE_PASSWORD`)
3. JavaScript-heavy page requires more time

**Solution**: Check logs for agent behavior, try running with `headless=False` for debugging.

### Issue: S3 upload fails

**Possible Causes**:

1. Invalid AWS credentials
2. Bucket doesn't exist
3. Insufficient S3 permissions

**Solution**:

- Verify AWS credentials in `.env`
- Ensure bucket exists and is accessible
- Check IAM permissions for S3 PutObject

### Issue: Docker container crashes

**Solution**:

- Check logs: `docker-compose logs api`
- Ensure sufficient memory (at least 2GB)
- Verify all environment variables are set

### Issue: Browser automation timeout

**Solution**:

- Increase timeout in browser service (default: 120 seconds)
- Check network connectivity
- Some websites may have anti-bot protection

## Testing

Test URLs verified to work:

**California eCal:**

- https://caleprocure.ca.gov/event/0850/0000036230
- https://caleprocure.ca.gov/event/2660/07A6065
- https://caleprocure.ca.gov/event/75021/0000035944

**SourceWell:**

- https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/68914ced-5e07-409d-b301-b10001e4bbb0/#Document
- https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/88c9616c-5685-4cae-b7fa-9c8ad726c38d/#Document
- https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/321c8f90-b43d-46ae-a8e4-41ac7587bc19/#Document

## Success Criteria Verification

- ✅ **Containerized API**: Fully Dockerized with docker-compose support
- ✅ **URL + S3 Parameters**: Accepts procurement URL and S3 configuration
- ✅ **Multi-Platform Support**: Successfully extracts from eCal and SourceWell
- ✅ **S3 Upload**: Uploads files with proper naming and organization
- ✅ **Accurate Responses**: Returns correct S3 URIs for all uploaded files
- ✅ **AI-Powered Automation**: Uses Gemini/OpenAI for intelligent navigation
- ✅ **Production Ready**: Health checks, logging, error handling

## Technologies Used

- **FastAPI**: Modern Python web framework
- **Browser Use**: AI-powered browser automation library
- **Gemini 2.0 Flash / GPT-4o**: Large language models for autonomous agents
- **Playwright**: Headless browser automation
- **boto3**: AWS SDK for S3 uploads
- **Pydantic**: Data validation and settings management
- **Docker**: Containerization and deployment

## License

This project is provided as-is for evaluation purposes.

## Support

For issues or questions, please check:

1. This README's troubleshooting section
2. API documentation at `/docs`
3. Application logs via `docker-compose logs -f`

---

**Created with Claude Code & Reviewed by Ilan Yashuk**
