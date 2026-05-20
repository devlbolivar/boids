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
