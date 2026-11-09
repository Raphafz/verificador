"""
WSGI config for saas_viabilidade project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saas_viabilidade.settings')

application = get_wsgi_application()

from saas_viabilidade.wsgi_security import strip_server_header_wsgi  # noqa: E402

application = strip_server_header_wsgi(application)
