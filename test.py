from django.db import models, transaction
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist
from django.core.signals import request_finished

from django_elasticsearch_dsl.registries import registry
from django_elasticsearch_dsl.signals import BaseSignalProcessor

from .utilities import (
    es_update_on_commit, es_delete_on_commit, write_es_changes,
)


@receiver(request_finished)
def write_es_changes_after_request(sender=None, **kwargs):
    # print(f'Writing changes...')
    write_es_changes()


class ContainerSignalProcessor(BaseSignalProcessor):
    """Real-time signal processor.
    Allows for observing when saves/deletes fire and automatically updates the
    search engine appropriately.
    """
    EXCLUDE_RELATED_TYPES = {
        'platform',
        'policy',
    }

    def handle_save(self, sender, instance, **kwargs):
        """Handle save.
        Given an individual model instance, update the object in the index.
        Update the related objects either.
        """
        registry.update(instance)
        # For relations, skip reindex if in type exclusion list
        if sender._meta.model_name == 'containerrelationship':
           if instance.to_container.type.name not in self.EXCLUDE_RELATED_TYPES:
                registry.update_related(instance)
        else:
            registry.update_related(instance)

    def handle_pre_delete(self, sender, instance, **kwargs):
        # Update at end of transaction, so parent relations are updated
        deleter = lambda: registry.delete_related(instance)
        # For relations, skip reindex if in type exclusion list
        if sender._meta.model_name == 'containerrelationship':
           if instance.to_container.type.name not in self.EXCLUDE_RELATED_TYPES:
                transaction.on_commit(deleter)
        else:
            transaction.on_commit(deleter)

    def setup(self):
        # Listen to all model saves.
        models.signals.post_save.connect(self.handle_save)
        models.signals.post_delete.connect(self.handle_delete)

        # Use to manage related objects update
        models.signals.m2m_changed.connect(self.handle_m2m_changed)
        models.signals.pre_delete.connect(self.handle_pre_delete)

    def teardown(self):
        # Listen to all model saves.
        models.signals.post_save.disconnect(self.handle_save)
        models.signals.post_delete.disconnect(self.handle_delete)
        models.signals.m2m_changed.disconnect(self.handle_m2m_changed)
        models.signals.pre_delete.disconnect(self.handle_pre_delete)


class TransactionSignalProcessor(ContainerSignalProcessor):

    EXCLUDE_RELATED_TYPES = set()

    def handle_save(self, sender, instance, **kwargs):
        es_update_on_commit(instance)
        # For relations, skip reindex if in type exclusion list
        if (sender._meta.model_name == 'containerrelationship' and
                instance.to_container.type.name in self.EXCLUDE_RELATED_TYPES):
            return
        # Bit of a reimplementation of registry.update_related()
        # so that we can use the on-commit helpers instead
        for doc in registry._get_related_doc(instance):
            doc_instance = doc()
            try:
                related = doc_instance.get_instances_from_related(instance)
            except ObjectDoesNotExist:
                related = None

            if related:
                es_update_on_commit(related)

    def handle_delete(self, sender, instance, **kwargs):
        # NOTE: the stock handler sets `raise_on_error=False`, presumably
        # to prevent errors with ES disrupting canonical storage -- but
        # since we're deferring indexing anyways, we'd actually prefer
        # those errors to bubble up if and when they happen
        es_delete_on_commit(instance)

    def handle_pre_delete(self, sender, instance, **kwargs):
        # For relations, skip reindex if in type exclusion list
        if (sender._meta.model_name == 'containerrelationship' and
                instance.to_container.type.name in self.EXCLUDE_RELATED_TYPES):
            return
        # Bit of a reimplementation of registry.delete_related()
        # so that we can use the on-commit helpers instead
        for doc in registry._get_related_doc(instance):
            doc_instance = doc(related_instance_to_ignore=instance)
            try:
                related = doc_instance.get_instances_from_related(instance)
            except ObjectDoesNotExist:
                related = None

            if related:
                es_update_on_commit(related)
