Three files describe application configuration: a set of base defaults, and
two environment-specific override files (staging and production). Each
override file only lists the keys it changes; any key not listed keeps the
base default value.

Compute the **effective production configuration**: start from the base
defaults and apply only the production overrides. The staging overrides
file is not relevant to production and must be ignored entirely.

Return **only** a single flat JSON object containing all five keys from the
base defaults file, with their effective values, using the same JSON types
as written in the source documents (string, integer, or boolean).

Example shape (not the real values):

```json
{
    "log_level": "warn",
    "max_connections": 42,
    "cache_ttl_seconds": 60,
    "feature_flag_new_checkout": true,
    "request_timeout_ms": 1000
}
```
