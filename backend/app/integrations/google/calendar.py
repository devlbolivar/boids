from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone

from app.config import settings


class GoogleCalendarClient:
    """
    Wrapper sobre Google Calendar API.
    Las credenciales del tenant se almacenan en api_keys_enc.
    """

    def __init__(self, credentials_json: dict):
        creds = Credentials(
            token=credentials_json.get("access_token"),
            refresh_token=credentials_json.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )
        self.service = build("calendar", "v3", credentials=creds)

    def get_available_slots(
        self,
        days_ahead: int = 5,
        slot_duration_minutes: int = 30,
    ) -> list[dict]:
        """
        Retorna slots disponibles en los próximos N días laborales.
        Evita horas fuera del rango 9am-6pm.
        """
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)

        # Consultar freebusy
        body = {
            "timeMin": now.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": "primary"}],
        }
        result = self.service.freebusy().query(body=body).execute()
        busy = result["calendars"]["primary"]["busy"]

        # Generar slots candidatos (cada 30 min, 9am-6pm)
        slots: list[dict] = []
        current = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if current < now:
            current += timedelta(days=1)

        while current < end and len(slots) < 6:
            # Saltar fines de semana
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue

            slot_end = current + timedelta(minutes=slot_duration_minutes)

            # Verificar que no colisiona con eventos existentes
            is_free = all(
                not (
                    current < datetime.fromisoformat(b["end"])
                    and slot_end > datetime.fromisoformat(b["start"])
                )
                for b in busy
            )

            if is_free and 9 <= current.hour < 18:
                slots.append(
                    {
                        "start": current.isoformat(),
                        "end": slot_end.isoformat(),
                        "label": current.strftime("%A %d %b, %H:%M"),
                    }
                )

            current += timedelta(minutes=30)

        return slots

    def create_event(
        self,
        title: str,
        start: str,  # ISO format
        end: str,
        guest_email: str,
        description: str = "",
    ) -> dict:
        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start, "timeZone": "America/Santiago"},
            "end": {"dateTime": end, "timeZone": "America/Santiago"},
            "attendees": [{"email": guest_email}],
            "conferenceData": {
                "createRequest": {
                    "requestId": f"boids-{guest_email}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }
        result = self.service.events().insert(
            calendarId="primary",
            body=event,
            conferenceDataVersion=1,
            sendUpdates="all",  # envía invitación al guest
        ).execute()

        return {
            "event_id": result["id"],
            "meet_link": result.get("hangoutLink", ""),
            "start": result["start"]["dateTime"],
            "html_link": result.get("htmlLink", ""),
        }
