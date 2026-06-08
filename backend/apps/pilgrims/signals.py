import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MedicalDocument
from .pipeline import run_pipeline

logger = logging.getLogger(__name__)


@receiver(post_save, sender=MedicalDocument)
def trigger_pipeline_on_new_document(sender, instance, created, **kwargs):
    """Automatically run the extraction pipeline when a new MedicalDocument is saved.

    Skips updates (e.g. admin status edits) so the pipeline runs exactly once
    per document — at upload time.
    """
    if not created:
        return

    try:
        run_pipeline(instance)
    except Exception:
        logger.exception(
            "Pipeline failed for document %s (pilgrim %s)",
            instance.pk,
            instance.pilgrim_id,
        )
