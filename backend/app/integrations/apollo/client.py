import httpx
from app.config import settings

APOLLO_BASE_URL = "https://api.apollo.io/v1"


class ApolloClient:
    """
    Wrapper sobre Apollo API v1.
    Si el tenant tiene su propia API key en api_keys_enc, se usa esa.
    Si no, usa la key global de Boids (plan compartido).
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.APOLLO_API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }

    async def search_people(self, filters: dict, page: int = 1, per_page: int = 25) -> dict:
        """
        Endpoint: POST /mixed_people/search
        Retorna: { people: [...], pagination: {...} }
        """
        payload = {
            **filters,
            "page": page,
            "per_page": per_page,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{APOLLO_BASE_URL}/mixed_people/search",
                json=payload,
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json()

    async def enrich_person(self, email: str) -> dict | None:
        """
        Endpoint: POST /people/match
        Enriquece un contacto existente con más datos.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{APOLLO_BASE_URL}/people/match",
                json={"email": email, "reveal_personal_emails": False},
                headers=self.headers,
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json().get("person")
