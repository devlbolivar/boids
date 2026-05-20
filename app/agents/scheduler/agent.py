import anthropic
import logging

from app.agents.scheduler.intent_classifier import IntentClassifier
from app.leads.models import Lead
from app.tenants.models import Tenant

logger = logging.getLogger(__name__)

BOOKING_TOOL = {
    "name": "book_meeting",
    "description": "Agenda la reunión en el horario seleccionado y genera el mensaje de confirmación",
    "input_schema": {
        "type": "object",
        "properties": {
            "selected_slot_start": {
                "type": "string",
                "description": "ISO datetime del slot seleccionado (de los disponibles)",
            },
            "selected_slot_end": {
                "type": "string",
                "description": "ISO datetime fin del slot",
            },
            "confirmation_message": {
                "type": "string",
                "description": (
                    "Mensaje de reply para confirmar la reunión al prospecto. "
                    "Breve, amigable, confirma fecha y hora, incluye link de Meet."
                ),
            },
        },
        "required": ["selected_slot_start", "selected_slot_end", "confirmation_message"],
    },
}

DECLINE_TOOL = {
    "name": "handle_negative",
    "description": "Maneja un reply negativo con una respuesta cortés",
    "input_schema": {
        "type": "object",
        "properties": {
            "response_message": {
                "type": "string",
                "description": (
                    "Mensaje breve y respetuoso agradeciendo la respuesta "
                    "y dejando la puerta abierta para el futuro."
                ),
            }
        },
        "required": ["response_message"],
    },
}


class SchedulerAgent:

    def __init__(self):
        self.claude = anthropic.Anthropic()
        self.classifier = IntentClassifier()

    async def process_reply(
        self,
        reply_body: str,
        lead: Lead,
        tenant: Tenant,
        thread_id: str = "",
    ) -> dict:
        """
        Proceso completo:
        1. Clasificar intención
        2. Si positivo → book meeting
        3. Si pregunta → generar respuesta (también ofrece reunión)
        4. Si negativo → respuesta de cierre cortés
        5. Si auto_reply → ignorar
        """
        # Paso 1: Clasificar intención
        classification = await self.classifier.classify(reply_body)
        intent = classification["intent"]
        confidence = classification["confidence"]

        logger.info(
            "Reply intent=%s confidence=%.2f | lead=%s", intent, confidence, lead.id
        )

        result: dict = {
            "intent": intent,
            "confidence": confidence,
            "key_phrase": classification.get("key_phrase", ""),
            "action": None,
            "message": None,
            "meeting": None,
        }

        if intent == "auto_reply":
            result["action"] = "ignored"
            return result

        if intent == "negative":
            result["action"] = "rejected"
            result["message"] = await self._generate_decline_response(
                reply_body, lead, tenant
            )
            return result

        if intent in ("positive", "question"):
            # Para ambos, intentamos ofrecer reunión
            # Si es question, el mensaje explicará el producto también
            meeting_result = await self._try_book_meeting(
                reply_body, lead, tenant, intent
            )
            result.update(meeting_result)

        return result

    async def _try_book_meeting(
        self,
        reply_body: str,
        lead: Lead,
        tenant: Tenant,
        intent: str,
    ) -> dict:
        # Obtener disponibilidad del tenant
        calendar_creds = (tenant.api_keys_enc or {}).get("google_calendar")
        if not calendar_creds:
            logger.warning("No Google Calendar credentials for tenant %s", tenant.id)
            return {"action": "no_calendar", "message": None, "meeting": None}

        try:
            from app.integrations.google.calendar import GoogleCalendarClient  # lazy import
            cal = GoogleCalendarClient(credentials_json=calendar_creds)
            slots = cal.get_available_slots(days_ahead=5, slot_duration_minutes=30)
        except Exception as e:
            logger.error("Calendar error for tenant %s: %s", tenant.id, e)
            return {"action": "calendar_error", "message": None, "meeting": None}

        if not slots:
            return {"action": "no_slots", "message": None, "meeting": None}

        # Llamar a Claude para seleccionar el slot y redactar la confirmación
        system = f"""Eres el asistente de agendamiento de {tenant.name}.
Recibiste un reply de un prospecto que mostró interés.
Tu trabajo es seleccionar el mejor slot disponible y redactar un mensaje de confirmación.

El mensaje debe:
- Ser breve (3-4 líneas)
- Confirmar fecha y hora en formato legible
- Mencionar que se enviará invitación con link de Google Meet
- Ser cálido y profesional

Usa el tool book_meeting para entregar tu respuesta."""

        slots_text = "\n".join(
            f"- {s['label']} (start={s['start']}, end={s['end']})" for s in slots
        )

        user_msg = f"""Reply del prospecto:
"{reply_body}"

Prospecto: {lead.full_name or lead.email} de {lead.company}

Slots disponibles:
{slots_text}

Selecciona el primer slot disponible (el más próximo) y redacta el mensaje de confirmación."""

        response = self.claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            tools=[BOOKING_TOOL],
            tool_choice={"type": "tool", "name": "book_meeting"},
        )

        block = next(b for b in response.content if b.type == "tool_use")
        data = block.input  # type: ignore[union-attr]

        # Crear evento en Google Calendar
        try:
            event = cal.create_event(
                title=f"Reunión {tenant.name} — {lead.full_name or lead.email}",
                start=data["selected_slot_start"],
                end=data["selected_slot_end"],
                guest_email=lead.email,
                description=f"Reunión agendada a través de Boids.\nProspecto: {lead.email}",
            )

            # Insertar Meet link en el mensaje de confirmación si hay placeholder
            confirmation = data["confirmation_message"].replace(
                "{meet_link}", event["meet_link"]
            )

            return {
                "action": "meeting_booked",
                "message": confirmation,
                "meeting": {
                    "calendar_event_id": event["event_id"],
                    "meet_link": event["meet_link"],
                    "scheduled_at": data["selected_slot_start"],
                },
            }

        except Exception as e:
            logger.error("Failed to create calendar event: %s", e)
            return {"action": "calendar_error", "message": None, "meeting": None}

    async def _generate_decline_response(
        self,
        reply_body: str,
        lead: Lead,
        tenant: Tenant,
    ) -> str:
        response = self.claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=f"""Eres el asistente de {tenant.name}.
Recibiste un reply negativo a un cold email.
Redacta un mensaje breve (2-3 líneas) que:
- Agradezca la respuesta
- Respete la decisión
- Deje la puerta abierta sin presionar
Usa el tool handle_negative.""",
            messages=[
                {
                    "role": "user",
                    "content": f'Reply negativo recibido: "{reply_body}"',
                }
            ],
            tools=[DECLINE_TOOL],
            tool_choice={"type": "tool", "name": "handle_negative"},
        )
        block = next(b for b in response.content if b.type == "tool_use")
        return block.input["response_message"]  # type: ignore[index]
