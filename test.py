# import logging
# import os
# from functools import reduce

# import jmespath

# from django.core.exceptions import ObjectDoesNotExist
# from django.db.models import Q, F, Prefetch, Max, Min
# from django.db.models.expressions import RawSQL
# from django.db import transaction

# from .models import Container, ContainerRelationship, Tag
# from .utilities import parse_date_utc, construct_timedelta, reindex_relations
# from templater.views import create_realtime_auth_header, query_realtime_server



# Example triggering E203:
my_list = [1, 2, 3, 4]
slice = my_list[1 : 4]

# class BaseDynamicQuery(object):
#     ''''''

#     def __init__(self, query):
#         self.query = query

#     def get_containers(self, variables={}):
#         if not hasattr(self, '_containers'):
#             self._containers = self.evaluate(variables)

#         return self._containers

#     def evaluate(self, variables={}, extract_values=None):
#         raise NotImplemented

#     def set_children_by_query(self, parent_id, start_order,
#                               tag_value='dynamic'):
#         '''
#         Add/update/remove dynamic children of `parent_id`.
#         '''
#         with transaction.atomic():
#             child_relations = ContainerRelationship.objects.filter(
#                 from_container_id=parent_id
#             )

#             # Get new container list, find new max order
#             children_by_id = {
#                 child.id: child for child in self.get_containers()
#             }

#             # Get exclusions, remove from new list
#             if children_by_id:
#                 to_exclude = list(
#                     child_relations
#                         .filter(to_container_id__in=children_by_id.keys())
#                         .exclude(tags__value=tag_value)
#                 )
#                 for relation in to_exclude:
#                     del children_by_id[relation.to_container_id]

#             # Get old container list, get max order, delete relations
#             to_replace = list(
#                 child_relations
#                     .filter(tags__value=tag_value)
#                     .select_related('to_container') # Speed up reindexing
#             )
#             max_dyn_order = None
#             for relation in to_replace:
#                 max_dyn_order = max(relation.order, max_dyn_order or 0)
#                 relation.delete()

#             # Get static containers in new dynamic range, push outside
#             new_relations = []
#             if children_by_id:
#                 to_update = (
#                     child_relations
#                         .filter(order__gte=start_order)
#                         .exclude(tags__value=tag_value)
#                 )
#                 update_min = to_update.aggregate(Min('order'))['order__min']
#                 end_order = start_order + len(children_by_id)
#                 # In theory could optimize moving children from inside new
#                 # dynamic range, but that's probably not worth it
#                 # Instead, just push everything out the same amount
#                 if update_min is not None and update_min < end_order:
#                     update_diff = end_order - update_min
#                     to_update.update(order=F('order') + update_diff)
#                     reindex_relations(parent_id, update_min + update_diff)

#                 # Add new relations for new container list
#                 relation_tag = Tag.objects.get(value=tag_value)
#                 for i, child in enumerate(children_by_id.values()):
#                     order = start_order + i
#                     # Create new relation and tag it
#                     relation = ContainerRelationship.objects.create(
#                         from_container_id=parent_id,
#                         to_container_id=child.id,
#                         order=order,
#                     )
#                     relation.tags.add(relation_tag)
#                     new_relations.append(relation)

#             return new_relations