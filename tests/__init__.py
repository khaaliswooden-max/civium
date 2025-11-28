"""
CIVIUM Test Suite
=================

Test organization:
- tests/unit/          - Unit tests (no external dependencies)
- tests/integration/   - Integration tests (require databases)
- tests/e2e/          - End-to-end tests (full stack)

Run tests:
    pytest                          # All tests
    pytest tests/unit               # Unit tests only
    pytest -m "not integration"     # Skip integration tests
    pytest --cov=shared            # With coverage
"""

