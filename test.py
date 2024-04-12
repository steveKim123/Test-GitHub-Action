from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

import uuid

from .models import (
    EntityType, Tag, Resource, ResourceTag,
    Container, ContainerRelationship, Segment, Schema
)
import time       
import calendar   

hihi  