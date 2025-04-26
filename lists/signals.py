from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import ListItem
from companies.tasks import trigger_financial_import_task

@receiver(post_save, sender=ListItem)
def trigger_financial_import(sender, instance, created, **kwargs):
    if created:
        company_id = instance.company_id
        transaction.on_commit(lambda: trigger_financial_import_task.delay(company_id))
