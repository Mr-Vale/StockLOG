from django.urls import path

from . import views, home

urlpatterns = [
    path("properties/add/", home.add_property, name="add_property"),
    path("pics/add/", home.add_pic, name="add_pic"),
    path("access/", home.access, name="access"),
    path("context/select/", home.select_context, name="select_context"),
    path("context/ready/", home.context_ready, name="context_ready"),
    path("charts/", home.charts, name="charts"),
    path("mobs/<int:pk>/retire/", home.retire_mob, name="retire_mob"),
    path("mobs/", home.mobs, name="mobs"),
    path("workflow/<str:group>/", home.workflow, name="workflow"),
    path("recovery-worker.js", views.recovery_worker, name="recovery_worker"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("action/<str:operation>/", views.action, name="action"),
    path("animals/", views.animals, name="animals"),
    path("animal/<uuid:pk>/", views.animal_detail, name="animal"),
    path("inventory/", views.inventory, name="inventory"),
    path("events/", views.events, name="events"),
    path("reports/", views.report_view, name="reports"),
    path("import/", views.import_view, name="import"),
    path("accounts/", views.accounts, name="accounts"),
    path("settings/", views.settings_view, name="settings"),
    path("backup/latest/", views.backup_latest, name="backup_latest"),
    path("backup/<str:identity>/", views.backup_download, name="backup_download"),
    path("health/", views.health, name="health"),
]
