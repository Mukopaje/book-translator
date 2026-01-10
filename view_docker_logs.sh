#!/bin/bash
# Helper script to view Docker logs and errors

echo "=== Docker Logs Viewer ==="
echo ""
echo "Choose an option:"
echo "1. View all logs (foreground - see errors in real-time)"
echo "2. View logs from specific service (backend, worker, etc.)"
echo "3. Follow logs in real-time (already running containers)"
echo "4. View recent logs only"
echo ""
read -p "Enter option (1-4): " option

case $option in
    1)
        echo "Starting all services in foreground (Ctrl+C to stop)..."
        docker-compose up
        ;;
    2)
        echo "Available services: backend, worker, frontend, postgres, redis"
        read -p "Enter service name(s) separated by space: " services
        echo "Starting services: $services"
        docker-compose up $services
        ;;
    3)
        echo "Following logs from all services (Ctrl+C to stop)..."
        docker-compose logs -f
        ;;
    4)
        echo "Showing last 100 lines of logs from all services:"
        docker-compose logs --tail=100
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

