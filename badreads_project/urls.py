from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import set_language
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/setlang/', set_language, name='set_language'),
    # path("__reload__/", include("django_browser_reload.urls")),
]

# Las URLs dentro de i18n_patterns tendrán el prefijo de idioma (ej. /es/, /en/)
urlpatterns += i18n_patterns(
    path('', include('main_app.urls')),
    prefix_default_language=True
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

