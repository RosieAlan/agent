@echo off
cd /d "%~dp0"
docker compose --env-file .env.mysql -f compose.mysql.yaml up -d --wait
