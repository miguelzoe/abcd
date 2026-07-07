"""
apps/admin_panel/urls.py
========================
Routes de l'interface administrateur.
Toutes les routes sont préfixées par /api/admin/ dans config/urls.py.
"""
from django.urls import path

from apps.admin_panel.views import (
    # Dashboard
    DashboardStatsView,
    UserEvolutionView,
    # Users
    AdminUserListView,
    AdminUserDetailView,
    UserApprouverView,
    UserRefuserView,
    UserBloquerView,
    UserDebloquerView,
    DocumentStatusView,
    DocumentContentView,
    # Modération
    SignalementListView,
    SignalementTraiterView,
    SignalementRejeterView,
    # Interventions
    AdminInterventionListView,
    AdminInterventionDetailView,
    # Notifications
    NotificationListView,
    NotificationStatsView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    NotificationDeleteView,
    NotificationDeleteReadView,
    # Ventes
    VenteListView,
    # Statistiques
    StatistiquesView,
    AdminTechnicianPerformanceView,
    MarketplaceAdminSummaryView,
    MarketplacePartnerApplicationsAdminView,
    MarketplacePartnerApplicationApproveView,
    MarketplacePartnerApplicationRejectView,
)

urlpatterns = [
    # ── Dashboard ───────────────────────────────────────────────────────────
    path('dashboard/stats', DashboardStatsView.as_view(), name='admin-dashboard-stats'),
    path('dashboard/user-evolution', UserEvolutionView.as_view(), name='admin-user-evolution'),

    # ── Gestion des utilisateurs ────────────────────────────────────────────
    path('users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('users/<int:pk>/approuver/', UserApprouverView.as_view(), name='admin-user-approuver'),
    path('users/<int:pk>/refuser/', UserRefuserView.as_view(), name='admin-user-refuser'),
    path('users/<int:pk>/bloquer/', UserBloquerView.as_view(), name='admin-user-bloquer'),
    path('users/<int:pk>/debloquer/', UserDebloquerView.as_view(), name='admin-user-debloquer'),
    path(
        'users/<int:user_pk>/documents/<int:doc_pk>/',
        DocumentStatusView.as_view(),
        name='admin-document-status',
    ),
    path(
        'users/<int:user_pk>/documents/<int:doc_pk>/view/',
        DocumentContentView.as_view(),
        name='admin-document-view',
    ),

    # ── Modération (signalements) ────────────────────────────────────────────
    path('signalements/', SignalementListView.as_view(), name='admin-signalement-list'),
    path(
        'signalements/<int:pk>/traiter/',
        SignalementTraiterView.as_view(),
        name='admin-signalement-traiter',
    ),
    path(
        'signalements/<int:pk>/rejeter/',
        SignalementRejeterView.as_view(),
        name='admin-signalement-rejeter',
    ),

    # ── Interventions ────────────────────────────────────────────────────────
    path('interventions/', AdminInterventionListView.as_view(), name='admin-intervention-list'),
    path('interventions/<int:pk>/', AdminInterventionDetailView.as_view(), name='admin-intervention-detail'),

    # ── Notifications ────────────────────────────────────────────────────────
    # ⚠️  L'ordre est important : les routes fixes avant les routes dynamiques
    path('notifications/stats/', NotificationStatsView.as_view(), name='admin-notification-stats'),
    path('notifications/all/lu/', NotificationMarkAllReadView.as_view(), name='admin-notification-all-lu'),
    path('notifications/lues/', NotificationDeleteReadView.as_view(), name='admin-notification-delete-lues'),
    path('notifications/', NotificationListView.as_view(), name='admin-notification-list'),
    path('notifications/<int:pk>/lu/', NotificationMarkReadView.as_view(), name='admin-notification-lu'),
    path('notifications/<int:pk>/', NotificationDeleteView.as_view(), name='admin-notification-delete'),

    # ── Ventes (Marketplace) ─────────────────────────────────────────────────
    path('ventes/', VenteListView.as_view(), name='admin-vente-list'),

    # ── Marketplace mobile/admin ──────────────────────────────────────────────
    path('marketplace/summary/', MarketplaceAdminSummaryView.as_view(), name='admin-marketplace-summary'),
    path('marketplace/partners/', MarketplacePartnerApplicationsAdminView.as_view(), name='admin-marketplace-partners'),
    path('marketplace/partners/<int:pk>/approve/', MarketplacePartnerApplicationApproveView.as_view(), name='admin-marketplace-partner-approve'),
    path('marketplace/partners/<int:pk>/reject/', MarketplacePartnerApplicationRejectView.as_view(), name='admin-marketplace-partner-reject'),

    # ── Statistiques ─────────────────────────────────────────────────────────
    path('statistiques/', StatistiquesView.as_view(), name='admin-statistiques'),
    path('techniciens/performance/', AdminTechnicianPerformanceView.as_view(), name='admin-technician-performance'),
]