"""Gunicorn configuration for QuizWeaver."""

bind = "0.0.0.0:8000"
workers = 2  # Keep low for SQLite (avoids write contention)
timeout = 120
accesslog = "-"
errorlog = "-"
loglevel = "info"
