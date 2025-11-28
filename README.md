# CIVIUM: Recursive Self-Improving Global Compliance World Engine

[![CI](https://github.com/your-org/civium/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/civium/actions)
[![codecov](https://codecov.io/gh/your-org/civium/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/civium)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌍 Overview

Civium is a **planetary-scale compliance intelligence system** that:

- **Ingests** and interprets regulatory requirements from all global jurisdictions
- **Models** compliance obligations as a queryable knowledge graph
- **Verifies** entity compliance through cryptographic proofs and automated audits
- **Self-improves** through reinforcement learning from compliance outcomes
- **Provides** real-time compliance guidance to governments, enterprises, and individuals

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CIVIUM WORLD ENGINE                         │
├─────────────────────────────────────────────────────────────────┤
│  PRESENTATION LAYER                                             │
│  ├── Entity Portal (Compliance Self-Service)                    │
│  ├── Regulator Dashboard                                        │
│  └── Public Transparency Portal                                 │
├─────────────────────────────────────────────────────────────────┤
│  API GATEWAY (GraphQL + REST | Auth | Rate Limiting)            │
├─────────────────────────────────────────────────────────────────┤
│  CORE SERVICES                                                  │
│  ├── Regulatory Intelligence Service (NLP + Ingestion)          │
│  ├── Compliance Graph Engine (Neo4j Knowledge Graph)            │
│  ├── Entity Assessment Service (Scoring + Tiers)                │
│  ├── Verification Service (ZK Proofs + Audit)                   │
│  └── Real-Time Monitoring Service (Kafka Streams)               │
├─────────────────────────────────────────────────────────────────┤
│  SELF-IMPROVEMENT ENGINE                                        │
│  ├── Model Training Pipeline                                    │
│  ├── Performance Profiler                                       │
│  └── Meta-Learning Code Generator                               │
├─────────────────────────────────────────────────────────────────┤
│  DATA LAYER                                                     │
│  ├── Neo4j (Compliance Graph)                                   │
│  ├── MongoDB (Regulatory Documents)                             │
│  ├── PostgreSQL (Entity Data)                                   │
│  ├── Redis (Cache/Sessions)                                     │
│  ├── InfluxDB (Time-Series Metrics)                             │
│  └── Pinecone/Weaviate (Vector Search)                          │
├─────────────────────────────────────────────────────────────────┤
│  BLOCKCHAIN LAYER                                               │
│  ├── Smart Contracts (Audit Trail)                              │
│  ├── DID Registry                                               │
│  └── Verifiable Credentials                                     │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
civium/
├── services/                    # Microservices
│   ├── regulatory-intelligence/ # NLP + Document Ingestion
│   ├── compliance-graph/        # Neo4j Graph Engine
│   ├── entity-assessment/       # Entity Management + Scoring
│   ├── verification/            # ZK Proofs + Blockchain Audit
│   └── monitoring/              # Real-Time Event Processing
├── shared/                      # Shared Libraries
│   ├── auth/                    # Authentication & Authorization
│   ├── config/                  # Configuration Management
│   ├── database/                # Database Clients
│   ├── llm/                     # LLM Provider Abstraction
│   ├── blockchain/              # Blockchain Abstraction Layer
│   ├── logging/                 # Structured Logging
│   └── models/                  # Shared Pydantic Models
├── infrastructure/              # IaC & DevOps
│   ├── docker/                  # Docker Configurations
│   ├── k8s/                     # Kubernetes Manifests
│   └── terraform/               # Cloud Infrastructure
├── docs/                        # Documentation
│   ├── adr/                     # Architecture Decision Records
│   ├── api/                     # API Documentation
│   └── guides/                  # Setup & Development Guides
├── tests/                       # Integration Tests
├── scripts/                     # Utility Scripts
├── docker-compose.yml           # Local Development Stack
├── pyproject.toml               # Python Project Configuration
└── .github/                     # GitHub Actions CI/CD
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Docker Desktop
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/your-org/civium.git
cd civium

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Start infrastructure
docker-compose up -d

# Run database migrations
python scripts/init_databases.py

# Start services (development)
python -m services.regulatory_intelligence
python -m services.compliance_graph
python -m services.entity_assessment
```

### Verify Installation

```bash
# Check all containers are healthy
docker-compose ps

# Run health checks
curl http://localhost:8001/health  # Regulatory Intelligence
curl http://localhost:8002/health  # Compliance Graph
curl http://localhost:8003/health  # Entity Assessment

# Run test suite
pytest --cov=shared --cov=services
```

## 🔧 Configuration

All configuration is managed through environment variables. See `.env.example` for all options.

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Deployment environment | `development` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `LLM_PROVIDER` | Primary LLM provider | `claude` |
| `BLOCKCHAIN_MODE` | Blockchain operation mode | `mock` |

## 📚 Documentation

- [Architecture Decision Records](docs/adr/)
- [API Reference](docs/api/)
- [Development Guide](docs/guides/development.md)
- [Deployment Guide](docs/guides/deployment.md)

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit

# Integration tests
pytest tests/integration

# Full test suite with coverage
pytest --cov --cov-report=html
```

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Follow [Conventional Commits](https://www.conventionalcommits.org/)
3. Ensure tests pass: `pytest`
4. Ensure linting passes: `ruff check . && mypy .`
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

**Version:** 0.1.0  
**Phase:** 1 - Foundation  
**Status:** In Development

