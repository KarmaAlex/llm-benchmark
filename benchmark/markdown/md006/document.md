# Runbook: Payment Service High Latency

Use this runbook when the payment-service p99 latency alert fires.

## 1. Check current latency

Query the dashboard to confirm the alert is not a false positive:

```promql
histogram_quantile(0.99, sum(rate(payment_service_request_duration_seconds_bucket[5m])) by (le))
```

## 2. Check downstream dependency health

Check whether the card-processor dependency is degraded:

```bash
curl -s https://status.internal.example.com/api/services/card-processor | jq .status
```

## 3. Restart the affected pods if needed

If the dependency is healthy but latency is still high, roll the deployment:

```
kubectl rollout restart deployment/payment-service -n payments
```

## 4. Escalate

If the issue persists after 15 minutes, page the on-call payments engineer.
