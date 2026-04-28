from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class MyBookingPagination(PageNumberPagination):
    page_size              = 1
    page_size_query_param  = 'page_size'
    max_page_size          = 50


class PitchSearchPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50