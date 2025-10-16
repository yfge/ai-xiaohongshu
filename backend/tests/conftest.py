import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Force anyio-based tests to run with asyncio backend only."""

    return "asyncio"
