from app.integrations.qdrant.client import QdrantKnowledgeClient


def test_collection_name_strips_hyphens():
    client = QdrantKnowledgeClient.__new__(QdrantKnowledgeClient)
    tenant_id = "550e8400-e29b-41d4-a716-446655440000"
    name = client._collection_name(tenant_id)
    assert "-" not in name
    assert name.startswith("knowledge_")


def test_collection_name_deterministic():
    client = QdrantKnowledgeClient.__new__(QdrantKnowledgeClient)
    tenant_id = "550e8400-e29b-41d4-a716-446655440000"
    assert client._collection_name(tenant_id) == client._collection_name(tenant_id)


def test_different_tenants_get_different_collections():
    client = QdrantKnowledgeClient.__new__(QdrantKnowledgeClient)
    name1 = client._collection_name("tenant-a-uuid")
    name2 = client._collection_name("tenant-b-uuid")
    assert name1 != name2
