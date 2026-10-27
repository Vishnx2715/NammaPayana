import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", 2))
worker_class = "sync"
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
preload_app = False


def on_starting(server):
    import os
    print(f"[gunicorn] Starting Namma Payana on port {os.environ.get('PORT', 5000)}")
    print(f"[gunicorn] FLASK_ENV={os.environ.get('FLASK_ENV', 'development')}")
    print(f"[gunicorn] Workers={server.cfg.workers}")
