from django.db.models.signals import post_delete
from django.db import transaction
from django.dispatch import receiver

from app.accounts.services import release_storage

from .models import Attachment


@receiver(post_delete, sender=Attachment)
def delete_attachment_file_and_release_quota(sender, instance, **kwargs):
    name = instance.file.name
    storage = instance.file.storage
    if name:
        transaction.on_commit(
            lambda: storage.delete(name) if storage.exists(name) else None
        )
    release_storage(instance.owner_id, instance.size)
