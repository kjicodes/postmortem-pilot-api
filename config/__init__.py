from .celery import app as celery_app

#ensure celery is loaded when Django starts up
__all__ = ('celery_app',)