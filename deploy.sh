#!/bin/bash
set -e
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
