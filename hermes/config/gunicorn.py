# -*- coding: utf-8 -*-

import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
accesslog = "-"
access_log_format = "%(h)s %(l)s %(u)s %(t)s '%(r)s' %(s)s %(b)s '%(f)s' '%(a)s' in %(D)sµs"  # noqa: E501

workers = int(os.getenv("WEB_CONCURRENCY", 2))
threads = int(os.getenv("PYTHON_MAX_THREADS", 1))
timeout = 300
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 50))
reload = os.getenv("WEB_RELOAD", "false").lower() in (
    "y", "yes", "t", "true", "on", "1")
