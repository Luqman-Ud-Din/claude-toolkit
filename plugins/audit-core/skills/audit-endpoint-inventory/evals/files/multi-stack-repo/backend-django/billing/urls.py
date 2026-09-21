from django.urls import path

from . import views

urlpatterns = [
    path("api/invoices/", views.invoice_list),
]
