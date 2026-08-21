COMPOSE ?= docker compose

.PHONY: bootstrap check migrate-governance check-governance migrate-tse-v1 check-tse-v1 up down ps logs

bootstrap:
	@printf '%s\n' 'Bootstrap is represented by the tracked repo structure, compose file, and service skeletons.'

check:
	$(COMPOSE) config >/dev/null

migrate-governance:
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-fonteaberta} -d $${POSTGRES_DB:-fonteaberta} -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/002_data_governance.sql

check-governance:
	./scripts/check-governance.sh

migrate-tse-v1:
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-fonteaberta} -d $${POSTGRES_DB:-fonteaberta} -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/003_tse_v1.sql

check-tse-v1:
	python3 ./scripts/check-tse-v1.py

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f
