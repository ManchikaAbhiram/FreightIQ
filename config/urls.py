from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.contrib.auth import views as auth_views
from audit import views
urlpatterns = [
 path('admin/', admin.site.urls),
 path('', views.home, name='home'),
 path('login/', views.login_view, name='login'),
 path('logout/', views.logout_view, name='logout'),
 path('register/', views.register, name='register'),
 path('waiting-for-approval/', views.waiting_for_approval, name='waiting_for_approval'),
 path('dashboard/', views.dashboard, name='dashboard'),
 path('admin-workspace/', views.admin_workspace, name='admin_workspace'),
 path('registration/<int:pk>/<str:decision>/', views.registration_decision, name='registration_decision'),
 path('shipments/', views.shipment_list, name='shipment_list'),
 path('shipments/new/', views.shipment_create, name='shipment_create'),
 path('invoices/', views.invoice_list, name='invoice_list'),
 path('invoices/new/', views.invoice_create, name='invoice_create'),
 path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
 path('cases/', views.case_queue, name='case_queue'),
 path('cases/<int:pk>/action/', views.case_action, name='case_action'),
 path('finance/', views.finance_workspace, name='finance_workspace'),
 path('credits/<int:pk>/action/', views.credit_action, name='credit_action'),
 path('audit-history/', views.audit_history, name='audit_history'),
 path('exports/<str:kind>.csv', views.export_csv, name='export_csv'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
