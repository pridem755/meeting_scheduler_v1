class OrganizationScopedQuerysetMixin:
    """
    Mixin for ViewSets whose list results should be filterable by an
    `organization` query param, e.g. GET /api/v1/meetings/?organization=<uuid>
    """
    organization_lookup_field = "organization"

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_id = self.request.query_params.get("organization")
        if organization_id:
            queryset = queryset.filter(**{self.organization_lookup_field: organization_id})
        return queryset
