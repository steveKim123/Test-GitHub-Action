import calendar
from collections import OrderedDict
from datetime import datetime
from dateutil.parser import parse as dtparser
from pytz import utc
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.contenttypes.models import ContentType

from .models import (
    EntityType, Tag, Resource, ResourceTag,
    Container, ContainerRelationship,Segment
)
from .fields import (
    EpochDateField, TagValueField, PivotResourcesField,
    PivotResourcesFieldDetailed, FilterDictionaryField,
    PrimaryKeyLookupField,
)

HistoricalContainer = Container.history.model
HistoricalResource = Resource.history.model

#from drf_haystack.serializers import HaystackSerializer
#from drf_haystack.viewsets import HaystackViewSet
#from search_indexes import ContainerIndex

class EntityTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EntityType
        fields = ('id', 'name',)


class SegmentSerializer(serializers.ModelSerializer):
    # type = serializers.SlugRelatedField(
    #     slug_field='name', queryset=EntityType.objects.all()
    # )

    # parent = serializers.SlugRelatedField(slug_field='guid', read_only=True)
    parent = serializers.CharField(source='parent_guid', read_only=True)

    class Meta:
        model = Segment
        fields = (
            'id', 'guid', 'type', 'namespace', 'status', 'origin', 'parent',
            'label', 'value', 'data', 'start_time_code', 'end_time_code',
            'created_date', 'updated_date', 'published_date', 'expiration_date'
        )

        read_only_fields = (
            'id', 'parent', 'created_date', 'updated_date',
        )


class BulkSegmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Segment
        fields = (
            'id', 'type', 'namespace', 'guid', 'status', 'origin',
            'data', 'label', 'value', 'start_time_code', 'end_time_code',
            'published_date', 'expiration_date'
        )

        read_only_fields = ('id',)

        extra_kwargs = {
            'guid': {'validators': [], 'required': False},
            'type': {'write_only': True},
            'namespace': {'write_only': True},
            'status': {'write_only': True},
            'origin': {'write_only': True},
            'data': {'write_only': True},
            'label': {'write_only': True},
            'value': {'write_only': True},
            'start_time_code': {'write_only': True},
            'end_time_code': {'write_only': True},
            'published_date': {'write_only': True},
            'expiration_date': {'write_only': True}
        }


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Tag
        fields = ('id', 'type', 'value', 'data', 'origin', 'label')

        extra_kwargs = {
            'value': {'validators': []},
        }

    def to_internal_value(self, data):
        # Allow specifying only the value (str)
        if isinstance(data, str):
            data = { 'value': data }

        return super(TagSerializer, self).to_internal_value(data)

class ResourceTagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ResourceTag
        fields = ('id', 'type', 'value', 'data', 'origin', 'label')

        extra_kwargs = {
            'value': {'validators': []},
        }

    def to_internal_value(self, data):
        # Allow specifying only the value (str)
        if isinstance(data, str):
            data = { 'value': data }

        return super(ResourceTagSerializer, self).to_internal_value(data)

class ResourceSerializer(serializers.ModelSerializer):
    type         = PrimaryKeyLookupField(queryset=EntityType.objects.all())

    tags         = ResourceTagSerializer(many=True, required=False)
    status       = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model  = Resource
        fields = (
            'id', 'type', 'data', 'uri', 'tags',
            'origin', 'status',
        )
        read_only_fields = ('id','created_date',)

    def _tag_queryset(self, tags):
        if not tags:
            return ResourceTag.objects.none()
        tag_values = []
        for tag in tags:
            if isinstance(tag, str):
                tag_values.append(tag)
            else:
                tag_values.append(tag['value'])
        return ResourceTag.objects.filter(value__in=tag_values)

    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        instance = Resource.objects.create(**validated_data)
        instance.tags.set(self._tag_queryset(tags))
        instance.save()     # to trigger reindex
        return instance 

    def update(self, instance, validated_data):

        if instance.origin != validated_data.get('origin', instance.origin):
            raise ValidationError({
                'Origin Violation Error'
            })

        tags = validated_data.pop('tags', None)
        instance.type = validated_data.get('type', instance.type)
        instance.data = validated_data.get('data', instance.data)
        instance.uri = validated_data.get('uri', instance.uri)
        instance.origin = validated_data.get('origin', instance.origin)
        instance.status = validated_data.get('status', instance.status)
        if tags is not None:
            instance.tags.set(self._tag_queryset(tags), clear=True)
        instance.save()
        return instance


class ResourceNestedSerializer(ResourceSerializer):
    type = EntityTypeSerializer()
    tags = ResourceTagSerializer(many=True, required=False)

    # class Meta(ResourceSerializer.Meta):
    #     depth = 2


class RelationshipSerializer(serializers.ModelSerializer):
    from_container  = serializers.PrimaryKeyRelatedField(queryset=ContainerRelationship.objects.all())
    to_container    = serializers.PrimaryKeyRelatedField(queryset=ContainerRelationship.objects.all())
    tags           = TagSerializer(many=True, required=False)
    created_date   = EpochDateField(required=True)

    class Meta:
        model  = ContainerRelationship
        fields = ('from_container','to_container','tags', 'order', 'created_date')
        read_only_fields = ('created_date',)


class ResourceFlatSerializer(ResourceNestedSerializer):
    type = serializers.CharField(source='type.name')
    tags = TagValueField(many=True)


class ContainerSerializer(serializers.ModelSerializer):
    type           = PrimaryKeyLookupField(queryset=EntityType.objects.all())
    origin         = serializers.CharField(allow_blank=False, required=True)
    tags           = TagSerializer(many=True, required=False)
    resources      = serializers.PrimaryKeyRelatedField(queryset=Resource.objects.all(), many=True, required=False)
    containers     = serializers.PrimaryKeyRelatedField(queryset=Container.enabled_objects.all(), many=True, required=False)
    status         = serializers.CharField(allow_blank=True, required=False)
    created_date   = EpochDateField(required=False)
    published_date = EpochDateField(required=False, allow_null=True)
    updated_date   = EpochDateField(required=False)
    reference_date  = EpochDateField(read_only=True, allow_null=True)
    expiration_date = EpochDateField(read_only=True, allow_null=True)

    class Meta:
        model  = Container
        fields = (
            'id', 'type', 'guid', 'data', 'tags', 'resources',
            'containers', 'origin', 'status', 'is_enabled',
            'created_date', 'published_date', 'updated_date',
            'reference_date', 'expiration_date',
        )
        read_only_fields = (
            'id', 'is_enabled', 'resources', 'containers',
            'created_date', 'updated_date',
            'reference_date', 'expiration_date',
        )

    def _tag_queryset(self, tags): 
        if not tags:
            return Tag.objects.none()
        tag_values = []
        for tag in tags:
            if isinstance(tag, str):
                tag_values.append(tag)
            else:
                tag_values.append(tag['value'])

        return Tag.objects.filter(value__in=tag_values)


    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        instance = Container.objects.create(**validated_data)
        instance.tags.set(self._tag_queryset(tags))
        instance.save()
        return instance 

    def update(self, instance, validated_data):

        if instance.origin != validated_data.get('origin', instance.origin):
            raise ValidationError({
                'Container Origin Constraint Violation Error'
            })

        tags = validated_data.pop('tags', None)
        instance.type = validated_data.get('type', instance.type)
        instance.guid = validated_data.get('guid', instance.guid)
        instance.data = validated_data.get('data', instance.data)
        instance.origin = validated_data.get('origin', instance.origin)
        instance.status = validated_data.get('status', instance.status)
        instance.published_date = validated_data.get(
            'published_date', instance.published_date)
        if tags is not None:
            instance.tags.set(self._tag_queryset(tags), clear=True)
        instance.save()
        return instance


class ContainerNestedSerializer(ContainerSerializer):
    type       = EntityTypeSerializer()
    tags       = TagSerializer(many=True, required=False)
    resources  = ResourceNestedSerializer(many=True, required=False)
    # containers = RecursiveField(many=True, max_depth=0)

    # class Meta(ContainerSerializer.Meta):
    #     depth = 2

class ContainerRelationshipNestedSerializer(ContainerNestedSerializer):
    relation_tags = TagSerializer(many=True, required=False)
    relation_order = serializers.IntegerField()

    class Meta:
        model = Container
        fields = ContainerNestedSerializer.Meta.fields + ('relation_tags', 'relation_order')
        read_only_fields = ContainerNestedSerializer.Meta.read_only_fields

class ContainerFlatSerializer(ContainerNestedSerializer):
    type      = serializers.CharField(source='type.name')
    resources = PivotResourcesField() 
    data = FilterDictionaryField()


class ContainerFlatSerializerwithTags(ContainerNestedSerializer):
    type      = serializers.CharField(source='type.name')
    resources = PivotResourcesFieldDetailed()
    data = FilterDictionaryField()

class ContainerMinimalSerializer(serializers.ModelSerializer):
    data = FilterDictionaryField()
    type = serializers.CharField(source='type.name')

    class Meta:
        model  = Container
        fields = ('id','guid','type', 'data',)

## Export tool serializers

class ResourceExportSerializer(serializers.ModelSerializer):
    type   = serializers.SlugRelatedField(
        slug_field='name', queryset=EntityType.objects.all()
    )
    uri    = serializers.CharField(allow_blank=False, required=True)
    data   = serializers.JSONField(allow_null=True, required=True)
    tags   = serializers.SlugRelatedField(
        slug_field='value', many=True,
        queryset=ResourceTag.objects.all(),
    )
    origin = serializers.CharField(allow_blank=False, required=True)
    status = serializers.CharField(allow_blank=False, required=True)

    class Meta:
        model = Resource
        fields = ('type', 'uri', 'data', 'tags', 'origin', 'status')

    def create(self, validated_data):
        tags = validated_data.pop('tags', None)

        instance = Resource.objects.create(**validated_data)

        if tags is not None:
            instance.tags.set(tags)

        return instance


class ParentExportSerializer(serializers.ModelSerializer):
    guid = serializers.SlugRelatedField(
        source='from_container',
        slug_field='guid',
        queryset=Container.objects.all()
    )
    tags = serializers.SlugRelatedField(
        slug_field='value',
        many=True,
        queryset=Tag.objects.all(),
        required=False
    )

    OPTIONAL_ATTRS = ('tags',)

    class Meta:
        model = ContainerRelationship
        fields = ('guid', 'tags')


class ChildExportSerializer(serializers.ModelSerializer):
    guid = serializers.SlugRelatedField(
        source='to_container',
        slug_field='guid',
        queryset=Container.objects.all()
    )
    tags = serializers.SlugRelatedField(
        slug_field='value',
        many=True,
        queryset=Tag.objects.all(),
        required=False
    )

    OPTIONAL_ATTRS = ('tags',)

    class Meta:
        model = ContainerRelationship
        fields = ('guid', 'tags')


class ContainerExportSerializer(serializers.ModelSerializer):
    type = serializers.SlugRelatedField(
        slug_field='name', queryset=EntityType.objects.all()
    )
    guid = serializers.CharField(allow_blank=False, required=True)
    data = serializers.JSONField(allow_null=True, required=True)
    tags = serializers.SlugRelatedField(
        slug_field='value', many=True,
        queryset=Tag.objects.all(),
    )
    origin = serializers.CharField(allow_blank=False, required=True)
    status = serializers.CharField(allow_blank=False, required=True)
    published_date = serializers.DateTimeField(
        allow_null=True, required=False
    )
    expiration_date = serializers.DateTimeField(
        allow_null=True, required=False
    )
    resources = ResourceExportSerializer(many=True, read_only=True)
    parent_containers = ParentExportSerializer(
        read_only=True, many=True, required=False
    )
    child_containers = ChildExportSerializer(
        read_only=True, many=True, required=False
    )

    OPTIONAL_ATTRS = ('child_containers', 'parent_containers',)

    class Meta:
        model = Container
        fields = (
            'type', 'guid', 'data', 'tags', 'origin', 'status',
            'published_date', 'expiration_date', 'resources',
            'child_containers', 'parent_containers',
        )
        read_only_fields = (
            'resources', 'child_containers', 'parent_containers',
        )

    def to_representation(self, value):
        # Specific optional attributes to be supplied by queryset
        for attr in self.OPTIONAL_ATTRS:
            if not hasattr(value, attr):
                setattr(value, attr, None)

        return super(ContainerExportSerializer, self).to_representation(value)

    def create(self, validated_data):
        resources = validated_data.pop('resources', None)
        tags = validated_data.pop('tags', None)

        # Set published date if creating and unspecified
        if (validated_data.get('status') == 'published' and
                not validated_data.get('published_date')):
            validated_data['published_date'] = datetime.now(utc)

        instance = Container.objects.create(**validated_data)

        if resources is not None:
            resource_list = self._set_resources(instance, resources)

        if tags is not None:
            instance.tags.set(tags)

        return instance 

    def update(self, instance, validated_data):
        # Ensure not clearing existing published date if unspecified
        if (validated_data.get('status') == 'published' and
                not validated_data.get('published_date')):
            validated_data.pop('published_date', None)

        # Let superclass handle most of it
        resources = validated_data.pop('resources', None)
        instance = super(ContainerExportSerializer, self).update(
            instance, validated_data
        )

        if resources is not None:
            resource_list = self._set_resources(instance, resources)

        return instance

    def _set_resources(self, container, resource_list):
        # This method can either update existing resources
        # or set new resources if one does not exist
        resources = []
        content_type = ContentType.objects.get_for_model(Container)
        old_resources = OrderedDict()
        to_delete = []

        # Check if a resource exists and if yes update it
        for res in container.resources.all():
            key = (res.type.name, res.uri,
                    frozenset(t.value for t in res.tags.all())
                )
            # Delete duplicates
            if key in old_resources:
                to_delete.append(res)
            else:
                old_resources[key] = res

        for res_dict in reversed(resource_list):
            key = (
                res_dict['type'], res_dict['uri'], frozenset(res_dict['tags'])
            )

            if key in old_resources:
                # Update old
                old_res = old_resources.pop(key)
                serializer = ResourceExportSerializer(
                    old_res, data=res_dict, partial=False
                )
                serializer.is_valid(raise_exception=True)
                res = serializer.save(
                    object_id=container.id, content_type=content_type)
                resources.append(res)
            else:
                # Create new
                serializer = ResourceExportSerializer(data=res_dict)
                serializer.is_valid(raise_exception=True)
                res = serializer.save(
                    object_id=container.id, content_type=content_type
                )
                resources.append(res)

        # Delete duplicates and any not in new list
        to_delete.extend(old_resources.values())
        for res in to_delete:
            res.delete()

        resources = list(reversed(resources))
        
        return resources

class ContainerSyncSerializer(ContainerExportSerializer):

    guid = serializers.CharField(required=False, read_only=True)
    
    class Meta:
        model = Container
        fields = (
            'guid',
            'type',
            'origin',
            'status',
            'data',
            'created_date', 'updated_date',
            'published_date', 'expiration_date',
            'tags', 'resources',
            # 'child_containers', 'parent_containers',
        )
        read_only_fields = (
            'created_date', 'updated_date',
            # 'child_containers', 'parent_containers',
        )


#class ContainerSearchSerializer(HaystackSerializer):

#    class Meta:
#        index_classes = [ContainerIndex]
#        fields = [
#            "id","guid","title", "description", "keywords","thumbnail","type"
#        ]


## History serializers

class HistoryListSerializer(serializers.Serializer):
    '''
    Standalone serializer class for history entries,
    not tied to any model class.
    '''

    history_id = serializers.IntegerField(read_only=True)
    history_date = serializers.DateTimeField(read_only=True)
    history_type = serializers.SerializerMethodField()
    # Related user
    # TODO: expose both username and email, and let client sort it out?
    history_user = serializers.SerializerMethodField()
    history_user_id = serializers.IntegerField(read_only=True)
    # Todo: override with empty string
    history_change_reason = serializers.SerializerMethodField()

    def get_history_type(self, obj):
        if obj.history_type == '+':
            return 'created'
        if obj.history_type == '~':
            return 'changed'
        if obj.history_type == '-':
            return 'deleted'
        return 'unknown'

    def get_history_user(self, obj):
        if not obj.history_user:
            return 'System'
        if obj.history_user.email:
            return obj.history_user.email
        return obj.history_user.username

    def get_history_change_reason(self, obj):
        return obj.history_change_reason or ''


class ContainerHistorySerializer(HistoryListSerializer,
                                 serializers.ModelSerializer):
    '''
    Container-specific history serializer.
    '''

    type = serializers.SlugRelatedField(slug_field='name', read_only=True)

    class Meta:
        model = HistoricalContainer
        fields = (
            'history_id', 'history_date', 'history_type',
            'history_user', 'history_user_id', 'history_change_reason',
            'id', 'type', 'guid', 'status', 'origin', 'data',
            'created_date', 'reference_date',
            'published_date', 'expiration_date',
        )
        read_only_fields = fields


class ResourceHistorySerializer(HistoryListSerializer,
                                serializers.ModelSerializer):
    '''
    Resource-specific history serializer.
    '''

    type = serializers.SlugRelatedField(slug_field='name', read_only=True)
    container_id = serializers.IntegerField(source='object_id', read_only=True)

    class Meta:
        model = HistoricalResource
        fields = (
            'history_id', 'history_date', 'history_type',
            'history_user', 'history_user_id', 'history_change_reason',
            'id', 'type', 'uri', 'status', 'origin', 'data', 'container_id',
            'created_date', 'published_date', 'expiration_date',
        )
        read_only_fields = fields


class HistoryModelChangeSerializer(serializers.Serializer):

    field = serializers.CharField(read_only=True)
    old = serializers.ReadOnlyField()
    new = serializers.ReadOnlyField()


class HistoryModelDeltaSerializer(serializers.Serializer):

    old_history_id = serializers.IntegerField(
        read_only=True, source='old_record.history_id'
    )
    old_history_date = serializers.DateTimeField(
        read_only=True, source='old_record.history_date'
    )
    new_history_id = serializers.IntegerField(
        read_only=True, source='new_record.history_id'
    )
    new_history_date = serializers.DateTimeField(
        read_only=True, source='new_record.history_date'
    )
    changes = HistoryModelChangeSerializer(many=True, read_only=True)


## Utilities

def epoch_millisecond_from_date(date):
    try:
        if isinstance(date, str):
            date = dtparser(date)
        if date.tzinfo is None:
            date = date.replace(tzinfo=utc)
        return calendar.timegm(date.utctimetuple()) * 1000
    except (AttributeError, TypeError, ValueError):
        return None
