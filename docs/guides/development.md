# Development Guide

This guide covers setting up a local development environment for Civium.

## Prerequisites

- **Python 3.12+** - Core language
- **Docker Desktop** - For running databases
- **Git** - Version control
- **Node.js 18+** - For ZK circuit compilation (optional)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/civium.git
cd civium
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### 3. Configure Environment

```bash
# Copy environment template
cp env.example .env

# Edit .env with your settings
# At minimum, set your API keys if using LLM features
```

### 4. Start Infrastructure

```bash
# Start all databases
docker-compose up -d

# Check all containers are healthy
docker-compose ps

# Initialize databases
python scripts/init_databases.py
```

### 5. Run Services

```bash
# Run individual services
python -m services.regulatory_intelligence
python -m services.compliance_graph
python -m services.entity_assessment
python -m services.verification
python -m services.monitoring

# Or use tmux/separate terminals for each
```

## Development Workflow

### Code Style

We use **Ruff** for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Type Checking

We enforce strict typing with **mypy**:

```bash
mypy shared services
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=shared --cov=services

# Run specific test file
pytest tests/unit/test_auth.py

# Run tests matching pattern
pytest -k "test_entity"
```

### Pre-commit Hooks

Install pre-commit hooks to ensure code quality:

```bash
pre-commit install
pre-commit install --hook-type commit-msg

# Run manually on all files
pre-commit run --all-files
```

## Project Structure

```
civium/
├── services/                # Microservices
│   ├── regulatory_intelligence/
│   ├── compliance_graph/
│   ├── entity_assessment/
│   ├── verification/
│   └── monitoring/
├── shared/                  # Shared libraries
│   ├── auth/               # Authentication
│   ├── config/             # Configuration
│   ├── database/           # Database clients
│   ├── llm/                # LLM providers
│   ├── blockchain/         # Blockchain
│   ├── logging/            # Logging
│   ├── models/             # Pydantic models
│   └── zk/                 # ZK-SNARK
├── tests/                  # Test suites
├── infrastructure/         # IaC
├── docs/                   # Documentation
└── scripts/                # Utility scripts
```

## Service Architecture

Each service follows a consistent pattern:

```
service/
├── __init__.py
├── main.py              # FastAPI app & lifespan
├── routes/              # API route handlers
│   ├── __init__.py
│   └── *.py
├── services/            # Business logic
│   ├── __init__.py
│   └── *.py
└── models/              # Service-specific models
    ├── __init__.py
    └── *.py
```

## Database Connections

### PostgreSQL
```python
from shared.database.postgres import PostgresClient

engine = PostgresClient.get_engine()
async with engine.begin() as conn:
    result = await conn.execute(text("SELECT 1"))
```

### Neo4j
```python
from shared.database.neo4j import Neo4jClient

driver = Neo4jClient.get_driver()
async with driver.session() as session:
    result = await session.run("MATCH (n) RETURN count(n)")
```

### MongoDB
```python
from shared.database.mongodb import MongoDBClient

db = MongoDBClient.get_database()
collection = db["regulations"]
doc = await collection.find_one({"id": "..."})
```

## Adding a New Endpoint

1. Create route handler in `routes/`:
```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/{id}")
async def get_item(id: str):
    return {"id": id}
```

2. Register in `main.py`:
```python
from .routes import new_route

app.include_router(
    new_route.router,
    prefix="/api/v1/items",
    tags=["Items"],
)
```

3. Add tests in `tests/`:
```python
async def test_get_item(client):
    response = await client.get("/api/v1/items/123")
    assert response.status_code == 200
```

## Environment Variables

See `env.example` for all available configuration options. Key variables:

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT` | dev/staging/production |
| `DEBUG` | Enable debug mode |
| `LOG_LEVEL` | INFO/DEBUG/WARNING |
| `LLM_PROVIDER` | claude/openai/ollama |
| `BLOCKCHAIN_MODE` | mock/testnet/mainnet |

## Troubleshooting

### Database Connection Issues

```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs postgres
docker-compose logs neo4j

# Restart services
docker-compose restart
```

### Import Errors

Ensure you've installed in editable mode:
```bash
pip install -e ".[dev]"
```

### Test Failures

Run with verbose output:
```bash
pytest -v --tb=long
```

