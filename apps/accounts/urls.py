from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import views as auth_views
from .forms import LoginForm
from .views import profile
from . import views

app_name = "accounts"

urlpatterns = [
    path('login/', LoginView.as_view(template_name='accounts/login.html', authentication_form=LoginForm), name='login'),
    path('logout/', LogoutView.as_view(next_page='accounts:login'), name='logout'),

    path('profile/', profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/update/', views.profile_update, name='profile_update'),
    path('profile/image/', views.image_upload, name='image_upload'),

    # User Management
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/access/', views.user_access_update, name='user_access_update'),
    path('users/<int:pk>/password-reset/', views.user_password_reset, name='user_password_reset'),
    path('users/<int:pk>/terminate/', views.user_terminate, name='user_terminate'),
    path('users/<int:pk>/reactivate/', views.user_reactivate, name='user_reactivate'),

    # Group Management (Superuser only)
    path('groups/', views.group_list, name='group_list'),
    path('groups/create/', views.group_create, name='group_create'),
    path('groups/<int:pk>/edit/', views.group_edit, name='group_edit'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),

    # Password Change (using Django's built-in views)
    path('password/change/',
         auth_views.PasswordChangeView.as_view(
             template_name='accounts/password_change.html',
             success_url='/accounts/password/change/done/'
         ),
         name='password_change'),

    path('password/change/done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='accounts/password_change_done.html'
         ),
         name='password_change_done'),
]

