from django.urls import path

from shortener.admins.views import url_list

urlpatterns = [
    path("", url_list, name="admin_url_list"),
]
