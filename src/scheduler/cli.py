"""CLI entry point for Agent Runtime worker."""
import sys

from celery.bin.celery import main as celery_main


def run_worker():
    """Run Celery worker for agent runtime."""
    sys.argv = ["celery", "-A", "src.scheduler.tasks", "worker", "--loglevel=info"]
    celery_main()


if __name__ == "__main__":
    run_worker()
