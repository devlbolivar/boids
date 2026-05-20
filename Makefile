.PHONY: test test-unit test-integration test-watch coverage lint migrate-test clean

test-services:
	docker compose -f docker-compose.test.yml up -d
	sleep 2
	docker compose -f docker-compose.test.yml exec db \
		psql -U boids -c "CREATE DATABASE boids_test_db;" || true

test: test-services
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration: test-services
	pytest tests/integration/ -v --tb=short

test-watch:
	pytest-watch tests/ -- -v --tb=short

coverage: test-services
	pytest tests/ --cov=app --cov-report=term-missing --cov-report=html
	@echo "HTML report: htmlcov/index.html"

lint:
	ruff check app/ tests/
	mypy app/

migrate-test:
	DATABASE_URL=postgresql+asyncpg://boids:boids@localhost:5433/boids_test_db \
		alembic upgrade head

clean:
	docker compose -f docker-compose.test.yml down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	rm -rf htmlcov/ .coverage

# M3: Lead Finder Agent targets
test-fast: test-services
	pytest tests/ -v --tb=short -m "not slow"

test-slow: test-services
	pytest tests/ -v --tb=short -m "slow"

test-agent-m3: test-services
	pytest tests/unit/test_icp_mapper.py \
	       tests/unit/test_lead_normalizer.py \
	       tests/unit/test_lead_finder_agent.py \
	       tests/integration/test_lead_finder_endpoint.py \
	       -v --tb=short

# M4: Research Agent targets
test-agent-m4: test-services
	pytest tests/unit/test_research_schemas.py \
	       tests/unit/test_research_agent.py \
	       tests/unit/test_research_task.py \
	       tests/integration/test_research_pipeline.py \
	       -v --tb=short

test-agents: test-services
	pytest tests/unit/ tests/integration/ -v --tb=short -m "not slow"

# M5: RAG Knowledge Base targets
test-agent-m5: test-services
	pytest tests/unit/test_chunker.py \
	       tests/unit/test_qdrant_collection_naming.py \
	       tests/unit/test_build_rag_query.py \
	       tests/integration/test_knowledge_pipeline.py \
	       -v --tb=short

qdrant-up:
	docker run -d -p 6333:6333 -p 6334:6334 \
	    -v qdrant_storage:/qdrant/storage \
	    --name boids_qdrant \
	    qdrant/qdrant

qdrant-down:
	docker stop boids_qdrant && docker rm boids_qdrant

# M6: Copywriter + QA Agent targets
test-agent-m6: test-services
	pytest tests/unit/test_qa_score.py \
	       tests/unit/test_copywriter_agent.py \
	       tests/unit/test_qa_agent.py \
	       tests/unit/test_copywriter_pipeline.py \
	       tests/integration/test_copywriter_pipeline.py \
	       -v --tb=short

# Smoke test del pipeline completo M3→M6 en secuencia
test-pipeline-smoke: test-services
	pytest tests/integration/ -k "e2e or pipeline" -v --tb=short -m "not slow"

# M7: Delivery + Scheduler Agent targets
test-agent-m7: test-services
	pytest tests/unit/test_intent_classifier.py \
	       tests/unit/test_scheduler_agent.py \
	       tests/unit/test_instantly_client.py \
	       tests/integration/test_delivery_pipeline.py \
	       tests/integration/test_scheduler_pipeline.py \
	       -v --tb=short

# Pipeline completo M3→M7 — smoke test del MVP
test-mvp-smoke: test-services
	pytest tests/ -k "e2e or pipeline or smoke" \
	       -v --tb=short -m "not slow"

# Coverage del MVP completo
coverage-mvp: test-services
	pytest tests/ --cov=app \
	       --cov-report=term-missing \
	       --cov-fail-under=75 \
	       -m "not slow" -q
