from rest_framework.pagination import PageNumberPagination

class ChallengeTeamsPagination(PageNumberPagination):
    page_size             = 2
    page_size_query_param = 'page_size'
    max_page_size         = 50


class PlayerChallengesPagination(PageNumberPagination):
    page_size             = 2
    page_size_query_param = 'page_size'
    max_page_size         = 50

class TeamChallengesPagination(PageNumberPagination):
    page_size             = 2
    page_size_query_param = 'page_size'
    max_page_size         = 50