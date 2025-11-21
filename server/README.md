# Server Structure

## Directory Structure

```
server/
├── api/              # API endpoints and routes
│   ├── __init__.py
│   └── routes.py     # FastAPI routes and app creation
├── core/             # Core business logic
│   ├── __init__.py
│   ├── chain.py      # LangChain integration for agent processing
│   └── orchestrator.py # Agent orchestrator
├── tools/            # AI agent tools
│   ├── __init__.py
│   ├── base.py       # Base tool class with LangChain
│   ├── filtering.py  # Email filtering tool
│   ├── newsletter.py # Newsletter management tool
│   ├── content_analysis.py # Content analysis tool
│   ├── auto_reply.py # Auto-reply generation tool
│   └── utils.py      # Tool utilities
├── services/         # External services
│   ├── __init__.py
│   ├── database.py   # PostgreSQL database service
│   └── embeddings.py # Embedding generation service
├── models/           # Data models
│   ├── __init__.py
│   └── schemas.py    # Pydantic schemas
├── config/           # Configuration
│   ├── __init__.py
│   └── settings.py   # Application settings
├── main.py           # Application entry point
└── README.md         # This file
```

## Module Descriptions

### API
- **routes.py** - FastAPI application setup, CORS configuration, and endpoint definitions

### Core
- **chain.py** - LangChain integration with prompt templates and structured output for reliable JSON parsing
- **orchestrator.py** - Coordinates tool execution, plans tool usage based on queries, manages tool dependencies

### Tools
- **base.py** - Base class for all AI tools with LangChain LLM integration
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

## LangChain Integration

The server now uses LangChain for:
- **Structured Output**: Reliable JSON parsing from LLM responses
- **Prompt Templates**: Reusable prompt templates for different tasks
- **Chain Composition**: Composable chains for complex workflows
- **Error Handling**: Fallback mechanisms when structured output fails

### Key Features
- `AgentChain` class manages LangChain LLM instances and prompt templates
- Tools can use shared LLM instances for efficiency
- Fallback to regular invocation if structured output fails
- All tools support both LangChain chains and direct tool execution

## Usage

The application is started via `main.py`, which creates the FastAPI app instance. All modules use proper imports and are organized for maintainability and testability.

## Dependencies

Key dependencies include:
- `fastapi` - Web framework
- `langchain` - LLM orchestration framework
- `langchain-google-genai` - Google Gemini integration
- `google-generativeai` - Direct Gemini API access (fallback)
- `psycopg` - PostgreSQL driver
- `pgvector` - Vector similarity search
