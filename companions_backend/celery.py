import os
import ssl
from celery import Celery
from django.conf import settings

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'companions_backend.settings')

if settings.DEBUG:
   app = Celery('companions_backend')
   
else:
   app = Celery('companions_backend')

   app.conf.update(
      broker_use_ssl={
         'ssl_cert_reqs': ssl.CERT_NONE,  # or ssl.CERT_REQUIRED if you fix SSL
      },
      redis_backend_use_ssl={
         'ssl_cert_reqs': ssl.CERT_NONE,
      },
   )

# Load config from Django settings, using a CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()