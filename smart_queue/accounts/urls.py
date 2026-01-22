from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    path('login/', views.user_login, name='login'),
    path('signup/', views.user_signup, name='signup'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),

    path('admin-login/', views.admin_login, name='admin_login'),

    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

    path('logout/', views.logout_view, name='logout'),
]
