from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class UserSearchPagination(PageNumberPagination):
    # Default page size — client can override with ?page_size=
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'

    def get_paginated_response(self, data):
        return Response({
            'pagination': {
                'count':       self.page.paginator.count,
                'next':        self.get_next_link(),
                'previous':    self.get_previous_link(),
            },
            'results': data
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'pagination': {
                    'type': 'object',
                    'properties': {
                        'count':        {'type': 'integer'},
                        'total_pages':  {'type': 'integer'},
                        'current_page': {'type': 'integer'},
                        'next':         {'type': 'string', 'nullable': True},
                        'previous':     {'type': 'string', 'nullable': True},
                    }
                },
                'results': schema,
            }
        }