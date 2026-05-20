from app.agents.lead_finder.normalizer import normalize_apollo_contact, normalize_apollo_batch


def test_normalizes_valid_contact():
    raw = {
        "id": "apollo_123",
        "name": "Carlos Vega",
        "email": "carlos@startup.cl",
        "title": "CTO",
        "organization": {"name": "Startup Chile"},
    }
    lead = normalize_apollo_contact(raw)
    assert lead is not None
    assert lead.email == "carlos@startup.cl"
    assert lead.full_name == "Carlos Vega"
    assert lead.company == "Startup Chile"
    assert lead.title == "CTO"
    assert lead.apollo_id == "apollo_123"


def test_returns_none_for_unlocked_email():
    raw = {
        "id": "apollo_456",
        "email": "email_not_unlocked@domain.com",
        "name": "Unknown",
    }
    lead = normalize_apollo_contact(raw)
    assert lead is None


def test_returns_none_for_missing_email():
    raw = {"id": "apollo_789", "name": "No Email"}
    lead = normalize_apollo_contact(raw)
    assert lead is None


def test_constructs_name_from_parts_when_no_full_name():
    raw = {
        "first_name": "Maria",
        "last_name": "González",
        "email": "maria@empresa.cl",
        "organization": {"name": "Empresa"},
    }
    lead = normalize_apollo_contact(raw)
    assert lead is not None
    assert lead.full_name == "Maria González"


def test_normalizes_email_to_lowercase():
    raw = {"email": "CTO@STARTUP.CL", "name": "Test"}
    lead = normalize_apollo_contact(raw)
    assert lead is not None
    assert lead.email == "cto@startup.cl"


def test_extracts_email_from_email_addresses_list():
    raw = {
        "id": "ap1",
        "name": "Luis",
        "email_addresses": [
            {"email": "email_not_unlocked@placeholder.com"},
            {"email": "luis@real.cl"},
        ],
    }
    lead = normalize_apollo_contact(raw)
    assert lead is not None
    assert lead.email == "luis@real.cl"


def test_returns_none_when_all_emails_unlocked():
    raw = {
        "name": "Ghost",
        "email_addresses": [{"email": "email_not_unlocked@domain.com"}],
    }
    lead = normalize_apollo_contact(raw)
    assert lead is None


def test_normalize_batch_filters_invalid():
    contacts = [
        {"id": "1", "email": "valid@co.cl", "name": "Valid"},
        {"id": "2", "email": "email_not_unlocked@domain.com", "name": "Invalid"},
        {"id": "3", "name": "No email at all"},
    ]
    results = normalize_apollo_batch(contacts)
    assert len(results) == 1
    assert results[0].email == "valid@co.cl"
