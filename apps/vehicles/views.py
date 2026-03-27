from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db.models import Count, Sum, Avg, Q
from datetime import datetime, timedelta

from apps.vehicles.models import Vehicle, MaintenanceRecord
from apps.vehicles.serializers import (
    VehicleSerializer, VehicleListSerializer, VehicleCreateSerializer,
    VehicleUpdateSerializer, VehicleDetailSerializer, VehicleStatsSerializer,
    MaintenanceRecordSerializer, MaintenanceRecordListSerializer,
    MaintenanceRecordCreateSerializer, MaintenanceStatsSerializer
)
from apps.vehicles.permissions import (
    IsVehicleOwner, CanCreateVehicle, CanManageMaintenance
)


# ==================== VEHICLE VIEWSET ====================

class VehicleViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les véhicules
    
    list: Lister les véhicules (filtrés selon l'utilisateur)
    retrieve: Récupérer un véhicule détaillé
    create: Créer un nouveau véhicule (clients uniquement)
    update: Mettre à jour un véhicule
    destroy: Supprimer un véhicule
    """
    queryset = Vehicle.objects.prefetch_related('proprietaires', 'maintenance_records')
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Choisir le serializer selon l'action"""
        if self.action == 'list':
            return VehicleListSerializer
        elif self.action == 'create':
            return VehicleCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return VehicleUpdateSerializer
        elif self.action == 'retrieve':
            return VehicleDetailSerializer
        return VehicleSerializer
    
    def perform_create(self, serializer):
        """Associer automatiquement le véhicule au client connecté"""
        user = self.request.user
        if not hasattr(user, 'client_profile'):
            raise PermissionDenied("Seuls les clients peuvent créer des véhicules")
        vehicle = serializer.save(client=user.client_profile)
        # IMPORTANT: la liste des véhicules côté client est filtrée via proprietaires__user.
        # Donc on s'assure que le client connecté est bien propriétaire.
        try:
            vehicle.proprietaires.add(user.client_profile)
        except Exception:
            pass

    def get_permissions(self):
        """Permissions selon l'action"""
        if self.action == 'create':
            return [CanCreateVehicle()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsVehicleOwner()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        """Filtrer les véhicules selon le type d'utilisateur"""
        user = self.request.user
        queryset = Vehicle.objects.prefetch_related('proprietaires', 'maintenance_records')
        
        # Filtrer selon le type d'utilisateur
        if user.user_type == 'client':
            # Compat: certains véhicules peuvent être liés via client (FK) ou via proprietaires (M2M)
            queryset = queryset.filter(Q(client__user=user) | Q(proprietaires__user=user)).distinct()
        elif user.user_type == 'technician':
            # Technicien voit les véhicules des réservations
            queryset = queryset.filter(
                proprietaires__reservations__technician__user=user
            ).distinct()
        elif user.user_type != 'administrator':
            queryset = queryset.none()
        
        # Filtres par query params
        marque = self.request.query_params.get('marque')
        if marque:
            queryset = queryset.filter(marque__icontains=marque)
        
        type_vehicule = self.request.query_params.get('type')
        if type_vehicule:
            queryset = queryset.filter(type_vehicule=type_vehicule)
        
        statut = self.request.query_params.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)
        
        annee_min = self.request.query_params.get('annee_min')
        annee_max = self.request.query_params.get('annee_max')
        
        if annee_min:
            queryset = queryset.filter(annee__gte=int(annee_min))
        if annee_max:
            queryset = queryset.filter(annee__lte=int(annee_max))
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'], permission_classes=[IsVehicleOwner])
    def add_owner(self, request, pk=None):
        """
        POST /api/vehicles/{id}/add_owner/
        Ajouter un propriétaire au véhicule
        
        Body: {"client_id": 1}
        """
        vehicle = self.get_object()
        client_id = request.data.get('client_id')
        
        if not client_id:
            return Response(
                {'error': 'client_id requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.users.models import Client
            client = Client.objects.get(id=client_id)
            vehicle.proprietaires.add(client)
            
            return Response({
                'message': 'Propriétaire ajouté',
                'proprietaires_count': vehicle.proprietaires.count()
            })
        except Client.DoesNotExist:
            return Response(
                {'error': 'Client non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsVehicleOwner])
    def remove_owner(self, request, pk=None):
        """
        POST /api/vehicles/{id}/remove_owner/
        Retirer un propriétaire du véhicule
        
        Body: {"client_id": 1}
        """
        vehicle = self.get_object()
        client_id = request.data.get('client_id')
        
        if not client_id:
            return Response(
                {'error': 'client_id requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.users.models import Client
            client = Client.objects.get(id=client_id)
            
            # Ne pas permettre de retirer le dernier propriétaire
            if vehicle.proprietaires.count() <= 1:
                return Response(
                    {'error': 'Impossible de retirer le dernier propriétaire'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            vehicle.proprietaires.remove(client)
            
            return Response({
                'message': 'Propriétaire retiré',
                'proprietaires_count': vehicle.proprietaires.count()
            })
        except Client.DoesNotExist:
            return Response(
                {'error': 'Client non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['patch'], permission_classes=[IsVehicleOwner])
    def update_kilometrage(self, request, pk=None):
        """
        PATCH /api/vehicles/{id}/update_kilometrage/
        Mettre à jour le kilométrage
        
        Body: {"kilometrage": 150000}
        """
        vehicle = self.get_object()
        new_kilometrage = request.data.get('kilometrage')
        
        if new_kilometrage is None:
            return Response(
                {'error': 'kilometrage requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_kilometrage = int(new_kilometrage)
            
            if new_kilometrage < vehicle.kilometrage:
                return Response(
                    {'error': f'Le kilométrage ne peut pas être inférieur à {vehicle.kilometrage} km'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            vehicle.kilometrage = new_kilometrage
            vehicle.save()
            
            return Response({
                'message': 'Kilométrage mis à jour',
                'kilometrage': vehicle.kilometrage
            })
        except ValueError:
            return Response(
                {'error': 'Kilométrage invalide'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def maintenance_history(self, request, pk=None):
        """
        GET /api/vehicles/{id}/maintenance_history/
        Historique de maintenance du véhicule
        """
        vehicle = self.get_object()
        maintenances = vehicle.maintenance_records.all()
        
        serializer = MaintenanceRecordListSerializer(maintenances, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        GET /api/vehicles/{id}/stats/
        Statistiques du véhicule
        """
        vehicle = self.get_object()
        
        maintenances = vehicle.maintenance_records.all()
        
        stats = {
            'total_maintenance': maintenances.count(),
            'total_maintenance_cost': float(maintenances.aggregate(
                Sum('cout')
            )['cout__sum'] or 0),
            'avg_maintenance_cost': float(maintenances.aggregate(
                Avg('cout')
            )['cout__avg'] or 0),
            'last_maintenance': None,
            'maintenance_by_type': {},
            'age_years': vehicle.age,
            'proprietaires_count': vehicle.proprietaires.count(),
        }
        
        # Dernière maintenance
        last = maintenances.first()
        if last:
            stats['last_maintenance'] = {
                'date': last.date,
                'type': last.get_type_maintenance_display(),
                'cout': float(last.cout)
            }
        
        # Par type de maintenance
        by_type = maintenances.values('type_maintenance').annotate(
            count=Count('id'),
            total_cost=Sum('cout')
        )
        
        for item in by_type:
            type_key = dict(MaintenanceRecord.TYPE_CHOICES)[item['type_maintenance']]
            stats['maintenance_by_type'][type_key] = {
                'count': item['count'],
                'total_cost': float(item['total_cost'])
            }
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def my_vehicles(self, request):
        """
        GET /api/vehicles/my_vehicles/
        Véhicules de l'utilisateur connecté
        """
        if request.user.user_type != 'client':
            return Response(
                {'error': 'Disponible uniquement pour les clients'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        vehicles = Vehicle.objects.filter(proprietaires__user=request.user)
        serializer = VehicleListSerializer(vehicles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        GET /api/vehicles/statistics/
        Statistiques globales des véhicules
        """
        user = request.user
        
        # Filtrer selon l'utilisateur
        if user.user_type == 'client':
            queryset = Vehicle.objects.filter(proprietaires__user=user)
        elif user.user_type == 'administrator':
            queryset = Vehicle.objects.all()
        else:
            queryset = Vehicle.objects.none()
        
        # Statistiques
        total = queryset.count()
        
        by_type = {}
        for choice in Vehicle.TYPE_CHOICES:
            count = queryset.filter(type_vehicule=choice[0]).count()
            by_type[choice[1]] = count
        
        by_status = {}
        for choice in Vehicle.STATUS_CHOICES:
            count = queryset.filter(statut=choice[0]).count()
            by_status[choice[1]] = count
        
        avg_age = queryset.aggregate(Avg('annee'))['annee__avg']
        if avg_age:
            avg_age = datetime.now().year - avg_age
        else:
            avg_age = 0
        
        total_value = queryset.aggregate(Sum('prix'))['prix__sum'] or 0
        
        stats = {
            'total_vehicles': total,
            'by_type': by_type,
            'by_status': by_status,
            'avg_age': round(avg_age, 1),
            'total_value': float(total_value)
        }
        
        serializer = VehicleStatsSerializer(stats)
        return Response(serializer.data)


# ==================== MAINTENANCE VIEWSET ====================

class MaintenanceRecordViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les maintenances
    
    list: Lister les maintenances
    retrieve: Récupérer une maintenance
    create: Créer une maintenance
    update: Mettre à jour une maintenance
    destroy: Supprimer une maintenance
    """
    queryset = MaintenanceRecord.objects.select_related('vehicle', 'technician__user')
    permission_classes = [CanManageMaintenance]
    
    def get_serializer_class(self):
        """Choisir le serializer selon l'action"""
        if self.action == 'list':
            return MaintenanceRecordListSerializer
        elif self.action == 'create':
            return MaintenanceRecordCreateSerializer
        return MaintenanceRecordSerializer
    
    def get_queryset(self):
        """Filtrer les maintenances selon le type d'utilisateur"""
        user = self.request.user
        queryset = MaintenanceRecord.objects.select_related('vehicle', 'technician__user')
        
        # Filtrer selon le type d'utilisateur
        if user.user_type == 'client':
            queryset = queryset.filter(vehicle__proprietaires__user=user)
        elif user.user_type == 'technician':
            queryset = queryset.filter(technician__user=user)
        elif user.user_type != 'administrator':
            queryset = queryset.none()
        
        # Filtres par query params
        vehicle_id = self.request.query_params.get('vehicle')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        
        type_maintenance = self.request.query_params.get('type')
        if type_maintenance:
            queryset = queryset.filter(type_maintenance=type_maintenance)
        
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        return queryset.order_by('-date')
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        GET /api/maintenance/statistics/
        Statistiques des maintenances
        """
        user = request.user
        
        # Filtrer selon l'utilisateur
        if user.user_type == 'client':
            queryset = MaintenanceRecord.objects.filter(vehicle__proprietaires__user=user)
        elif user.user_type == 'technician':
            queryset = MaintenanceRecord.objects.filter(technician__user=user)
        elif user.user_type == 'administrator':
            queryset = MaintenanceRecord.objects.all()
        else:
            queryset = MaintenanceRecord.objects.none()
        
        total = queryset.count()
        
        by_type = {}
        for choice in MaintenanceRecord.TYPE_CHOICES:
            count = queryset.filter(type_maintenance=choice[0]).count()
            by_type[choice[1]] = count
        
        total_cost = queryset.aggregate(Sum('cout'))['cout__sum'] or 0
        avg_cost = queryset.aggregate(Avg('cout'))['cout__avg'] or 0
        
        stats = {
            'total_maintenance': total,
            'by_type': by_type,
            'total_cost': float(total_cost),
            'avg_cost': float(avg_cost)
        }
        
        serializer = MaintenanceStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        GET /api/maintenance/recent/?limit=10
        Dernières maintenances
        """
        limit = int(request.query_params.get('limit', 10))
        
        user = request.user
        if user.user_type == 'client':
            queryset = MaintenanceRecord.objects.filter(
                vehicle__proprietaires__user=user
            )
        elif user.user_type == 'technician':
            queryset = MaintenanceRecord.objects.filter(technician__user=user)
        elif user.user_type == 'administrator':
            queryset = MaintenanceRecord.objects.all()
        else:
            queryset = MaintenanceRecord.objects.none()
        
        maintenances = queryset.select_related('vehicle', 'technician__user').order_by('-date')[:limit]
        
        serializer = MaintenanceRecordListSerializer(maintenances, many=True)
        return Response(serializer.data)