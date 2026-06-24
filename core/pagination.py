from rest_framework.pagination import PageNumberPagination


class StandardResultsPagination(PageNumberPagination):
    """Default pagination for every list endpoint in the project."""
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
