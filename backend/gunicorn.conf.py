# Gunicorn configuration for WebSocket support
bind = "0.0.0.0:5001"
workers = 4  # Single worker for WebSocket support
worker_class = "eventlet"
worker_connections = 250
timeout = 120
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = False 