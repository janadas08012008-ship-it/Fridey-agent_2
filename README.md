# Fridey

Fridey is a mobile-friendly AI assistant starter with a FastAPI backend, task history, and a responsive web interface.

## Features in this starter
- Chat through a configured OpenAI API key
- Persistent task records in SQLite (best for local/single-instance testing)
- Responsive dashboard for phone and desktop
- Health endpoint for Render
- Secrets configured through environment variables

## Deploy to Render
1. Create a new **Web Service** from this repository.
2. Use the included `render.yaml`, or set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
3. Add `OPENAI_API_KEY` in Render Environment. Never commit API keys.
4. Open the deployed URL.

## Important
This is a starter foundation, not yet a fully autonomous agent. Web research, GitHub write actions, ZIP processing, scheduled background workers, user authentication, and production-grade PostgreSQL persistence still need to be implemented and tested before public use. Do not expose an unauthenticated instance publicly with a real API key.
