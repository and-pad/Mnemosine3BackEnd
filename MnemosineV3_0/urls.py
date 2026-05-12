#from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles import views
from django.urls import re_path

urlpatterns = [
  #  path("admin/", admin.site.urls),
    path("auth/", include("authentication.urls")),
    path("authenticated/", include("user_queries.urls")),
]

# Servir archivos estáticos y medios durante el desarrollo
if settings.DEBUG:
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', views.serve, {'document_root': settings.STATIC_ROOT}),
    ]
