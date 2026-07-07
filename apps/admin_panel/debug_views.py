"""
Endpoint temporaire de debug pour vérifier les statistiques
À supprimer après le debug
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.db.models import Min, Max
from apps.users.models import User

class DebugStatsView(APIView):
    def get(self, request):
        now = timezone.now()
        
        # 1. Nombre total
        total = User.objects.count()
        
        # 2. Par type
        by_type = {}
        for utype in ['client', 'technician', 'vendor', 'administrator']:
            by_type[utype] = User.objects.filter(user_type=utype).count()
        
        # 3. Dates
        min_date = User.objects.aggregate(Min('date_joined'))['date_joined__min']
        max_date = User.objects.aggregate(Max('date_joined'))['date_joined__max']
        null_count = User.objects.filter(date_joined__isnull=True).count()
        
        # 4. Derniers utilisateurs
        recent_users = []
        for u in User.objects.all().order_by('-date_joined')[:5]:
            recent_users.append({
                'username': u.username,
                'type': u.user_type,
                'date_joined': u.date_joined.isoformat() if u.date_joined else None
            })
        
        # 5. Variations
        debut_30j = now - timedelta(days=30)
        debut_30j_prev = now - timedelta(days=60)
        
        users_30j = User.objects.filter(
            user_type__in=['client', 'technician', 'vendor', 'administrator'],
            date_joined__gte=debut_30j
        ).count()
        users_30j_prev = User.objects.filter(
            user_type__in=['client', 'technician', 'vendor', 'administrator'],
            date_joined__gte=debut_30j_prev,
            date_joined__lt=debut_30j
        ).count()
        
        return Response({
            'total_users': total,
            'by_type': by_type,
            'min_date': min_date.isoformat() if min_date else None,
            'max_date': max_date.isoformat() if max_date else None,
            'null_date_count': null_count,
            'recent_users': recent_users,
            'users_30d': users_30j,
            'users_30_60d': users_30j_prev,
            'current_time': now.isoformat(),
        })
