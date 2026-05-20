import anthropic

from app.agents.copywriter.schemas import EmailDraft
from app.leads.models import Lead
from app.tenants.models import Tenant

EMAIL_TOOL = {
    "name": "generate_email",
    "description": "Genera el subject y body del cold email personalizado",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": (
                    "Asunto del email. Máx 60 chars. "
                    "Sin signos de exclamación ni mayúsculas. Sin clickbait."
                ),
            },
            "body": {
                "type": "string",
                "description": (
                    "Cuerpo del email. Máx 150 palabras. "
                    "Primera línea específica al lead. Un solo CTA al final."
                ),
            },
            "personalization_notes": {
                "type": "string",
                "description": (
                    "Qué señal o contexto específico usaste para personalizar. "
                    "Para auditoría interna."
                ),
            },
        },
        "required": ["subject", "body", "personalization_notes"],
    },
}


class CopywriterAgent:

    def __init__(self) -> None:
        self.claude = anthropic.Anthropic()

    def _build_system_prompt(self, tenant: Tenant) -> str:
        """
        Este prompt es CACHEADO — contiene todo lo que no cambia entre leads:
        voz del tenant, ejemplos exitosos, reglas, propuesta de valor.
        Se construye una vez y se reutiliza para todos los leads del tenant.
        """
        config = tenant.icp_config or {}
        voice = config.get("voice_guidelines", "Profesional pero cercano. Directo al punto.")
        value = config.get("value_proposition", "")
        examples_raw = config.get("successful_emails", [])

        examples_formatted = ""
        if examples_raw:
            examples_formatted = "\n\nEmails que han funcionado bien:\n"
            for i, ex in enumerate(examples_raw[:3], 1):  # máx 3 ejemplos
                examples_formatted += f"\nEjemplo {i}:\n"
                examples_formatted += f"Subject: {ex.get('subject', '')}\n"
                examples_formatted += f"Body: {ex.get('body', '')}\n"

        return f"""Eres el copywriter de {tenant.name}. Tu objetivo es escribir cold emails\
 que consigan reuniones B2B — no que suenen bonitos.

VOZ Y ESTILO:
{voice}

PROPUESTA DE VALOR:
{value}
{examples_formatted}

REGLAS ABSOLUTAS (violarlas = email rechazado):
- Máximo 150 palabras en el body
- La primera línea DEBE ser específica al lead (nombre, empresa, o señal real)
- Un solo CTA al final — sin ambigüedad sobre qué hacer
- No menciones IA, automatización, ni que esto es outreach masivo
- No uses "espero que estés bien", "me permito escribirte", ni fórmulas vacías
- Subject: máx 60 chars, sin signos de exclamación, sin mayúsculas innecesarias
- No uses "estimado/a" ni formalismos excesivos
- Si hay una señal temporal relevante (funding, hiring, noticia), úsala en la primera línea

Usa el tool generate_email para entregar tu respuesta."""

    async def run(
        self,
        lead: Lead,
        tenant: Tenant,
        rag_context: str,
        previous_issues: list[str] | None = None,
    ) -> EmailDraft:

        system_prompt = self._build_system_prompt(tenant)

        # Construir el mensaje de usuario (cambia por lead — NO cacheado)
        signals_text = ""
        if lead.research_ctx:
            signals = lead.research_ctx.get("signals", [])
            if signals:
                signals_text = "\nSeñales encontradas:\n" + "\n".join(
                    f"- [{s['type'].upper()}] {s['description']} — {s.get('relevance', '')}"
                    for s in signals[:3]
                )

        retry_feedback = ""
        if previous_issues:
            retry_feedback = "\n\n⚠️ PROBLEMAS DEL INTENTO ANTERIOR (corrige estos):\n" + \
                             "\n".join(f"- {issue}" for issue in previous_issues)

        rag_section = ""
        if rag_context:
            rag_section = f"\n\nCONTEXTO DE NUESTRA BASE DE CONOCIMIENTO:\n{rag_context}"

        user_message = f"""Escribe un cold email para este prospecto.

LEAD:
- Nombre: {lead.full_name or 'Sin nombre'}
- Cargo: {lead.title}
- Empresa: {lead.company}
- Email: {lead.email}

RESUMEN DE INVESTIGACIÓN:
{lead.research_ctx.get('summary', 'Sin contexto disponible')}
{signals_text}
{rag_section}
{retry_feedback}"""

        response = self.claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},  # CACHING aquí
                }
            ],
            messages=[{"role": "user", "content": user_message}],
            tools=[EMAIL_TOOL],
            tool_choice={"type": "tool", "name": "generate_email"},
        )

        tool_block = next(b for b in response.content if b.type == "tool_use")
        return EmailDraft(**tool_block.input)
