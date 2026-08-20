COMPOSE ?= docker compose

.PHONY: bootstrap check up down ps logs

bootstrap:
	@printf '%s\n' 'Bootstrap is represented by the tracked repo structure, compose file, and service skeletons.'

check:
	$(COMPOSE) config >/dev/null

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f
