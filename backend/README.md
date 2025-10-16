# Backend

FastAPI backend for the AI Xiaohongshu project. The service exposes foundational APIs and a
health endpoint that upstream services and infrastructure checks can use.

## Getting started

1. Create a virtualenv: `python -m venv .venv && source .venv/bin/activate`
2. Install dependencies: `pip install -e .[dev]`
3. Run the API: `uvicorn app.main:app --reload`

The default application serves a `/health` endpoint that should return `{"status":"ok"}`.

## Running tests

Execute `pytest` from the `backend/` directory to run the asynchronous integration test suite.

## Configuration

Set the following environment variables before hitting Ark endpoints (e.g. in a `.env` file):

| Variable | Description |
| --- | --- |
| `ARK_API_KEY` | Ark API key (alternatively configure `ARK_AK` + `ARK_SK`) |
| `ARK_BASE_URL` | Optional override for the Ark API base URL |
| `ARK_PROMPT_MODEL` | Endpoint ID for prompt JSON generation |
| `ARK_IMAGE_MODEL` | Endpoint ID for image generation |
| `ARK_IMAGE_SIZE` | Output size for generated images (default `1024x1024`) |

## Marketing collage workflow

POST `/api/marketing/collage` with a multipart form containing:

- `prompt`: text brief describing the campaign
- `count`: number of prompt/image pairs to produce
- `images`: 1~M reference images

The endpoint returns a JSON payload with generated prompt variants and image metadata.

The integration uses `volcengine-python-sdk[ark]` and will raise `502` responses if Ark returns
invalid data or the prompt count mismatches your request.
