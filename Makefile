IMAGE_NAME = zap2py
CONTAINER_NAME = zap2py

.PHONY: build up down logs shell

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker logs -f $(CONTAINER_NAME)

shell:
	docker exec -it $(CONTAINER_NAME) /bin/bash
