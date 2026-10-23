from django.conf import settings
from django.urls import include, path

urlpatterns = [path("", include("herd.urls"))]

if settings.DEBUG:
    from django.contrib.staticfiles.views import serve
    from django.urls import re_path

    urlpatterns += [re_path(r"^static/(?P<path>.*)$", serve)]
