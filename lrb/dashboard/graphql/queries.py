import strawberry
from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.dashboard.graphql.types import DashboardData


@strawberry.type
class DashboardQuery:
    @strawberry.field
    def dashboard(self, info:strawberry.Info) -> DashboardData:
        user = get_current_user_or_raise(info, message="Authentication required.")
        return DashboardData()