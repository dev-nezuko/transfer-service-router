"""Pagination defaults shared by every list endpoint."""

from django.conf import settings
from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Page-number pagination with a client-controlled, capped page size.

    Clients may ask for a larger page with ``?page_size=``, but never more than
    ``API_MAX_PAGE_SIZE`` rows: an uncapped parameter would let a single request
    turn a paginated endpoint back into an unbounded table scan.
    """

    page_size_query_param = "page_size"

    @property
    def max_page_size(self):
        return getattr(settings, "API_MAX_PAGE_SIZE", 100)
