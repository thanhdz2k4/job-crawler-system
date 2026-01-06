@echo off
REM Rebuild Docker Script for Job Crawler System
REM This script stops, rebuilds, and restarts all Docker containers

echo.
echo ============================================
echo   Rebuild Docker - Job Crawler System
echo ============================================
echo.

set COMPOSE_FILE=docker-compose.yml

echo [1/3] Stopping and removing existing containers...
docker-compose -f %COMPOSE_FILE% down

echo.
echo [2/3] Building Docker images (no cache)...
docker-compose -f %COMPOSE_FILE% build --no-cache

echo.
echo [3/3] Starting containers in detached mode...
docker-compose -f %COMPOSE_FILE% up -d

echo.
echo ============================================
echo   Docker containers rebuilt successfully!
echo ============================================
echo.
echo Container status:
docker-compose -f %COMPOSE_FILE% ps

echo.
echo -------------------------------------------
echo   Useful Information:
echo -------------------------------------------
echo   - View logs: docker-compose -f %COMPOSE_FILE% logs -f
echo   - Airflow UI: http://localhost:8081
echo   - Login: admin/admin
echo   - MongoDB: mongodb://admin:admin123@localhost:27018
echo -------------------------------------------
echo.

pause
