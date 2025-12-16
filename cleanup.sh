#!/bin/bash
echo "🧹 Stopping services and removing project images..."
docker compose down --rmi local --remove-orphans

echo "🧹 Pruning build cache and dangling images..."
docker system prune -f

echo "✨ Cleanup complete! No unnecessary builds left on disk."
