import logging
import os
from functools import reduce

import jmespath

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, F, Prefetch, Max, Min
from django.db.models.expressions import RawSQL
from django.db import transaction

from .models import Container, ContainerRelationship, Tag
from .utilities import parse_date_utc, construct_timedelta, reindex_relations
from templater.views import create_realtime_auth_header, query_realtime_server


class BaseDynamicQuery(object):
    ''''''

    def __init__(self, query):
        self.query = query

    def get_containers(self, variables={}):
        if not hasattr(self, '_containers'):
            self._containers = self.evaluate(variables)

        return self._containers

    def evaluate(self, variables={}, extract_values=None):
        raise NotImplemented

    def set_children_by_query(self, parent_id, start_order,
                              tag_value='dynamic'):
        '''
        Add/update/remove dynamic children of `parent_id`.
        '''
        with transaction.atomic():
            child_relations = ContainerRelationship.objects.filter(id=parent_id)
