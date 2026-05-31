from datetime import datetime, timezone

from app.models import IncidentMemory, SplunkAlert


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


SEED_INCIDENTS: list[IncidentMemory] = [
    IncidentMemory(
        orgId="acme-retail",
        incidentId="inc-redis-econnreset-2026-05-21",
        service="checkout-api",
        severity="sev1",
        symptoms=[
            "Redis ECONNRESET spikes during checkout writes",
            "p95 latency over 4800ms",
            "burst of 5xx errors after connection reuse",
        ],
        rootCause="A stale Redis connection pool kept reusing half-closed sockets after failover.",
        resolution="Rotated the Redis connection pool, forced reconnect jitter, and replayed failed checkout writes.",
        actionTaken="rotate_connection_pool",
        resolved=True,
        createdAt=utc("2026-05-21T18:34:00Z"),
    ),
    IncidentMemory(
        orgId="acme-retail",
        incidentId="inc-queue-backlog-2026-05-18",
        service="fulfillment-worker",
        severity="sev2",
        symptoms=[
            "Queue backlog above 14000 jobs",
            "worker heartbeats delayed",
            "ship confirmation events lagging behind checkout",
        ],
        rootCause="A slow downstream carrier API exhausted worker concurrency and blocked retry lanes.",
        resolution="Raised worker concurrency, split carrier retries into a low-priority queue, and drained oldest jobs first.",
        actionTaken="split_retry_queue",
        resolved=True,
        createdAt=utc("2026-05-18T11:08:00Z"),
    ),
    IncidentMemory(
        orgId="acme-retail",
        incidentId="inc-auth-token-expiry-2026-05-14",
        service="auth-gateway",
        severity="sev2",
        symptoms=[
            "401 rate climbed after token refresh",
            "mobile sessions failed silent renewal",
            "JWT verifier rejected fresh tokens",
        ],
        rootCause="The auth gateway cached the old signing key past the provider rotation window.",
        resolution="Flushed JWKS cache, shortened key TTL, and replayed failed refresh attempts.",
        actionTaken="flush_jwks_cache",
        resolved=True,
        createdAt=utc("2026-05-14T07:22:00Z"),
    ),
    IncidentMemory(
        orgId="acme-retail",
        incidentId="inc-db-pool-exhaustion-2026-05-10",
        service="orders-db",
        severity="sev1",
        symptoms=[
            "database pool waiters above 80",
            "order writes timing out",
            "API latency rose during nightly reconciliation",
        ],
        rootCause="Nightly reconciliation opened long transactions and starved the write pool.",
        resolution="Killed long-running reconciliation, reduced transaction batch size, and raised pool headroom.",
        actionTaken="shrink_reconciliation_batches",
        resolved=True,
        createdAt=utc("2026-05-10T02:48:00Z"),
    ),
    IncidentMemory(
        orgId="acme-retail",
        incidentId="inc-payment-webhook-2026-05-06",
        service="payments-webhook",
        severity="sev2",
        symptoms=[
            "payment provider retries doubled",
            "webhook signature verification failed",
            "checkout confirmations delayed",
        ],
        rootCause="The provider rotated webhook signing secrets before our secret cache refreshed.",
        resolution="Reloaded webhook secret versions, replayed failed provider events, and tightened secret cache TTL.",
        actionTaken="reload_webhook_secrets",
        resolved=True,
        createdAt=utc("2026-05-06T15:12:00Z"),
    ),
    IncidentMemory(
        orgId="acme-retail",
        incidentId="inc-inventory-cache-2026-05-02",
        service="inventory-api",
        severity="sev3",
        symptoms=[
            "inventory reads returned stale counts",
            "cache hit rate dropped below 42%",
            "oversell warnings increased",
        ],
        rootCause="A cache namespace migration left old and new keys active for the same SKUs.",
        resolution="Purged the old namespace, warmed hot SKU keys, and pinned cache writes to the new namespace.",
        actionTaken="purge_legacy_cache_namespace",
        resolved=True,
        createdAt=utc("2026-05-02T09:41:00Z"),
    ),
    IncidentMemory(
        orgId="acme-retail",
        incidentId="inc-search-timeout-2026-04-29",
        service="product-search",
        severity="sev2",
        symptoms=[
            "search timeout rate above 18%",
            "facet requests stalled",
            "CPU saturation on two search nodes",
        ],
        rootCause="A broad synonym expansion created expensive facet scans for short queries.",
        resolution="Disabled the synonym rule, rebalanced hot shards, and rebuilt the affected facet cache.",
        actionTaken="disable_synonym_rule",
        resolved=True,
        createdAt=utc("2026-04-29T13:05:00Z"),
    ),
    IncidentMemory(
        orgId="acme-retail",
        incidentId="inc-email-provider-2026-04-25",
        service="notification-worker",
        severity="sev3",
        symptoms=[
            "password reset emails delayed",
            "provider throttling warnings",
            "retry queue growing slowly",
        ],
        rootCause="The email provider rate limit changed and our retry policy kept bursting.",
        resolution="Reduced retry burst size, enabled provider backoff headers, and drained the retry queue.",
        actionTaken="respect_provider_backoff",
        resolved=True,
        createdAt=utc("2026-04-25T20:13:00Z"),
    ),
    IncidentMemory(
        orgId="globex-payments",
        incidentId="inc-redis-econnreset-globex-2026-05-23",
        service="settlement-api",
        severity="sev1",
        symptoms=[
            "Redis ECONNRESET surfaced in settlement ledger writes",
            "idempotency checks timed out",
            "ledger API returned intermittent 503s",
        ],
        rootCause="A proxy idle timeout was shorter than the Redis client keepalive interval.",
        resolution="Aligned Redis keepalive with proxy timeout and rotated settlement writer connections.",
        actionTaken="align_keepalive_timeout",
        resolved=True,
        createdAt=utc("2026-05-23T16:02:00Z"),
    ),
    IncidentMemory(
        orgId="globex-payments",
        incidentId="inc-card-webhook-globex-2026-05-17",
        service="card-webhooks",
        severity="sev2",
        symptoms=[
            "card authorization webhooks arrived twice",
            "dedupe store latency rose",
            "merchant callbacks delayed",
        ],
        rootCause="A dedupe table migration missed the merchant partition key.",
        resolution="Restored the partition key, replayed delayed callbacks, and compacted duplicate records.",
        actionTaken="restore_dedupe_partition",
        resolved=True,
        createdAt=utc("2026-05-17T10:19:00Z"),
    ),
    IncidentMemory(
        orgId="globex-payments",
        incidentId="inc-auth-clock-skew-globex-2026-05-11",
        service="issuer-auth",
        severity="sev2",
        symptoms=[
            "token validation failed for issuer callbacks",
            "clock skew warnings increased",
            "fresh signatures rejected",
        ],
        rootCause="One auth node drifted 77 seconds after NTP stopped syncing.",
        resolution="Removed the drifting node, restored NTP sync, and widened temporary clock skew tolerance.",
        actionTaken="restore_ntp_sync",
        resolved=True,
        createdAt=utc("2026-05-11T08:47:00Z"),
    ),
]


DEFAULT_ALERT = SplunkAlert(
    orgId="acme-retail",
    alertId="splunk-alert-redis-econnreset-777",
    service="checkout-api",
    severity="sev1",
    title="Checkout Redis ECONNRESET burst after failover",
    message=(
        "Splunk saved search detected Redis ECONNRESET errors from checkout-api. "
        "p95 latency is 5120ms, 5xx errors jumped, and failed checkout writes are retrying "
        "after the service reused stale Redis sockets during connection pool failover."
    ),
    errorCount=327,
    p95LatencyMs=5120,
)

