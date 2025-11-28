"""
Test Configuration
==================

Pytest fixtures for Civium tests.
"""

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Set test environment
os.environ["ENVIRONMENT"] = "testing"
os.environ["BLOCKCHAIN_MODE"] = "mock"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Use asyncio backend for async tests."""
    return "asyncio"


@pytest_asyncio.fixture
async def regulatory_intelligence_client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client for Regulatory Intelligence Service."""
    from services.regulatory_intelligence.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def compliance_graph_client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client for Compliance Graph Service."""
    from services.compliance_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def entity_assessment_client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client for Entity Assessment Service."""
    from services.entity_assessment.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def sample_entity_data() -> dict[str, Any]:
    """Sample entity data for tests."""
    return {
        "name": "Test Corporation",
        "entity_type": "corporation",
        "sectors": ["TECH", "FINANCE"],
        "jurisdictions": ["US", "EU"],
        "size": "large",
        "external_id": "LEI-TEST-123",
        "metadata": {"industry_code": "5415"},
    }


@pytest.fixture
def sample_regulation_data() -> dict[str, Any]:
    """Sample regulation data for tests."""
    return {
        "id": "REG-TEST-001",
        "name": "Test Regulation",
        "short_name": "TREG",
        "jurisdiction": "US",
        "jurisdictions": ["US"],
        "sectors": ["TECH"],
        "effective_date": "2024-01-01",
        "rml": {"version": "1.0"},
    }


@pytest.fixture
def sample_requirement_data() -> dict[str, Any]:
    """Sample requirement data for tests."""
    return {
        "id": "REQ-TEST-001",
        "regulation_id": "REG-TEST-001",
        "article_ref": "Section 1.1",
        "natural_language": "Entities must implement reasonable security measures.",
        "formal_logic": "FORALL e: secure(e) IFF has_security_measures(e)",
        "tier": "basic",
        "verification_method": "self_attestation",
    }


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Generate test authentication headers."""
    from shared.auth import create_access_token

    token = create_access_token({
        "sub": "test-user-id",
        "email": "test@civium.io",
        "roles": ["user", "admin"],
    })
    return {"Authorization": f"Bearer {token}"}

