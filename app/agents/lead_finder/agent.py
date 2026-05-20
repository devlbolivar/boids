import anthropic
import json
from app.campaigns.schemas import ICPConfig
from app.integrations.apollo.client import ApolloClient
from app.integrations.apollo.icp_mapper import icp_to_apollo_filters

APOLLO_SEARCH_TOOL = {
    "name": "search_apollo",
    "description": (
        "Busca contactos B2B en Apollo.io según los filtros del ICP. "
        "Úsala cuando necesites encontrar leads que coincidan con el perfil de cliente ideal. "
        "Retorna una lista de contactos con email, nombre, cargo y empresa."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "person_titles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Cargos objetivo. Ej: ['CTO', 'VP Engineering']",
            },
            "person_locations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Países o ciudades. Ej: ['Chile', 'Colombia']",
            },
            "organization_industry_tag_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Industrias. Ej: ['SaaS', 'Fintech']",
            },
            "organization_num_employees_ranges": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Rango de empleados. Ej: ['51,200']",
            },
            "q_keywords": {
                "type": "string",
                "description": "Keywords de tech stack o señales. Ej: 'AWS React Python'",
            },
            "per_page": {
                "type": "integer",
                "description": "Resultados por página. Máximo 25.",
                "default": 25,
            },
        },
        "required": [],
    },
}

SYSTEM_PROMPT = """Eres el Lead Finder de Boids, un sistema de prospección B2B.
Tu trabajo es buscar contactos en Apollo que coincidan con el ICP dado.

Instrucciones:
1. Usa el tool search_apollo con los filtros más relevantes del ICP
2. Si el ICP tiene múltiples títulos, inclúyelos todos
3. Prioriza la calidad sobre la cantidad — es mejor 25 leads precisos que 100 genéricos
4. Siempre incluye ubicación si está en el ICP

Responde SOLO usando el tool. No expliques nada."""


class LeadFinderAgent:

    def __init__(self, apollo_client: ApolloClient):
        self.apollo = apollo_client
        self.claude = anthropic.Anthropic()

    async def run(self, icp: ICPConfig, max_leads: int = 100) -> list[dict]:
        """
        Usa Claude Haiku para interpretar el ICP y construir la query óptima de Apollo.
        Retorna lista de contactos raw de Apollo.
        """
        base_filters = icp_to_apollo_filters(icp)

        user_message = (
            f"ICP a prospectar:\n{icp.model_dump_json(indent=2)}\n\n"
            f"Filtros base pre-calculados (úsalos como referencia):\n"
            f"{json.dumps(base_filters, indent=2)}\n\n"
            f"Busca los primeros {min(max_leads, 25)} leads más relevantes."
        )

        response = self.claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=[APOLLO_SEARCH_TOOL],
            tool_choice={"type": "tool", "name": "search_apollo"},
        )

        tool_block = next(b for b in response.content if b.type == "tool_use")
        apollo_filters = tool_block.input

        result = await self.apollo.search_people(
            filters=apollo_filters,
            per_page=min(max_leads, 25),
        )

        return result.get("people", [])
