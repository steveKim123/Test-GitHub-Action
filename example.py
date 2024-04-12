import json
import pytz
import uuid

from django.db.models import Prefetch
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import (
    GenericForeignKey, GenericRelation
)
from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models
from simple_history.models import HistoricalRecords

from dateutil.parser import parse as dt_parse
from datetime import datetime
utc = pytz.utc


# TODO: add slug fields
class EntityType(models.Model):
    name         = models.CharField(max_length=256)
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_date',)
        get_latest_by = 'created_date'

    def __str__(self):
        return self.name

class Tag(models.Model):
    type           = models.CharField(max_length=256, blank=True, default='')
    
    origin         = models.CharField(max_length=256, default='system')
    label          = models.CharField(max_length=256, blank=True, default='')
    value          = models.CharField(max_length=256, unique=True)
    data           = JSONField(null=True, blank=True)
    
    created_date   = models.DateTimeField(auto_now_add=True)
    updated_date   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_date',)
        get_latest_by = 'created_date'

    def __str__(self):
        return self.value

class ResourceTag(models.Model):
    id             = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    type           = models.CharField(max_length=256, blank=True, default='')
    
    origin         = models.CharField(max_length=256, default='system')
    label          = models.CharField(max_length=256, blank=True, default='')
    value          = models.CharField(max_length=256, unique=True)
    data           = JSONField(null=True, blank=True)
    
    created_date   = models.DateTimeField(auto_now_add=True)
    updated_date   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_date',)
        get_latest_by = 'created_date'

    def __str__(self):
        return self.value

class Resource(models.Model):
    type         = models.ForeignKey(EntityType, null=True, on_delete=models.PROTECT)
    uri          = models.CharField(max_length=2048, db_index=True)
    status       = models.CharField(max_length=256, blank=True, default='')
    origin       = models.CharField(max_length=256, default='system')
    tags         = models.ManyToManyField(ResourceTag, blank=True, symmetrical=False, related_name="resources")
    data         = JSONField(null=True, blank=True)
    
    created_date = models.DateTimeField(auto_now_add=True)
    published_date = models.DateTimeField(blank=True,null=True)
    updated_date   = models.DateTimeField(auto_now=True)
    expiration_date  = models.DateTimeField(blank=True,null=True)
    # generic relation
    content_type   = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id      = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    history        = HistoricalRecords(excluded_fields=['updated_date'])

    class Meta:
        ordering = ('-created_date',)
        get_latest_by = 'created_date'

    def __str__(self):
        return '{} {}'.format(self.type.name, self.uri)

class EnabledManager(models.Manager):
    def get_queryset(self):
        queryset = super(EnabledManager, self).get_queryset()
        return queryset.filter(is_enabled=True).order_by('to_container__order', '-created_date')

class Segment(models.Model):
    parent = models.ForeignKey(
        'Container', on_delete=models.CASCADE,
        related_name='segments', related_query_name='segment',
    )

    guid             = models.CharField(max_length=256, unique=True, default=uuid.uuid4)
    type             = models.CharField(max_length=256, db_index=True)
    namespace        = models.CharField(max_length=256, default='', blank=True, db_index=True)
    status           = models.CharField(max_length=256, blank=True, default='new', db_index=True)
    origin           = models.CharField(max_length=256, default='system', db_index=True)

    label            = models.CharField(max_length=256) 
    value            = models.CharField(max_length=256) 
    data             = JSONField(null=True, blank=True, default=dict)

    # TODO: index (together)?
    start_time_code  = models.DecimalField(decimal_places=5, max_digits=15)
    end_time_code    = models.DecimalField(decimal_places=5, max_digits=15)

    created_date     = models.DateTimeField(auto_now_add=True)
    updated_date     = models.DateTimeField(auto_now=True)
    published_date   = models.DateTimeField(blank=True,null=True)
    expiration_date  = models.DateTimeField(blank=True,null=True)

    class Meta:
        indexes = [
            models.Index(fields=['parent', 'type', 'start_time_code']),
            models.Index(fields=['parent', 'type', 'end_time_code']),
        ]

    @property
    def type_indexing(self):
        return self.type

    @property
    def parent_guid(self):
        if not hasattr(self, '_parent_guid'):
            if self.parent:
                self._parent_guid = self.parent.guid
            else:
                self._parent_guid = None
        return self._parent_guid


class Container(models.Model):
    type           = models.ForeignKey(EntityType, null=True, on_delete=models.PROTECT)
    guid           = models.CharField(max_length=256, unique=True)
    status         = models.CharField(max_length=256, blank=True, default='new', db_index=True)
    origin         = models.CharField(max_length=256, default='system', db_index=True)
    data           = JSONField(null=True, blank=True)
    tags           = models.ManyToManyField(Tag, blank=True)
    resources      = GenericRelation(Resource)
    containers     = models.ManyToManyField('self', through='ContainerRelationship', symmetrical=False, related_name="parents")
    is_enabled     = models.BooleanField(default=True)
    
    created_date    = models.DateTimeField(auto_now_add=True, db_index=True)
    published_date  = models.DateTimeField(blank=True, null=True, db_index=True)
    updated_date    = models.DateTimeField(auto_now=True, db_index=True)
    expiration_date = models.DateTimeField(blank=True, null=True, db_index=True)
    reference_date  = models.DateTimeField(blank=True, null=True, db_index=True)
    
    history        = HistoricalRecords(excluded_fields=['updated_date'])

    hard_lock_id   = models.CharField(max_length=256, null=True, default=None)
    soft_lock_id   = models.CharField(max_length=256, null=True, default=None)

    objects         = models.Manager()
    enabled_objects = EnabledManager()

    class Meta:
        ordering = ('id',)
        get_latest_by = 'created_date'

    def __str__(self):
        return '{} {} {}'.format(self.type.name, self.id, self.guid)

    @classmethod
    def with_children(cls, queryset, depth=0, restrict_resources=False,
                      resource_status=None):
        nested_queryset = cls.enabled_objects.all()

        if depth > 0:
            nested_queryset = cls.with_children(
                nested_queryset, depth=depth - 1
            )
        elif depth == -1:
            nested_queryset = cls.enabled_objects.none()

        resource_queryset = (
            Resource.objects
                .select_related('type')
                .prefetch_related('tags')
        )
        if restrict_resources:
            resource_queryset = resource_queryset.filter(status='published')
        if resource_status is not None:
            if resource_status:
                resource_queryset = resource_queryset.filter(
                    status__in=resource_status
                )
            else:
                resource_queryset = resource_queryset.none()

        return (
            queryset
                .select_related('type')
                .prefetch_related(
                    Prefetch(
                        'containers',
                        queryset=nested_queryset,
                    ),
                    Prefetch(
                        'resources',
                        queryset=resource_queryset
                    ),
                    'tags',
                )
        )

    @property
    def resource_indexing(self):
        return [{'type':resource['type__name'],
                 'uri':resource['uri'],
                 'status':resource['status'],
                 'tag':resource['tags__value']}
                for resource in self.resources.values('id','status','uri','type__name','tags__value')
                if resource['status'] == 'published']

    @property
    def type_indexing(self):
        print(self.guid)
        return self.type.name

    @property
    def data_indexing(self):
        return json.dumps(self.data)

    @property
    def parent_indexing(self):
        return [
            {
                'id': parent['from_container_id'],
                'guid': parent['from_container__guid'],
                'type': parent['from_container__type__name'],
                'order': parent['order'],
                'relation_tag_value': parent['tags__value'],
                'relation_tag_label': parent['tags__label'],
                'relation_tag_type': parent['tags__type'],
            }
            for parent in self.to_container.values(
                'from_container_id',
                'from_container__guid',
                'from_container__type__name',
                'order',
                'tags__value',
                'tags__label',
                'tags__type')
        ]

    @property
    def tag_indexing(self):
        return list(self.tags.values('type', 'value', 'label'))

    def get_reference_date(self):
        ref_date = None
        # First try metadata fields
        for f in ['pub_date', 'local_air_date', 'available_date']:
            val = self.data.get(f)
            # Exclude epoch dates
            if val and not val.startswith('1970-01-01'):
                ref_date = dt_parse(val)
                if ref_date.tzinfo is None:
                    ref_date = ref_date.replace(tzinfo=utc)
                break
        # Fall back to top-level fields
        if not ref_date:
            ref_date = self.published_date
        if not ref_date:
            ref_date = self.created_date

        return ref_date

    def get_expiration_date(self):
        exp_date = None
        val = self.data.get('expiration_date')
        # Exclude epoch dates
        if val and not val.startswith('1970-01-01'):
            exp_date = dt_parse(val)
            if exp_date.tzinfo is None:
                exp_date = exp_date.replace(tzinfo=utc)

        return exp_date


class ContainerRelationship(models.Model):
    from_container = models.ForeignKey('Container', related_name='from_container', on_delete=models.CASCADE)
    to_container   = models.ForeignKey('Container', related_name='to_container', on_delete=models.CASCADE)
    tags           = models.ManyToManyField(Tag, blank=True)
    order          = models.IntegerField(default=0)
    created_date   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_container', 'to_container', 'order')
        ordering = ('from_container', 'order', '-created_date')
        get_latest_by = 'created_date'

    def __str__(self):
        return '{} -> {}'.format(
            self.from_container.guid, self.to_container.guid
        )


HistoricalContainer = Container.history.model
HistoricalResource = Resource.history.model
# Forgive me, this is such a hack, but I don't see any
# other better way to do this until/unless the fix
# is merged upstream
# See https://github.com/jazzband/django-simple-history/pull/601
for field in HistoricalContainer._meta.fields:
    if field.attname == 'history_date':
        field.db_index = True
for field in HistoricalResource._meta.fields:
    if field.attname == 'history_date':
        field.db_index = True
del field
