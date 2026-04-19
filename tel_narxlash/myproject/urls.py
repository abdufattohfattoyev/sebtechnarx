from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.template.response import TemplateResponse
from botapp import views


# Custom admin index with statistics
_original_index = admin.site.__class__.index

def custom_admin_index(self, request, extra_context=None):
    from botapp.models import iPhoneModel, StorageOption, Color, PriceEntry, ReplacedPartCombination
    extra_context = extra_context or {}
    extra_context.update({
        'total_models': iPhoneModel.objects.filter(is_active=True).count(),
        'total_prices': PriceEntry.objects.count(),
        'total_storages': StorageOption.objects.count(),
        'total_colors': Color.objects.count(),
        'total_combinations': ReplacedPartCombination.objects.filter(is_active=True).count(),
    })
    return _original_index(self, request, extra_context)

admin.site.__class__.index = custom_admin_index


urlpatterns = [
    path('admin/', admin.site.urls),

    # Public pages
    path('', views.index, name='index'),
    path('narxlar/', views.price_list, name='price_list'),
    path('model/<int:model_id>/', views.model_detail, name='model_detail'),
    path('taqqoslash/', views.compare, name='compare'),

    # AJAX API
    path('api/model-options/', views.api_model_options, name='api_model_options'),
    path('api/calculate/', views.api_calculate, name='api_calculate'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
