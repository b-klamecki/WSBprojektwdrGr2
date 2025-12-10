from django.urls import path
from . import adminpanel_views

urlpatterns = [
    path("", adminpanel_views.dashboard, name="panel_dashboard"),
    path("sessions/", adminpanel_views.session_list, name="panel_sessions"),
    path('sessions/form/', adminpanel_views.session_form, name='panel_session_add'),
    path('sessions/form/<int:id>/', adminpanel_views.session_form, name='panel_session_edit'),
    path("sessions/<int:id>/delete/", adminpanel_views.session_delete, name="panel_session_delete"),
    path("sessions/<int:id>/photos/upload/", adminpanel_views.session_photos_upload, name="panel_session_photos_upload"),
    path("photos/<int:photo_id>/set-cover/", adminpanel_views.set_cover_photo, name="panel_set_cover_photo"),
    path("photos/<int:photo_id>/delete/", adminpanel_views.photo_delete, name="panel_photo_delete"),
    path("login/", adminpanel_views.panel_login, name="panel_login"),
    path("logout/", adminpanel_views.panel_logout, name="panel_logout"),
]
