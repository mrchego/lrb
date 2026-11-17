import strawberry
from lrb.company.graphql.platform import PlatformMutation, PlatformQuery
from lrb.core.ratelimit.graphql import RateLimitExtension

schema = strawberry.Schema(query=PlatformQuery, mutation=PlatformMutation, extensions=[RateLimitExtension])
