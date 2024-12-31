from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.conf.urls.static import static

urlpatterns = [
                  path('admin/', admin.site.urls),
                  path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
                  path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
                  path("auth/", include("apps.accounts.urls")),
                  path("profiles/", include("apps.profiles.urls")),
                  path("sellers/", include("apps.sellers.urls")),
                  path("shop/", include("apps.shop.urls")),

              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
