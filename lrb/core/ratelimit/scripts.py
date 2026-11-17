"""Lua scripts. Each runs atomically inside Redis, so concurrent requests on
different app servers can never interleave halfway through a decision.

Conventions used by every script
  * Time comes from Redis (TIME), never from an app server's clock.
  * Time is integer microseconds, tokens are integer milli-tokens (1 token = 1000).
    No floating-point drift, and every product stays below 2**53, which policies.py
    enforces at startup, so Lua doubles represent every value exactly.
  * Numbers written back to Redis go through string.format('%d'). Redis would
    otherwise print a 16-digit timestamp with %.14g and silently drop digits.
  * Rejected requests perform no writes (a flood of rejections costs only reads).
"""

_COMMON = """
local function idiv(a, b) return (a - (a % b)) / b end          -- exact floor(a/b)
local function cdiv(a, b) return idiv(a + b - 1, b) end         -- exact ceil(a/b)
local function now_us()
  local t = redis.call('TIME')
  return tonumber(t[1]) * 1000000 + tonumber(t[2])
end
"""

# KEYS[1..n]  one hash per bucket           fields: t (milli-tokens), ts (last refill, us)
# ARGV[1]=n  ARGV[2]=grace_ms  then per bucket: capacity_milli, refill_milli, period_us, cost_milli
# Returns {allowed, binding_index, (remaining_milli, retry_us, reset_us) * n}
# All-or-nothing: tokens are deducted from every bucket only if every bucket can pay.
TOKEN_BUCKET = _COMMON + """
local n        = tonumber(ARGV[1])
local grace_ms = tonumber(ARGV[2])
local now      = now_us()
local st, allowed, binding, worst = {}, 1, 0, 0

for i = 1, n do
  local o = 2 + (i - 1) * 4
  local cap, refill = tonumber(ARGV[o + 1]), tonumber(ARGV[o + 2])
  local period, cost = tonumber(ARGV[o + 3]), tonumber(ARGV[o + 4])
  local h = redis.call('HMGET', KEYS[i], 't', 'ts')
  local tokens, ts
  if (not h[1]) or (not h[2]) then
    tokens = cap; ts = now                       -- new or expired bucket starts full
  else
    tokens = tonumber(h[1]); ts = tonumber(h[2])
    if ts > now then ts = now end                -- clock moved backwards: no time passed
    if tokens >= cap then
      tokens = cap; ts = now                     -- full (also clamps after a policy was lowered)
    else
      local fill_us = cdiv((cap - tokens) * period, refill)
      local elapsed = now - ts
      if elapsed >= fill_us then
        tokens = cap; ts = now
      else
        local added = idiv(elapsed * refill, period)
        if added > 0 then
          tokens = tokens + added
          ts = ts + idiv(added * period, refill) -- keep the fractional remainder, lose nothing
        end
      end
    end
  end
  local retry = 0
  if tokens < cost then
    allowed = 0
    retry = cdiv((cost - tokens) * period, refill)
    if retry > worst then worst = retry; binding = i end
  end
  st[i] = {tokens, ts, cap, refill, period, cost, retry}
end

local out = {allowed, binding}
for i = 1, n do
  local s = st[i]
  local tokens = s[1]
  if allowed == 1 then
    tokens = tokens - s[6]
    local to_full = cdiv((s[3] - tokens) * s[5], s[4])
    redis.call('HSET', KEYS[i], 't', string.format('%d', tokens), 'ts', string.format('%d', s[2]))
    -- Expire once the bucket would be full again anyway: dropping it then changes nothing.
    redis.call('PEXPIRE', KEYS[i], cdiv(to_full, 1000) + grace_ms)
  end
  out[#out + 1] = tokens
  out[#out + 1] = s[7]
  out[#out + 1] = cdiv((s[3] - tokens) * s[5], s[4])
end
return out
"""

# KEYS[1..n] one sorted set per window (member = request id, score = time us)
# ARGV[1]=n ARGV[2]=request_id ARGV[3]=grace_ms then per window: limit, window_us
# Returns {allowed, binding_index, (remaining, retry_us, reset_us) * n}
SLIDING_WINDOW = _COMMON + """
local n, rid, grace_ms = tonumber(ARGV[1]), ARGV[2], tonumber(ARGV[3])
local now = now_us()
local counts, retries, allowed, binding, worst = {}, {}, 1, 0, 0

for i = 1, n do
  local o = 3 + (i - 1) * 2
  local limit, window = tonumber(ARGV[o + 1]), tonumber(ARGV[o + 2])
  redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', now - window)   -- idempotent pruning
  local c = redis.call('ZCARD', KEYS[i])
  counts[i] = c
  retries[i] = 0
  if c >= limit then
    allowed = 0
    local oldest = redis.call('ZRANGE', KEYS[i], 0, 0, 'WITHSCORES')
    retries[i] = tonumber(oldest[2]) + window - now
    if retries[i] < 1 then retries[i] = 1 end
    if retries[i] > worst then worst = retries[i]; binding = i end
  end
end

local out = {allowed, binding}
for i = 1, n do
  local o = 3 + (i - 1) * 2
  local limit, window = tonumber(ARGV[o + 1]), tonumber(ARGV[o + 2])
  local c = counts[i]
  if allowed == 1 then
    redis.call('ZADD', KEYS[i], string.format('%d', now), rid)
    redis.call('PEXPIRE', KEYS[i], cdiv(window, 1000) + grace_ms)
    c = c + 1
  end
  local reset = 0
  local oldest = redis.call('ZRANGE', KEYS[i], 0, 0, 'WITHSCORES')
  if oldest[2] then reset = tonumber(oldest[2]) + window - now end
  if reset < 0 then reset = 0 end
  out[#out + 1] = limit - c
  out[#out + 1] = retries[i]
  out[#out + 1] = reset
end
return out
"""

# KEYS[1] penalty hash (score, ts, until). Returns {blocked, retry_us}
PENALTY_CHECK = _COMMON + """
local now = now_us()
local u = tonumber(redis.call('HGET', KEYS[1], 'until') or '0')
if u > now then return {1, u - now} end
return {0, 0}
"""

# KEYS[1] penalty hash. ARGV[1]=decay_per_second (float) ARGV[2]=grace_ms ARGV[3..]=ladder seconds
# Score decays over time, +1 per violation. ladder[min(floor(score), #ladder)] picks the block.
# Returns {level, block_seconds}
PENALTY_VIOLATE = _COMMON + """
local now = now_us()
local decay, grace_ms = tonumber(ARGV[1]), tonumber(ARGV[2])
local h = redis.call('HMGET', KEYS[1], 'score', 'ts', 'until')
local score = tonumber(h[1] or '0') or 0
local ts = tonumber(h[2] or tostring(now)) or now
local until_us = tonumber(h[3] or '0') or 0
local elapsed_s = (now - ts) / 1000000
if elapsed_s > 0 then score = math.max(0, score - decay * elapsed_s) end
score = score + 1
-- +0.1: a violation that has decayed by less than 10% still counts as a whole one, so the
-- level does not depend on how many milliseconds a Redis round trip took.
local idx = math.min(math.floor(score + 0.1), #ARGV - 2)
if idx < 1 then idx = 1 end
local secs = tonumber(ARGV[2 + idx])
if secs > 0 then
  local candidate = now + secs * 1000000
  if candidate > until_us then until_us = candidate end   -- never shorten an active block
end
redis.call('HSET', KEYS[1], 'score', string.format('%.6f', score),
           'ts', string.format('%d', now), 'until', string.format('%d', until_us))
local decay_ms = 0
if decay > 0 then decay_ms = math.ceil(score / decay * 1000) end
local block_ms = math.max(0, math.ceil((until_us - now) / 1000))
redis.call('PEXPIRE', KEYS[1], math.max(decay_ms, block_ms) + grace_ms)
return {idx, secs}
"""

# KEYS[1] zset (member = lease token, score = lease expiry us)
# ARGV: max, lease_us, token, grace_ms. Returns {acquired, in_use}
SEM_ACQUIRE = _COMMON + """
local max, lease, token, grace_ms = tonumber(ARGV[1]), tonumber(ARGV[2]), ARGV[3], tonumber(ARGV[4])
local now = now_us()
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)        -- drop expired leases (crashed holders)
local c = redis.call('ZCARD', KEYS[1])
if c >= max then return {0, c} end
redis.call('ZADD', KEYS[1], string.format('%d', now + lease), token)
redis.call('PEXPIRE', KEYS[1], cdiv(lease, 1000) + grace_ms)
return {1, c + 1}
"""

# Releases only our own lease, so a late release can never free someone else's slot.
SEM_RELEASE = "return redis.call('ZREM', KEYS[1], ARGV[1])"
