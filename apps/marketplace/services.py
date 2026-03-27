from django.db import transaction
from django.db.models import Sum, Count, Avg
from apps.marketplace.models import Commande, LigneCommande, Produit
import uuid


@transaction.atomic
def create_commande(client, commande_data):
    """
    Créer une commande avec ses lignes
    
    Args:
        client: Instance de Client
        commande_data: Dict contenant les données de la commande
    
    Returns:
        Commande créée
    
    Raises:
        ValueError: Si stock insuffisant ou produit introuvable
    """
    # Créer la commande
    commande = Commande.objects.create(
        id=f"CMD-{uuid.uuid4().hex[:8].upper()}",
        client=client,
        adresse_livraison=commande_data['adresse_livraison'],
        telephone_livraison=commande_data.get('telephone_livraison', client.user.telephone),
        prix_total=0,
        frais_livraison=commande_data.get('frais_livraison', 0),
        status='pending',
        notes=commande_data.get('notes', '')
    )
    
    total = 0
    
    # Créer les lignes de commande
    for ligne_data in commande_data['lignes']:
        produit = Produit.objects.select_for_update().get(id=ligne_data['produit_id'])
        quantite = int(ligne_data['quantite'])
        
        # Vérifier le stock
        if produit.stock < quantite:
            raise ValueError(f"Stock insuffisant pour {produit.nom}. Disponible: {produit.stock}")
        
        # Créer la ligne
        LigneCommande.objects.create(
            commande=commande,
            produit=produit,
            quantite=quantite,
            prix_unitaire=produit.prix
        )
        
        # Décrémenter le stock
        produit.stock -= quantite
        produit.save()
        
        total += float(produit.prix) * quantite
    
    # Mettre à jour le prix total
    commande.prix_total = total
    commande.save()
    
    return commande


@transaction.atomic
def update_commande_status(commande, new_status):
    """
    Mettre à jour le statut d'une commande
    
    Args:
        commande: Instance de Commande
        new_status: Nouveau statut
    """
    from django.utils import timezone
    
    old_status = commande.status
    commande.status = new_status
    
    # Mettre à jour les dates selon le statut
    if new_status == 'shipped' and not commande.date_expedition:
        commande.date_expedition = timezone.now()
    elif new_status == 'delivered' and not commande.date_livraison:
        commande.date_livraison = timezone.now()
    
    commande.save()
    
    # TODO: Envoyer notifications
    # if new_status == 'shipped':
    #     send_shipping_notification.delay(commande.id)
    # elif new_status == 'delivered':
    #     send_delivery_confirmation.delay(commande.id)


@transaction.atomic
def cancel_commande(commande):
    """
    Annuler une commande et restaurer les stocks
    
    Args:
        commande: Instance de Commande
    
    Raises:
        ValueError: Si la commande ne peut pas être annulée
    """
    if commande.status in ['delivered', 'cancelled']:
        raise ValueError(f"Impossible d'annuler une commande {commande.get_status_display()}")
    
    # Restaurer les stocks
    for ligne in commande.lignes.all():
        produit = ligne.produit
        produit.stock += ligne.quantite
        produit.save()
    
    # Mettre à jour le statut
    commande.status = 'cancelled'
    commande.save()


def get_best_selling_products(limit=10):
    """
    Récupérer les produits les plus vendus
    
    Args:
        limit: Nombre de produits à retourner
    
    Returns:
        QuerySet de produits
    """
    return Produit.objects.annotate(
        total_sold=Sum('lignecommande__quantite')
    ).filter(
        total_sold__isnull=False
    ).order_by('-total_sold')[:limit]


def get_low_stock_products(threshold=10):
    """
    Récupérer les produits avec stock faible
    
    Args:
        threshold: Seuil de stock
    
    Returns:
        QuerySet de produits
    """
    return Produit.objects.filter(
        stock__lte=threshold,
        is_active=True
    ).order_by('stock')


def get_product_rating(produit):
    """
    Calculer le rating moyen d'un produit
    
    Args:
        produit: Instance de Produit
    
    Returns:
        dict avec moyenne et nombre d'avis
    """
    from apps.marketplace.models import Avis
    
    avis = Avis.objects.filter(produit=produit)
    
    return {
        'average': avis.aggregate(Avg('note'))['note__avg'] or 0,
        'count': avis.count(),
        'distribution': {
            '5': avis.filter(note=5).count(),
            '4': avis.filter(note=4).count(),
            '3': avis.filter(note=3).count(),
            '2': avis.filter(note=2).count(),
            '1': avis.filter(note=1).count(),
        }
    }


def get_marketplace_stats(start_date=None, end_date=None):
    """
    Obtenir des statistiques sur le marketplace
    
    Args:
        start_date: Date de début (optionnel)
        end_date: Date de fin (optionnel)
    
    Returns:
        dict: Statistiques
    """
    commandes_qs = Commande.objects.all()
    
    if start_date:
        commandes_qs = commandes_qs.filter(date__gte=start_date)
    if end_date:
        commandes_qs = commandes_qs.filter(date__lte=end_date)
    
    stats = {
        'total_produits': Produit.objects.filter(is_active=True).count(),
        'total_commandes': commandes_qs.count(),
        'commandes_by_status': {
            'pending': commandes_qs.filter(status='pending').count(),
            'processing': commandes_qs.filter(status='processing').count(),
            'shipped': commandes_qs.filter(status='shipped').count(),
            'delivered': commandes_qs.filter(status='delivered').count(),
            'cancelled': commandes_qs.filter(status='cancelled').count(),
        },
        'revenus': {
            'total': float(commandes_qs.filter(
                status='delivered'
            ).aggregate(Sum('prix_total'))['prix_total__sum'] or 0),
            'moyen': float(commandes_qs.filter(
                status='delivered'
            ).aggregate(Avg('prix_total'))['prix_total__avg'] or 0),
        },
        'produits_stock_faible': get_low_stock_products().count(),
    }
    
    return stats


@transaction.atomic
def process_payment(commande, payment_method='cash'):
    """
    Traiter le paiement d'une commande
    
    Args:
        commande: Instance de Commande
        payment_method: Méthode de paiement
    
    Returns:
        bool: Succès du paiement
    """
    from django.utils import timezone
    
    # TODO: Intégrer avec un système de paiement réel
    # Pour l'instant, on simule un paiement cash
    
    commande.payment_status = 'paid'
    commande.date_paiement = timezone.now()
    commande.status = 'processing'
    commande.save()
    
    return True