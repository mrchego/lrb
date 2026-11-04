import strawberry
from lrb.company.graphql.platform import PlatformMutation, PlatformQuery

schema = strawberry.Schema(query=PlatformQuery, mutation=PlatformMutation)
