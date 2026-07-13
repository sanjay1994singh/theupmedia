import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "theupmedia.settings")

application = get_wsgi_application()

try:
    from static_ranges import Ranges
    from dj_static import Cling, MediaCling
except ImportError:
    pass
else:
    application = Ranges(Cling(MediaCling(application)))
