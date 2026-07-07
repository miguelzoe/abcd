from django.core.management.base import BaseCommand

from apps.reservations.services import dispatch_due_reservation_reminders


class Command(BaseCommand):
    help = 'Envoie les rappels Cartronic arrivés à échéance.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        sent = dispatch_due_reservation_reminders(limit=options['limit'])
        self.stdout.write(self.style.SUCCESS(f'{sent} rappel(s) envoyé(s).'))
