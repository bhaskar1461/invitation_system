# Gunicorn configuration file for production deployment
import multiprocessing

# Bind address and port
bind = "0.0.0.0:8000"

# Number of worker processes (standard formula: 2 * CPU + 1)
workers = multiprocessing.cpu_count() * 2 + 1

# Worker type
worker_class = "sync"

# Log configuration (Gunicorn logs to stdout/stderr so Azure Web App streams capture them)
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Timeout settings
timeout = 60
keepalive = 2
