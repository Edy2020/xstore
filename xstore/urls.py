from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('catalogo.urls')),
]

if settings.DEBUG:
    from django.views.static import serve
    import re

    urlpatterns += [
        path(
            'media/<path:path>',
            serve,
            {'document_root': settings.XSTOCK_STORAGE_ROOT},
        ),
    ]
