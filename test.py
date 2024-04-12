from django.contrib import admin

from .models import (
    EntityType, Tag, Resource, ResourceTag,
    Container, ContainerRelationship, Segment,
)
from simple_history.admin import SimpleHistoryAdmin

@admin.register(EntityType)  
class EntityTypeAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'created_date',)


@admin.register(Segment)
class SegmentTypeAdmin(admin.ModelAdmin):
    list_display = ('id','guid', 'label','value', 'created_date',)

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('value', 'label', 'type', 'origin', 'created_date',)

@admin.register(Resource)
class ResourceAdmin(SimpleHistoryAdmin):
    list_display = (
        'id', 'type', 'origin', 'uri', 'status',
        'created_date', 'updated_date',
    )

@admin.register(Container)
class ContainerAdmin(SimpleHistoryAdmin):
    list_display = (
        'id', 'type', 'origin', 'guid', 'status', 
        'published_date', 'created_date', 'updated_date',
    )
    readonly_fields = ('hard_lock_id', 'soft_lock_id')

@admin.register(ContainerRelationship)
class ContainerRelationshipAdmin(admin.ModelAdmin):
    list_display = ('from_container', 'to_container', 'order', 'created_date')
    list_select_related = ('from_container__type', 'to_container__type',)
    raw_id_fields = ('from_container', 'to_container',)

@admin.register(ResourceTag)
class ResourceTagAdmin(admin.ModelAdmin):
    list_display = ('value', 'label', 'origin', 'created_date')

#@admin.register(Container, SimpleHistoryAdmin)
#@admin.register(Resource, SimpleHistoryAdmin)