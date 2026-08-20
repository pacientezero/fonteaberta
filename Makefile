COMPOSE ?= docker compose

.PHONY: bootstrap check migrate-governance check-governance up down ps logs

bootstrap:
	@printf '%s\n' 'Bootstrap is represented by the tracked repo structure, compose file, and service skeletons.'

check:
	$(COMPOSE) config >/dev/null

migrate-governance:
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-fonteaberta} -d $${POSTGRES_DB:-fonteaberta} -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/002_data_governance.sql

check-governance:
	./scripts/check-governance.sh

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f
