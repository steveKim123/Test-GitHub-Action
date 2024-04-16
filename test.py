class BaseDynamicQuery(object):
    def set_children_by_query(self, parent_id, start_order,
                              tag_value='dynamic'):
        with transaction.atomic():
            child_relations = ContainerRelationship.objects.filter(id=parent_id)

