# Server Structure

## Directory Structure

```
server/
├── api/              # API endpoints and routes
│   └── routes.py     # FastAPI routes and app creation
├── core/             # Core business logic
│   └── orchestrator.py # Agent orchestrator
├── tools/            # AI agent tools
│   ├── base.py       # Base tool class
│   ├── filtering.py  # Email filtering tool
│   ├── newsletter.py # Newsletter management tool
│   ├── content_analysis.py # Content analysis tool
│   ├── auto_reply.py # Auto-reply generation tool
│   └── utils.py      # Tool utilities
├── services/         # External services
│   ├── database.py   # PostgreSQL database service
│   └── embeddings.py # Embedding generation service
├── models/           # Data models
│   └── schemas.py    # Pydantic schemas
├── config/           # Configuration
│   └── settings.py   # Application settings
└── main.py           # Application entry point
```

## Module Descriptions

### API

- **routes.py** - FastAPI application setup, CORS configuration, and endpoint definitions

### Core

- **orchestrator.py** - Coordinates tool execution, plans tool usage based on queries, manages tool dependencies

### Tools

- **base.py** - Base class for all AI tools with Gemini model integration
- **filtering.py** - Categorizes and prioritizes emails
- **newsletter.py** - Manages newsletters and subscriptions
- **content_analysis.py** - Extracts key information, tasks, and deadlines
- **auto_reply.py** - Generates personalized auto-reply templates
- **utils.py** - Utility functions for formatting messages

### Services

- **database.py** - PostgreSQL connection pool, table initialization, email storage, metrics retrieval
- **embeddings.py** - Vector embedding generation using Gemini API

### Models

- **schemas.py** - Pydantic models for API requests and responses

### Config

- **settings.py** - Application settings loaded from environment variables

## Usage

The application is started via `main.py`, which creates the FastAPI app instance. All modules use proper imports and are organized for maintainability and testability.
