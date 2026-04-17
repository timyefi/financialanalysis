# 联系方式流程

This flow keeps V1 contact collection lightweight and reliable.

## Rules

- Collect fields only at the first meaningful core action.
- Cache submissions locally before sending.
- Send the same payload to multiple sinks in parallel.
- Retry automatically until the payload is confirmed or marked failed.
- Never require a heavy custom server just to persist records.

## Sinks

1. Email notification
2. Persistent store
3. Archive or signed link

## Suggested Record Fields

- name
- institution
- role
- email
- phone
- card_image
- consent_version
- device_id
- client_version
- submitted_at
- delivery_status
- sink_receipts
