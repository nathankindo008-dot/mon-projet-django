from django.urls import path
from . import views

app_name = 'public'

urlpatterns = [
    path('',                              views.accueil,                  name='accueil'),
    path('api/autocomplete/',             views.autocomplete_indicateurs, name='autocomplete_indicateurs'),
    path('indicateurs/',                  views.liste_indicateurs,        name='liste_indicateurs'),
    path('indicateurs/export/',           views.export_indicateurs,       name='export_indicateurs'),
    path('indicateurs/<int:pk>/',         views.detail_indicateur,        name='detail_indicateur'),
    path('indicateurs/<int:pk>/export/',  views.export_donnees_indicateur,name='export_donnees_indicateur'),
]
