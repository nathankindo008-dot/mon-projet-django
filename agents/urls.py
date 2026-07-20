from django.urls import path
from . import views

app_name = 'agents'

urlpatterns = [
    # Authentification
    path('login/',               views.login_view,      name='login'),
    path('logout/',              views.logout_view,      name='logout'),

    # Dashboard agent
    path('dashboard/',           views.dashboard,        name='dashboard'),
    path('saisie/',              views.saisie,           name='saisie'),
    path('saisie/<int:ind_id>/', views.saisie,           name='saisie_indicateur'),
    path('mes-donnees/',         views.mes_donnees,      name='mes_donnees'),

    # Admin — Validation
    path('validation/',          views.validation,       name='validation'),
    path('valider/<int:pk>/',    views.valider_donnee,   name='valider_donnee'),
    path('rejeter/<int:pk>/',    views.rejeter_donnee,   name='rejeter_donnee'),
    path('supprimer-donnee/<int:pk>/', views.supprimer_donnee, name='supprimer_donnee'),

    # Admin — Gestion des agents
    path('agents/',              views.liste_agents,     name='liste_agents'),
    path('agents/creer/',        views.creer_agent,      name='creer_agent'),
    path('agents/<int:pk>/modifier/', views.modifier_agent, name='modifier_agent'),
    path('agents/<int:pk>/supprimer/', views.supprimer_agent, name='supprimer_agent'),

    # Admin — Gestion des indicateurs
    path('gestion-indicateurs/',                   views.gestion_indicateurs, name='gestion_indicateurs'),
    path('gestion-indicateurs/<int:pk>/modifier/', views.modifier_indicateur, name='modifier_indicateur'),
]
