#!/bin/bash
docker compose -f docker-compose.yml -f docker-compose.limits.yml build --no-cache
docker compose -f docker-compose.yml -f docker-compose.limits.yml up -d