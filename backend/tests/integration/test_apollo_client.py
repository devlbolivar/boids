import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("APOLLO_API_KEY"),
    reason="Requiere APOLLO_API_KEY real — solo corre en entorno con credenciales",
)


@pytest.mark.slow
async def test_apollo_search_returns_results():
    """Test con Apollo real. Solo corre cuando APOLLO_API_KEY está en env."""
    from app.integrations.apollo.client import ApolloClient

    client = ApolloClient()
    result = await client.search_people(
        filters={
            "person_titles": ["CTO"],
            "person_locations": ["Chile"],
        },
        per_page=5,
    )

    assert "people" in result
    assert len(result["people"]) > 0
    for person in result["people"]:
        assert "email" in person or "email_addresses" in person
