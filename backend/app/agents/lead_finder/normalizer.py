from app.leads.schemas import LeadCreate

UNLOCKED_PLACEHOLDER = "email_not_unlocked@domain.com"


def normalize_apollo_contact(raw: dict) -> LeadCreate | None:
    """
    Convierte un contacto de Apollo al schema LeadCreate de Boids.
    Retorna None si el contacto no tiene email verificado.
    """
    email = (
        raw.get("email")
        or raw.get("primary_email")
        or _extract_first_email(raw.get("email_addresses", []))
    )

    if not email or email == UNLOCKED_PLACEHOLDER:
        return None

    full_name = raw.get("name", "").strip()
    if not full_name:
        first = raw.get("first_name", "")
        last = raw.get("last_name", "")
        full_name = f"{first} {last}".strip()

    org = raw.get("organization") or {}
    company = org.get("name") or raw.get("organization_name", "")

    return LeadCreate(
        email=email.lower().strip(),
        full_name=full_name,
        company=company,
        title=raw.get("title", ""),
        apollo_id=raw.get("id"),
    )


def _extract_first_email(email_list: list[dict]) -> str | None:
    for e in email_list:
        if e.get("email") and "not_unlocked" not in e["email"]:
            return e["email"]
    return None


def normalize_apollo_batch(raw_contacts: list[dict]) -> list[LeadCreate]:
    results = []
    for raw in raw_contacts:
        normalized = normalize_apollo_contact(raw)
        if normalized:
            results.append(normalized)
    return results
