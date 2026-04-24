# Protobuf Proxy Safety Fixtures

Fixtures in `fixtures.yaml` describe language-neutral command/admin inputs and
the structured status, issue code, field path, and retry hint expected from
generated clients.

Rules:

- `fixture_id` is stable and unique.
- `kind` is `command` or `admin`.
- `mode` is `compatibility`, `warning-only`, or `strict`.
- `expected_status` must match a proto enum name.
- `expected_issue_codes`, `expected_field_paths`, and `expected_retry_hints`
  must stay ordered by emitted issue.
- Command fixtures should include `client_language` only when the payload is
  intentionally language-specific; otherwise runners apply them to every client.
