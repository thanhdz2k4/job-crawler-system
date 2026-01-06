#!/bin/bash

# Rebuild Docker Script for Job Crawler System
# This script stops, rebuilds, and restarts all Docker containers

echo "🛑 Stopping existing containers..."
docker compose down

echo ""
echo "🔨 Building Docker images..."
docker compose build

echo ""
echo "🚀 Starting containers in detached mode..."
docker compose up -d

echo ""
echo "✅ Docker containers rebuilt and started successfully!"
echo ""
echo "📊 Container status:"
docker compose ps

echo ""
echo "📝 To view logs, run: docker compose logs -f"
echo "🌐 Airflow UI: http://192.168.10.211:8081 (admin/admin)"
echo "🗄️  MongoDB: mongodb://admin:admin123@localhost:27018"
