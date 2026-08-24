COMPOSE ?= docker compose

.PHONY: bootstrap check migrate-governance check-governance migrate-tse-v1 check-tse-v1 migrate-documents-rag check-documents-rag migrate-expansion-bcb check-expansion-bcb migrate-expansion-ibge check-expansion-ibge migrate-expansion-camara check-expansion-camara check-expansion-senado up down ps logs

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

migrate-documents-rag:
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-fonteaberta} -d $${POSTGRES_DB:-fonteaberta} -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/004_documents_rag.sql

check-documents-rag:
	$(COMPOSE) run --rm --no-deps -v $(CURDIR):/workspace -w /workspace api python3 scripts/check-documents-rag.py

migrate-expansion-bcb:
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-fonteaberta} -d $${POSTGRES_DB:-fonteaberta} -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/005_expansion_bcb.sql

check-expansion-bcb:
	$(COMPOSE) run --rm --no-deps -v $(CURDIR):/workspace -w /workspace api python3 scripts/check-expansion-bcb.py

migrate-expansion-ibge:
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-fonteaberta} -d $${POSTGRES_DB:-fonteaberta} -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/006_expansion_ibge.sql

check-expansion-ibge:
	$(COMPOSE) run --rm --no-deps -v $(CURDIR):/workspace -w /workspace api python3 scripts/check-expansion-ibge.py

migrate-expansion-camara:
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-fonteaberta} -d $${POSTGRES_DB:-fonteaberta} -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/007_expansion_camara.sql

check-expansion-camara:
	$(COMPOSE) run --rm --no-deps -v $(CURDIR):/workspace -w /workspace api python3 scripts/check-expansion-camara.py

check-expansion-senado:
	$(COMPOSE) run --rm --no-deps -v $(CURDIR):/workspace -w /workspace api python3 scripts/check-expansion-senado.py

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f
