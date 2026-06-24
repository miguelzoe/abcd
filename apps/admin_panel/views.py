"""
apps/admin_panel/views.py
=========================
Tous les endpoints de l'interface administrateur de CARTRONIC.

Routes couvertes (préfixe /api/admin/) :
  GET  /dashboard/stats            → DashboardStatsView
  GET  /dashboard/user-evolution   → UserEvolutionView

  GET  /users/                     → AdminUserListView
  GET  /users/<pk>/                → AdminUserDetailView
  POST /users/<pk>/approuver/      → UserApprouverView
  POST /users/<pk>/refuser/        → UserRefuserView
  POST /users/<pk>/bloquer/        → UserBloquerView
  POST /users/<pk>/debloquer/      → UserDebloquerView
  PATCH /users/<pk>/documents/<doc_pk>/  → DocumentStatusView
  GET   /users/<pk>/documents/<doc_pk>/view/ → DocumentContentView

  GET  /signalements/              → SignalementListView
  POST /signalements/              → SignalementCreateView
  POST /signalements/<pk>/traiter/ → SignalementTraiterView
  POST /signalements/<pk>/rejeter/ → SignalementRejeterView

  GET  /interventions/             → AdminInterventionListView
  GET  /interventions/<pk>/        → AdminInterventionDetailView

  GET  /notifications/             → NotificationListView
  GET  /notifications/stats/       → NotificationStatsView
  PATCH /notifications/<pk>/lu/    → NotificationMarkReadView
  PATCH /notifications/all/lu/     → NotificationMarkAllReadView
  DELETE /notifications/<pk>/      → NotificationDeleteView
  DELETE /notifications/lues/      → NotificationDeleteReadView

  GET  /ventes/                    → VenteListView
  GET  /statistiques/              → StatistiquesView
  GET  /techniciens/performance/    → AdminTechnicianPerformanceView
"""

from datetime import timedelta, date
from calendar import month_abbr

from django.utils import timezone
from django.db.models import Sum, Avg, Count
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.admin_panel.models import Signalement, Notification
from apps.admin_panel.permissions import IsAdministrator
from apps.admin_panel.serializers import (
    DashboardStatsSerializer,
    UserEvolutionSerializer,
    AdminUserListSerializer,
    AdminUserDetailSerializer,
    DocumentJustificatifSerializer,
    SignalementSerializer,
    SignalementCreateSerializer,
    SignalementTraiterSerializer,
    AdminInterventionSerializer,
    NotificationSerializer,
    NotificationStatsSerializer,
    AdminVenteSerializer,
    StatistiquesSerializer,
)
from apps.users.models import User, Client, Technician, Vendor, Administrator, TechnicianDocument
from apps.reservations.models import Reservation, Invoice, Evaluation
from apps.reservations.services import get_reservations_revenue, get_reservation_revenue
from apps.marketplace.models import Commande

User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _percent_change(current, previous):
    """Calcule la variation en % entre deux valeurs."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round((current - previous) / previous * 100, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardStatsView(APIView):
    """
    GET /api/admin/dashboard/stats
    Retourne les indicateurs clés pour le tableau de bord admin.
    """
    permission_classes = [IsAdministrator]

    def get(self, request):
        now = timezone.now()
        debut_mois = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Pour les 30 derniers jours au lieu du mois calendaire
        debut_30j = now - timedelta(days=30)
        debut_30j_prev = now - timedelta(days=60)
        
        # Utilisateurs
        USER_TYPES = ['client', 'technician', 'vendor', 'administrator']
        total_users = User.objects.filter(user_type__in=USER_TYPES).count()
        
        # Variation sur les 30 derniers jours vs 60-30 derniers jours (plus représentatif)
        users_30j = User.objects.filter(
            user_type__in=USER_TYPES,
            date_joined__gte=debut_30j
        ).count()
        users_30j_prev = User.objects.filter(
            user_type__in=USER_TYPES,
            date_joined__gte=debut_30j_prev,
            date_joined__lt=debut_30j
        ).count()
        
        # Si très peu de données et les 30j n'affichent rien, utiliser le mois complet 
        if users_30j == 0 and users_30j_prev == 0 and total_users > 0:
            # Fallback: comparer avec les 30 j avant (pour éviter 0% si personne ce mois)
            users_before_30j = User.objects.filter(
                user_type__in=USER_TYPES,
                date_joined__isnull=False,
                date_joined__lt=debut_30j_prev
            ).count()
            users_30j_prev = users_before_30j
            users_30j = total_users - users_before_30j
        
        variation_users = _percent_change(users_30j, users_30j_prev)

        # Signalements en attente
        signalements_en_attente = Signalement.objects.filter(status='en_attente').count()

        # Revenus du mois (factures payées)
        debut_mois = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        debut_mois_prec = (debut_mois - timedelta(days=1)).replace(day=1)
        
        revenus_mois = float(get_reservations_revenue(
            Reservation.objects.filter(created_at__gte=debut_mois)
        ))
        revenus_mois_prec = float(get_reservations_revenue(
            Reservation.objects.filter(created_at__gte=debut_mois_prec, created_at__lt=debut_mois)
        ))
        variation_revenus = _percent_change(revenus_mois, revenus_mois_prec)

        data = {
            'utilisateursTotaux': total_users,
            'utilisateursVariation': variation_users,
            'signalementEnAttente': signalements_en_attente,
            'revenusMois': revenus_mois,
            'revenusVariation': variation_revenus,
        }
        serializer = DashboardStatsSerializer(data)
        return Response(serializer.data)


class UserEvolutionView(APIView):
    """
    GET /api/admin/dashboard/user-evolution
    Retourne l'évolution du nombre TOTAL cumulatif d'utilisateurs par type sur 6 mois.
    """
    permission_classes = [IsAdministrator]

    def get(self, request):
        now = timezone.now()
        result = []

        for i in range(5, -1, -1):
            # Début et fin du mois i mois en arrière
            ref = now - timedelta(days=30 * i)
            debut = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if debut.month == 12:
                fin = debut.replace(year=debut.year + 1, month=1)
            else:
                fin = debut.replace(month=debut.month + 1)

            # Compter le TOTAL cumulatif d'utilisateurs jusqu'à la fin du mois
            clients = User.objects.filter(
                user_type='client',
                date_joined__lt=fin
            ).count()
            techniciens = User.objects.filter(
                user_type='technician',
                date_joined__lt=fin
            ).count()

            mois_label = debut.strftime('%b %Y')
            result.append({
                'mois': mois_label,
                'clients': clients,
                'techniciens': techniciens,
            })

        serializer = UserEvolutionSerializer(result, many=True)
        return Response(serializer.data)


# ═══════════════════════════════════════════════════════════════════════════════
# USERS (Gestion des utilisateurs)
# ═══════════════════════════════════════════════════════════════════════════════

class AdminUserListView(APIView):
    """
    GET /api/admin/users/
    Liste tous les utilisateurs (clients + techniciens + vendeurs).
    Paramètres query : search, role, status
    """
    permission_classes = [IsAdministrator]

    def get(self, request):
        # Exclure les administrateurs et superusers de la liste
        queryset = User.objects.exclude(
            user_type='administrator'
        ).exclude(
            is_superuser=True
        ).order_by('-date_joined')

        # Filtres
        search = request.query_params.get('search', '').strip()
        role = request.query_params.get('role', 'all')
        user_status = request.query_params.get('status', 'all')

        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(username__icontains=search)
            )

        role_mapping = {
            'client': 'client',
            'technicien': 'technician',
            'vendeur': 'vendor',
            'administrateur': 'administrator',
        }
        if role != 'all' and role in role_mapping:
            queryset = queryset.filter(user_type=role_mapping[role])

        if user_status == 'refuse':
            # Refusé = techniciens avec approval_status='rejected'
            queryset = queryset.filter(user_type='technician', technician_profile__approval_status='rejected')
        elif user_status == 'en_attente':
            # En attente = techniciens avec approval_status='pending'
            queryset = queryset.filter(user_type='technician', technician_profile__approval_status='pending')
        elif user_status == 'actif':
            # Actif = techniciens approuvés OU autres utilisateurs avec is_active=True
            from django.db.models import Q
            queryset = queryset.filter(
                Q(user_type='technician', technician_profile__approval_status='approved') |
                Q(~Q(user_type='technician'), is_active=True)
            )
        elif user_status == 'bloque':
            # Bloqué = non-techniciens avec is_active=False
            queryset = queryset.filter(is_active=False).exclude(user_type='technician')
        # 'all' → pas de filtre

        # Pagination
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        paginator.page_size = int(request.query_params.get('limit', 20))
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        serializer = AdminUserListSerializer(
            paginated_queryset, many=True, context={'request': request}
        )

        # Stats
        all_users = User.objects.exclude(user_type='administrator').exclude(is_superuser=True)
        total = all_users.count()
        actifs = (
            all_users.filter(user_type='technician', technician_profile__approval_status='approved').count() +
            all_users.exclude(user_type='technician').filter(is_active=True).count()
        )
        en_attente = all_users.filter(user_type='technician', technician_profile__approval_status='pending').count()
        bloques = all_users.exclude(user_type='technician').filter(is_active=False).count()
        techniciens_en_attente = en_attente

        stats = {
            'total': total,
            'actifs': actifs,
            'enAttente': en_attente,
            'bloques': bloques,
            'techniciensEnAttente': techniciens_en_attente,
        }

        return Response({
            'count': paginator.page.paginator.count,
            'results': serializer.data,
            'stats': stats,
        })


class AdminUserDetailView(APIView):
    """
    GET /api/admin/users/<pk>/
    Détail complet d'un utilisateur.
    """
    permission_classes = [IsAdministrator]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        serializer = AdminUserDetailSerializer(user, context={'request': request})
        return Response(serializer.data)


class UserApprouverView(APIView):
    """
    POST /api/admin/users/<pk>/approuver/
    Active le compte d'un utilisateur et envoie un email de confirmation au technicien.
    """
    permission_classes = [IsAdministrator]

    def post(self, request, pk):
        from django.core.mail import send_mail
        from django.conf import settings

        user = get_object_or_404(User, pk=pk)
        user.is_active = True
        user.save(update_fields=['is_active'])

        # Mettre à jour l'approval_status pour les techniciens
        if user.user_type == 'technician':
            tech = getattr(user, 'technician_profile', None)
            if not tech:
                return Response({'detail': 'Profil technicien introuvable.'}, status=status.HTTP_400_BAD_REQUEST)

            documents = list(tech.documents.all())
            if not documents:
                return Response(
                    {'detail': 'Impossible d’approuver : aucun document justificatif n’a été déposé.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            invalid_docs = [doc for doc in documents if doc.validation_status != 'valide']
            if invalid_docs:
                return Response(
                    {
                        'detail': 'Impossible d’approuver : tous les documents doivent être validés un par un.',
                        'documents_non_valides': [
                            {
                                'id': doc.id,
                                'name': doc.display_name,
                                'status': doc.validation_status,
                                'commentaire': doc.validation_comment,
                            }
                            for doc in invalid_docs
                        ],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tech.approval_status = 'approved'
            tech.rejection_reason = ''
            tech.save(update_fields=['approval_status', 'rejection_reason'])

            # ── Email de confirmation au technicien ─────────────────────────
            try:
                nom = user.get_full_name() or user.username

                sujet = "Cartronic — Votre demande d'inscription a été acceptée 🎉"
                corps = (
                    f"Bonjour {nom},\n\n"
                    f"Bonne nouvelle ! Votre demande d'inscription en tant que technicien "
                    f"sur la plateforme Cartronic a été examinée et acceptée.\n\n"
                    f"Votre compte est maintenant actif. Vous pouvez dès à présent vous "
                    f"connecter et commencer à recevoir des demandes d'intervention :\n"
                    f"Bienvenue dans l'équipe Cartronic !\n\n"
                    f"Cordialement,\n"
                    f"L'équipe Cartronic"
                )

                send_mail(
                    sujet,
                    corps,
                    getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    [user.email],
                    fail_silently=False,
                )
                print(f"[APPROBATION] ✅ Email envoyé à {user.email}")
            except Exception as e:
                print(f"[APPROBATION] ❌ Erreur envoi email : {e}")

        # Créer une notification pour les autres admins
        _create_notification_for_admins(
            type_notif='utilisateurs',
            titre=f"Compte approuvé : {user.get_full_name() or user.username}",
            message=f"Le compte de {user.get_full_name() or user.email} a été approuvé.",
            lien_type='user',
            lien_id=str(user.pk),
            exclude_user=request.user,
        )

        return Response({
            'message': f"Compte de {user.get_full_name() or user.username} approuvé. Un email de confirmation lui a été envoyé.",
            'status': 'actif',
        })


class UserRefuserView(APIView):
    """
    POST /api/admin/users/<pk>/refuser/
    Body: { "motif": "..." }
    Désactive le compte avec motif de refus.
    """
    permission_classes = [IsAdministrator]

    def post(self, request, pk):
        from django.core.mail import send_mail
        from django.conf import settings

        user = get_object_or_404(User, pk=pk)
        motif = request.data.get('motif', '')

        # Mettre à jour l'approval_status pour les techniciens
        if user.user_type == 'technician':
            try:
                tech = user.technician_profile
                tech.approval_status = 'rejected'
                tech.rejection_reason = motif
                tech.save(update_fields=['approval_status', 'rejection_reason'])
            except Exception:
                pass

            # ── Email de refus au technicien ─────────────────────────
            try:
                nom = user.get_full_name() or user.username

                sujet = "Cartronic — Votre demande d'inscription a été refusée"
                corps = (
                    f"Bonjour {nom},\n\n"
                    f"Nous avons examiné votre demande d'inscription en tant que technicien "
                    f"sur la plateforme Cartronic.\n\n"
                    f"Malheureusement, votre demande n'a pas pu être acceptée.\n"
                )

                if motif:
                    corps += f"Motif du refus : {motif}\n\n"

                # Récupérer les documents refusés
                rejected_documents = tech.documents.filter(validation_status='invalide')
                if rejected_documents.exists():
                    corps += "Documents refusés :\n"
                    for doc in rejected_documents:
                        corps += f"- {doc.display_name}"
                        if doc.validation_comment:
                            corps += f" ({doc.validation_comment})"
                        corps += "\n"
                    corps += "\n"

                corps += (
                    f"Que faire maintenant ? \n"
                    f"Vous pouvez soumettre une nouvelle demande à en remplissant le formulaire avec les documents corrects.\n\n"
                    f"Assurez-vous de corriger les points identifiés et de fournir des documents clairs et lisibles.\n\n"
                    f"Nous vous encourageons à réessayer, et nous restons à votre disposition pour toute question ou assistance.\n\n"
                    f"Cordialement,\n"
                    f"L'équipe Cartronic"
                )

                send_mail(
                    sujet,
                    corps,
                    getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    [user.email],
                    fail_silently=False,
                )
                print(f"[REFUS] ✅ Email envoyé à {user.email}")
            except Exception as e:
                print(f"[REFUS] ❌ Erreur envoi email : {e}")
        else:
            # Pour les autres utilisateurs, les bloquer
            user.is_active = False
            user.save(update_fields=['is_active'])

        _create_notification_for_admins(
            type_notif='utilisateurs',
            titre=f"Compte refusé : {user.get_full_name() or user.username}",
            message=f"Le compte de {user.get_full_name() or user.email} a été refusé. Motif : {motif}",
            lien_type='user',
            lien_id=str(user.pk),
            exclude_user=request.user,
        )

        return Response({
            'message': f"Compte de {user.get_full_name() or user.username} refusé.",
            'status': 'refuse',
            'motif': motif,
        })


class UserBloquerView(APIView):
    """
    POST /api/admin/users/<pk>/bloquer/
    Désactive temporairement un compte.
    """
    permission_classes = [IsAdministrator]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.is_active = False
        user.save(update_fields=['is_active'])

        return Response({
            'message': f"Compte de {user.get_full_name() or user.username} bloqué.",
            'status': 'bloque',
        })


class UserDebloquerView(APIView):
    """
    POST /api/admin/users/<pk>/debloquer/
    Réactive un compte bloqué.
    """
    permission_classes = [IsAdministrator]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.is_active = True
        user.save(update_fields=['is_active'])

        return Response({
            'message': f"Compte de {user.get_full_name() or user.username} débloqué.",
            'status': 'actif',
        })


class DocumentContentView(APIView):
    """
    GET /api/admin/users/<user_pk>/documents/<doc_pk>/view/
    Renvoie le contenu réel du document technicien depuis PostgreSQL.

    Cette vue évite les erreurs /media introuvables et fonctionne sans Render Disk.
    Elle est protégée par le rôle administrateur.
    """
    permission_classes = [IsAdministrator]

    def get(self, request, user_pk, doc_pk):
        user = get_object_or_404(User, pk=user_pk)
        doc = get_object_or_404(TechnicianDocument, pk=doc_pk, technician__user=user)

        content = None
        if doc.has_database_file:
            content = bytes(doc.file_data)
        elif doc.file:
            # Fallback ancien stockage /media : utile uniquement si le fichier existe encore.
            try:
                doc.file.open('rb')
                content = doc.file.read()
                doc.file.close()
            except Exception:
                content = None

        if not content:
            raise Http404(
                "Document introuvable : le fichier n'est pas présent en base de données "
                "et l'ancien fichier /media n'existe plus."
            )

        filename = (doc.display_name or f'document-{doc.pk}').replace('"', '')
        response = HttpResponse(content, content_type=doc.safe_content_type)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['Cache-Control'] = 'private, no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response


class DocumentStatusView(APIView):
    """
    PATCH /api/admin/users/<user_pk>/documents/<doc_pk>/
    Body: { "status": "valide"|"invalide"|"non_verifie", "commentaire": "..." }
    Met à jour le statut de validation d'un document technicien.
    """
    permission_classes = [IsAdministrator]

    def patch(self, request, user_pk, doc_pk):
        from apps.users.models import TechnicianDocument

        user = get_object_or_404(User, pk=user_pk)
        doc = get_object_or_404(TechnicianDocument, pk=doc_pk, technician__user=user)

        new_status = request.data.get('status')
        commentaire = request.data.get('commentaire', '')

        valid_statuses = ['non_verifie', 'valide', 'invalide']
        if new_status not in valid_statuses:
            return Response(
                {'error': f"Statut invalide. Choix : {', '.join(valid_statuses)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mettre à jour et sauvegarder les champs de validation
        doc.validation_status = new_status
        doc.validation_comment = commentaire
        doc.save(update_fields=['validation_status', 'validation_comment'])

        return Response({
            'message': 'Statut du document mis à jour.',
            'docId': str(doc.pk),
            'status': new_status,
            'commentaire': commentaire,
            'label': doc.display_name,
            'viewUrl': request.build_absolute_uri(
                f'/api/admin/users/{user.pk}/documents/{doc.pk}/view/'
            ),
        })


# ═══════════════════════════════════════════════════════════════════════════════
# MODÉRATION (Signalements)
# ═══════════════════════════════════════════════════════════════════════════════

class SignalementListView(APIView):
    """
    GET  /api/admin/signalements/
    POST /api/admin/signalements/
    """
    permission_classes = [IsAdministrator]

    def get(self, request):
        queryset = Signalement.objects.select_related(
            'signale_par', 'utilisateur_vise', 'traite_par'
        ).all()

        search = request.query_params.get('search', '').strip()
        filtre_status = request.query_params.get('status', 'all')
        filtre_type = request.query_params.get('type', 'all')

        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(contenu__icontains=search) |
                Q(raison__icontains=search) |
                Q(signale_par_nom__icontains=search)
            )

        if filtre_status != 'all':
            queryset = queryset.filter(status=filtre_status)

        if filtre_type != 'all':
            queryset = queryset.filter(type=filtre_type)

        serializer = SignalementSerializer(queryset, many=True)

        # Stats globales
        all_sigs = Signalement.objects.all()
        stats = {
            'total': all_sigs.count(),
            'enAttente': all_sigs.filter(status='en_attente').count(),
            'traites': all_sigs.filter(status='traite').count(),
            'rejetes': all_sigs.filter(status='rejete').count(),
        }

        return Response({
            'results': serializer.data,
            'stats': stats,
        })

    def post(self, request):
        serializer = SignalementCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        signalement = serializer.save()

        # Notifier les admins
        _create_notification_for_admins(
            type_notif='moderation',
            titre="Nouveau signalement reçu",
            message=f"Un signalement a été soumis concernant : {signalement.contenu}",
            lien_type='signalement',
            lien_id=str(signalement.pk),
        )

        return Response(
            SignalementSerializer(signalement).data,
            status=status.HTTP_201_CREATED
        )


class SignalementTraiterView(APIView):
    """
    POST /api/admin/signalements/<pk>/traiter/
    Body (optionnel): { "note": "..." }
    """
    permission_classes = [IsAdministrator]

    def post(self, request, pk):
        signalement = get_object_or_404(Signalement, pk=pk)
        ser = SignalementTraiterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        signalement.status = 'traite'
        signalement.note_admin = ser.validated_data.get('note', '')
        signalement.traite_par = request.user
        signalement.traite_le = timezone.now()
        signalement.save(update_fields=['status', 'note_admin', 'traite_par', 'traite_le', 'updated_at'])

        return Response(SignalementSerializer(signalement).data)


class SignalementRejeterView(APIView):
    """
    POST /api/admin/signalements/<pk>/rejeter/
    Body (optionnel): { "note": "..." }
    """
    permission_classes = [IsAdministrator]

    def post(self, request, pk):
        signalement = get_object_or_404(Signalement, pk=pk)
        ser = SignalementTraiterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        signalement.status = 'rejete'
        signalement.note_admin = ser.validated_data.get('note', '')
        signalement.traite_par = request.user
        signalement.traite_le = timezone.now()
        signalement.save(update_fields=['status', 'note_admin', 'traite_par', 'traite_le', 'updated_at'])

        return Response(SignalementSerializer(signalement).data)


# ═══════════════════════════════════════════════════════════════════════════════
# INTERVENTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class AdminInterventionListView(APIView):
    """
    GET /api/admin/interventions/
    Paramètres : search, type, status
    """
    permission_classes = [IsAdministrator]

    def get(self, request):
        queryset = Reservation.objects.select_related(
            'client__user', 'technician__user', 'vehicle'
        ).prefetch_related('invoice').order_by('-created_at')

        search = request.query_params.get('search', '').strip()
        filtre_status = request.query_params.get('status', 'all')
        filtre_type = request.query_params.get('type', 'all')

        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(description__icontains=search) |
                Q(client__user__first_name__icontains=search) |
                Q(client__user__last_name__icontains=search) |
                Q(technician__user__first_name__icontains=search) |
                Q(technician__user__last_name__icontains=search)
            )

        # Mapping status frontend → backend
        status_mapping = {
            'en_attente': ['pending', 'confirmed'],
            'en_cours': ['technician_dispatched', 'technician_arrived', 'in_progress',
                         'diagnosis_submitted', 'awaiting_client_approval', 'parts_ordered', 'ready_for_pickup'],
            'termine': ['completed'],
            'annule': ['cancelled'],
        }
        if filtre_status != 'all' and filtre_status in status_mapping:
            queryset = queryset.filter(status__in=status_mapping[filtre_status])

        # Mapping type frontend → backend service_type
        type_mapping = {
            'vidange': ['scheduled_maintenance', 'preventive_maintenance'],
            'diagnostic': ['emergency', 'diagnosis'],
            'freinage': ['specific_repair'],
            'revision': ['scheduled_maintenance'],
            'climatisation': ['specific_repair'],
            'electricite': ['specific_repair'],
            'carrosserie': ['specific_repair'],
            'autre': ['roadside_repair', 'towing', 'specific_repair'],
        }
        if filtre_type != 'all' and filtre_type in type_mapping:
            queryset = queryset.filter(service_type__in=type_mapping[filtre_type])

        serializer = AdminInterventionSerializer(
            queryset, many=True, context={'request': request}
        )

        # Stats
        all_res = Reservation.objects.all()
        chiffre = float(get_reservations_revenue(all_res))
        stats = {
            'total': all_res.count(),
            'terminees': all_res.filter(status='completed').count(),
            'enCours': all_res.filter(status__in=['in_progress', 'technician_dispatched',
                                                    'technician_arrived']).count(),
            'enAttente': all_res.filter(status__in=['pending', 'confirmed']).count(),
            'annulees': all_res.filter(status='cancelled').count(),
            'chiffreAffaires': chiffre,
        }

        return Response({
            'results': serializer.data,
            'stats': stats,
        })


class AdminInterventionDetailView(APIView):
    """
    GET /api/admin/interventions/<pk>/
    """
    permission_classes = [IsAdministrator]

    def get(self, request, pk):
        reservation = get_object_or_404(
            Reservation.objects.select_related(
                'client__user', 'technician__user', 'vehicle'
            ).prefetch_related('invoice', 'diagnostic', 'work_progress'),
            pk=pk
        )
        serializer = AdminInterventionSerializer(reservation, context={'request': request})
        return Response(serializer.data)



class AdminTechnicianPerformanceView(APIView):
    """
    GET /api/admin/techniciens/performance/
    Donne à l'admin une vision claire des revenus et interventions par technicien.
    """
    permission_classes = [IsAdministrator]

    def get(self, request):
        now = timezone.now()
        start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_week = now - timedelta(days=7)

        technicians = Technician.objects.select_related('user').prefetch_related('documents').order_by('user__first_name', 'user__last_name')
        results = []

        for tech in technicians:
            reservations = Reservation.objects.filter(technician=tech)

            revenu_total = float(get_reservations_revenue(reservations))
            revenu_mois = float(get_reservations_revenue(reservations.filter(created_at__gte=start_month)))
            revenu_semaine = float(get_reservations_revenue(reservations.filter(created_at__gte=start_week)))

            interventions_total = reservations.count()
            interventions_terminees = reservations.filter(status='completed').count()
            interventions_annulees = reservations.filter(status='cancelled').count()
            interventions_en_cours = reservations.filter(
                status__in=[
                    'confirmed', 'technician_dispatched', 'technician_arrived', 'in_progress',
                    'diagnosis_submitted', 'awaiting_client_approval', 'parts_ordered', 'ready_for_pickup',
                ]
            ).count()
            montant_en_attente = float(
                Invoice.objects.filter(
                    reservation__technician=tech,
                    payment_status__in=['pending', 'partial'],
                ).aggregate(total=Sum('balance_due'))['total'] or 0
            )
            note_moyenne = Evaluation.objects.filter(technician=tech).aggregate(avg=Avg('note'))['avg'] or 0
            derniere = reservations.order_by('-date').first()
            docs_total = tech.documents.count()
            docs_valides = tech.documents.filter(validation_status='valide').count()
            docs_invalides = tech.documents.filter(validation_status='invalide').count()
            docs_non_verifies = tech.documents.filter(validation_status='non_verifie').count()

            user = tech.user
            results.append({
                'technicienId': tech.id,
                'userId': user.id,
                'nom': user.last_name or user.username,
                'prenom': user.first_name,
                'email': user.email,
                'telephone': user.telephone,
                'status': tech.status,
                'approvalStatus': tech.approval_status,
                'specialites': tech.specializations or [],
                'anneesExperience': tech.years_experience,
                'revenuTotal': revenu_total,
                'revenuMois': revenu_mois,
                'revenuSemaine': revenu_semaine,
                'montantEnAttente': montant_en_attente,
                'interventionsTotal': interventions_total,
                'interventionsTerminees': interventions_terminees,
                'interventionsEnCours': interventions_en_cours,
                'interventionsAnnulees': interventions_annulees,
                'tauxCompletion': round((interventions_terminees / interventions_total) * 100, 1) if interventions_total else 0,
                'noteMoyenne': round(float(note_moyenne), 2),
                'documents': {
                    'total': docs_total,
                    'valides': docs_valides,
                    'invalides': docs_invalides,
                    'nonVerifies': docs_non_verifies,
                    'aVerifier': docs_non_verifies,
                },
                'derniereIntervention': {
                    'id': derniere.id,
                    'date': derniere.date,
                    'status': derniere.status,
                    'description': derniere.description,
                } if derniere else None,
            })

        results.sort(key=lambda item: item['revenuTotal'], reverse=True)
        totals = {
            'techniciens': len(results),
            'revenuTotal': round(sum(item['revenuTotal'] for item in results), 2),
            'revenuMois': round(sum(item['revenuMois'] for item in results), 2),
            'revenuSemaine': round(sum(item['revenuSemaine'] for item in results), 2),
            'montantEnAttente': round(sum(item['montantEnAttente'] for item in results), 2),
            'interventionsTotal': sum(item['interventionsTotal'] for item in results),
            'interventionsTerminees': sum(item['interventionsTerminees'] for item in results),
            'interventionsEnCours': sum(item['interventionsEnCours'] for item in results),
            'interventionsAnnulees': sum(item['interventionsAnnulees'] for item in results),
        }
        return Response({'results': results, 'totals': totals})


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class NotificationListView(APIView):
    """
    GET /api/admin/notifications/
    Retourne les notifications de l'admin connecté.
    """
    permission_classes = [IsAdministrator]

    def get(self, request):
        notifications = Notification.objects.filter(
            destinataire=request.user
        ).order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)


class NotificationStatsView(APIView):
    """
    GET /api/admin/notifications/stats/
    """
    permission_classes = [IsAdministrator]

    def get(self, request):
        now = timezone.now()
        debut_semaine = now - timedelta(days=7)

        qs = Notification.objects.filter(destinataire=request.user)
        total = qs.count()
        non_lues = qs.filter(lu=False).count()
        lues = qs.filter(lu=True).count()
        cette_semaine = qs.filter(created_at__gte=debut_semaine).count()

        data = {
            'total': total,
            'nonLues': non_lues,
            'lues': lues,
            'cetteSemaine': cette_semaine,
        }
        serializer = NotificationStatsSerializer(data)
        return Response(serializer.data)


class NotificationMarkReadView(APIView):
    """
    PATCH /api/admin/notifications/<pk>/lu/
    Marque une notification comme lue.
    """
    permission_classes = [IsAdministrator]

    def patch(self, request, pk):
        notification = get_object_or_404(
            Notification, pk=pk, destinataire=request.user
        )
        notification.lu = True
        notification.lu_le = timezone.now()
        notification.save(update_fields=['lu', 'lu_le'])
        return Response(NotificationSerializer(notification).data)


class NotificationMarkAllReadView(APIView):
    """
    PATCH /api/admin/notifications/all/lu/
    Marque toutes les notifications comme lues.
    """
    permission_classes = [IsAdministrator]

    def patch(self, request):
        Notification.objects.filter(
            destinataire=request.user, lu=False
        ).update(lu=True, lu_le=timezone.now())
        return Response({'message': 'Toutes les notifications ont été marquées comme lues.'})


class NotificationDeleteView(APIView):
    """
    DELETE /api/admin/notifications/<pk>/
    """
    permission_classes = [IsAdministrator]

    def delete(self, request, pk):
        notification = get_object_or_404(
            Notification, pk=pk, destinataire=request.user
        )
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationDeleteReadView(APIView):
    """
    DELETE /api/admin/notifications/lues/
    Supprime toutes les notifications lues.
    """
    permission_classes = [IsAdministrator]

    def delete(self, request):
        count, _ = Notification.objects.filter(
            destinataire=request.user, lu=True
        ).delete()
        return Response({'message': f'{count} notification(s) supprimée(s).'})


# ═══════════════════════════════════════════════════════════════════════════════
# VENTES (Marketplace)
# ═══════════════════════════════════════════════════════════════════════════════

class VenteListView(APIView):
    """
    GET /api/admin/ventes/
    Paramètres : search, status
    """
    permission_classes = [IsAdministrator]

    def get(self, request):
        queryset = Commande.objects.select_related(
            'client__user'
        ).prefetch_related('lignes__produit').order_by('-created_at')

        search = request.query_params.get('search', '').strip()
        filtre_status = request.query_params.get('status', 'all')

        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(client__user__first_name__icontains=search) |
                Q(client__user__last_name__icontains=search) |
                Q(client__user__email__icontains=search)
            )

        if filtre_status != 'all':
            queryset = queryset.filter(status=filtre_status)

        serializer = AdminVenteSerializer(queryset, many=True, context={'request': request})

        # Stats
        all_commandes = Commande.objects.all()
        stats = {
            'total': all_commandes.count(),
            'enCours': all_commandes.filter(status__in=['pending', 'processing', 'shipped']).count(),
            'livrees': all_commandes.filter(status='delivered').count(),
            'annulees': all_commandes.filter(status='cancelled').count(),
            'chiffreAffaires': float(
                all_commandes.filter(status='delivered').aggregate(
                    total=Sum('prix_total')
                )['total'] or 0
            ),
        }

        return Response({
            'results': serializer.data,
            'stats': stats,
        })


# ═══════════════════════════════════════════════════════════════════════════════
# STATISTIQUES
# ═══════════════════════════════════════════════════════════════════════════════

class StatistiquesView(APIView):
    """
    GET /api/admin/statistiques/
    Statistiques complètes pour la page Statistiques du dashboard.
    """
    permission_classes = [IsAdministrator]

    def get(self, request):
        try:
            now = timezone.now()
            debut_mois = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            debut_semaine = now - timedelta(days=7)

            # Utilisateurs
            all_users = User.objects.all()
            
            # Évolution mensuelle (6 mois) - DONNÉES PRINCIPALES
            evolution = []
            for i in range(5, -1, -1):
                ref = now - timedelta(days=30 * i)
                debut = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if debut.month == 12:
                    fin = debut.replace(year=debut.year + 1, month=1)
                else:
                    fin = debut.replace(month=debut.month + 1)

                clients_mois = User.objects.filter(
                    user_type='client',
                    date_joined__gte=debut, 
                    date_joined__lt=fin
                ).count()
                techs_mois = User.objects.filter(
                    user_type='technician',
                    date_joined__gte=debut, 
                    date_joined__lt=fin
                ).count()

                evolution.append({
                    'mois': debut.strftime('%b %Y'),
                    'revenus': 0.0,
                    'interventions': 0,
                    'clients': clients_mois,
                    'techniciens': techs_mois,
                })

            # Données optionnelles - avec fallback
            try:
                from apps.reservations.models import Invoice, Reservation, Evaluation
                
                all_res = Reservation.objects.all()
                revenus_total = float(get_reservations_revenue(all_res))
                revenus_mois = float(get_reservations_revenue(all_res.filter(created_at__gte=debut_mois)))
                revenus_semaine = float(get_reservations_revenue(all_res.filter(created_at__gte=debut_semaine)))
                
                all_res = Reservation.objects.all()
                res_mois = all_res.filter(created_at__gte=debut_mois)
                interventions_total = all_res.count()
                interventions_mois = res_mois.count()
                interventions_terminees = all_res.filter(status='completed').count()
                interventions_annulees = all_res.filter(status='cancelled').count()
                
                note_moy = float(
                    Evaluation.objects.aggregate(moy=Avg('note'))['moy'] or 0
                )
                
                # Mettre à jour l'évolution avec les revenus
                for i, item in enumerate(evolution):
                    ref = now - timedelta(days=30 * (5 - i))
                    debut = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    if debut.month == 12:
                        fin = debut.replace(year=debut.year + 1, month=1)
                    else:
                        fin = debut.replace(month=debut.month + 1)
                    
                    rev_mois = float(get_reservations_revenue(
                        Reservation.objects.filter(created_at__gte=debut, created_at__lt=fin)
                    ))
                    item['revenus'] = rev_mois
                    item['interventions'] = Reservation.objects.filter(
                        created_at__gte=debut, created_at__lt=fin
                    ).count()
                
            except Exception as e:
                print(f"⚠️ Erreur chargement optionnel: {e}")
                revenus_total = 0.0
                revenus_mois = 0.0
                revenus_semaine = 0.0
                interventions_total = 0
                interventions_mois = 0
                interventions_terminees = 0
                interventions_annulees = 0
                note_moy = 0.0

            # Marketplace optionnelle
            try:
                from apps.marketplace.models import Commande
                all_commandes = Commande.objects.all()
                commandes_mois = all_commandes.filter(date__gte=debut_mois)
                
                try:
                    ventes_mois = float(
                        commandes_mois.filter(status='delivered').aggregate(
                            total=Sum('prix_total'))['total'] or 0
                    )
                except:
                    ventes_mois = 0.0
                
                commandes_total = all_commandes.count()
                commandes_mois_count = commandes_mois.count()
            except Exception as e:
                print(f"⚠️ Erreur marketplace: {e}")
                ventes_mois = 0.0
                commandes_total = 0
                commandes_mois_count = 0

            data = {
                'revenuTotal': revenus_total,
                'revenuMois': revenus_mois,
                'revenuSemaine': revenus_semaine,
                'interventionsTotal': interventions_total,
                'interventionsMois': interventions_mois,
                'interventionsTerminees': interventions_terminees,
                'interventionsAnnulees': interventions_annulees,
                'utilisateursTotal': all_users.count(),
                'nouveauxUtilisateursMois': all_users.filter(date_joined__gte=debut_mois).count(),
                'techniciensActifs': User.objects.filter(user_type='technician').count(),
                'clientsActifs': User.objects.filter(user_type='client').count(),
                'commandesTotal': commandes_total,
                'commandesMois': commandes_mois_count,
                'ventesMontantMois': ventes_mois,
                'noteMoyenneTechniciens': round(note_moy, 2),
                'evolutionMensuelle': evolution,
            }

            serializer = StatistiquesSerializer(data)
            return Response(serializer.data)
        except Exception as e:
            import traceback
            print(f"❌ ERREUR CRITIQUE StatistiquesView: {e}")
            print(traceback.format_exc())
            return Response({
                'error': str(e),
                'traceback': traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER INTERNE
# ═══════════════════════════════════════════════════════════════════════════════

def _create_notification_for_admins(
    type_notif: str,
    titre: str,
    message: str,
    lien_type: str = '',
    lien_id: str = '',
    exclude_user=None,
):
    """Crée une notification pour tous les administrateurs."""
    admins = User.objects.filter(user_type='administrator', is_active=True)
    if exclude_user:
        admins = admins.exclude(pk=exclude_user.pk)

    notifications = [
        Notification(
            destinataire=admin,
            type=type_notif,
            titre=titre,
            message=message,
            lien_type=lien_type,
            lien_id=lien_id,
        )
        for admin in admins
    ]
    Notification.objects.bulk_create(notifications)
