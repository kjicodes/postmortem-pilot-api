import os
from celery import Celery

#tells Celery which Django settings to use at startup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

#initialize Celery obj
app = Celery('config')

#read own config from settings.py - look for prefix CELERY
app.config_from_object('django.conf:settings', namespace='CELERY')

#automatically finds tasks.py files across all installed apps
app.autodiscover_tasks()
