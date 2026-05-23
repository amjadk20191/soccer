from rest_framework.permissions import BasePermission


# 1 for player
# 2 for owner
# 3 for us
# 4 for owner staff

class IsPlayerPermission(BasePermission):
    def has_permission(self, request, view):
        # Ensure token exists
        if not request.auth:
            return False

        role = request.auth.get("role")

        if role == 1:
            return True

        return False
    


class IsClubStaffOrOwnerPermission(BasePermission):
    def has_permission(self, request, view):
        # Ensure token exists
        if not request.auth:
            return False

        role = request.auth.get("role")

        if role in (2, 4):
            return True

        return False
    


class IsClubOwnerPermission(BasePermission):
    def has_permission(self, request, view):
        # Ensure token exists
        if not request.auth:
            return False

        role = request.auth.get("role")

        if role == 2:
            return True

        return False
    


