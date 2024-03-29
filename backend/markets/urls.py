from django.urls import path

from .views import IndexView, YieldPerDayView, YieldPerMaturityView, SectorsView

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('yield-per-day', YieldPerDayView.as_view(), name='yield_per_day'),
    path('yield-per-maturity', YieldPerMaturityView.as_view(), name='yield_per_maturity'),
    path('sectors', SectorsView.as_view(), name='sectors'),
]
