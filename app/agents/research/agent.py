import anthropic
from datetime import datetime, timezone
from app.leads.models import Lead
from app.agents.research.schemas import ResearchContext

RESEARCH_OUTPUT_TOOL = {
    "name": "save_research",
    "description": "Guarda el contexto de investigación del prospecto",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Por qué este lead es un buen prospecto. Máximo 500 caracteres. Sé específico — no genérico."
            },
            "signals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type":        {"type": "string",
                                        "enum": ["hiring", "funding", "expansion",
                                                 "tech_stack", "news", "pain_point", "award"]},
                        "description": {"type": "string"},
                        "relevance":   {"type": "string"},
                        "date":        {"type": "string"}
                    },
                    "required": ["type", "description", "relevance"]
                },
                "maxItems": 5
            },
            "pain_points": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 3,
                "description": "Dolores inferidos de las señales encontradas"
            },
            "company_context": {
                "type": "object",
                "properties": {
                    "website":       {"type": "string"},
                    "founded":       {"type": "string"},
                    "size_estimate": {"type": "string"},
                    "recent_news":   {"type": "string"},
                    "description":   {"type": "string"}
                }
            },
            "data_quality": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "high: 3+ señales concretas. medium: 1-2 señales. low: poco contexto."
            },
            "limited_data": {
                "type": "boolean",
                "description": "True si no encontraste suficiente información útil"
            }
        },
        "required": ["summary", "signals", "pain_points", "company_context",
                     "data_quality", "limited_data"]
    }
}

SYSTEM_PROMPT = """Eres el Research Agent de Boids, un sistema de prospección B2B.

Tu trabajo es investigar prospectos para que el Copywriter pueda escribir
emails altamente personalizados. La calidad de tu investigación determina
directamente si el prospecto responde o no.

Qué buscar (en orden de prioridad):
1. Señales de timing — ¿por qué AHORA es el momento de contactarlos?
   - Contrataciones recientes (job posts relevantes)
   - Funding reciente (Series A/B, noticias de inversión)
   - Expansión (nuevas oficinas, nuevos mercados)
2. Tech stack — ¿qué tecnologías usan? ¿hay compatibilidad o gap con nuestra solución?
3. Noticias recientes (últimos 6 meses) — cualquier evento empresarial relevante
4. Dolores inferibles — ¿qué problema probable tiene alguien en este cargo, en esta empresa?

Cómo buscar:
- Busca "{nombre} {empresa}" para contexto del individuo
- Busca "{empresa} funding OR hiring OR expansion 2025"
- Busca "{empresa} tech stack OR engineering"
- Busca el sitio web de la empresa si no lo conoces
- Si no encuentras nada útil, reporta limited_data=true — no inventes

Formato del output:
- summary: específico y basado en evidencia. NO genérico.
  MAL: "Empresa de tecnología con potencial de crecimiento."
  BIEN: "Levantaron $3M en enero, están contratando 2 data engineers — señal de que están escalando infra."
- signals: máximo 5, solo los más relevantes y accionables
- pain_points: dolores INFERIDOS de las señales, no inventados

Usa el tool save_research para entregar tu respuesta."""


class ResearchAgent:

    def __init__(self):
        self.claude = anthropic.Anthropic()

    async def run(self, lead: Lead) -> ResearchContext:
        user_message = (
            f"Investiga este prospecto:\n\n"
            f"Nombre: {lead.full_name}\n"
            f"Cargo: {lead.title}\n"
            f"Empresa: {lead.company}\n"
            f"Email: {lead.email}\n\n"
            f"Busca contexto relevante para personalizar un cold email B2B."
        )

        response = self.claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=[
                {"type": "web_search_20250305", "name": "web_search"},
                RESEARCH_OUTPUT_TOOL
            ],
        )

        save_block = self._extract_save_block(response.content)

        if not save_block:
            return ResearchContext(
                summary=f"Sin contexto encontrado para {lead.full_name} en {lead.company}",
                limited_data=True,
                data_quality="low",
                researched_at=datetime.now(timezone.utc).isoformat()
            )

        ctx_data = save_block.input
        ctx_data["researched_at"] = datetime.now(timezone.utc).isoformat()
        return ResearchContext(**ctx_data)

    def _extract_save_block(self, content: list) -> object | None:
        save_blocks = [
            block for block in content
            if hasattr(block, "type")
            and block.type == "tool_use"
            and block.name == "save_research"
        ]
        return save_blocks[-1] if save_blocks else None
