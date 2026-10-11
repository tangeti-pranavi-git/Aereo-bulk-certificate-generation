from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(connection_created)
def configure_sqlite(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('PRAGMA synchronous=NORMAL;')
            cursor.execute('PRAGMA busy_timeout=20000;')


class CertificatesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'certificates'

    def ready(self):
        pass
