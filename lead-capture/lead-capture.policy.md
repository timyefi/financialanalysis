# 联系方式政策

## Goal

Collect contact details with the least possible friction while keeping delivery reliable.

## Rules

- Ask for name, institution, role, email, phone, and card image at the first meaningful core action.
- Cache locally before sending.
- Send to email, persistent storage, and archive link in parallel.
- Retry automatically on network or sink failure.
- Keep the implementation serverless and lightweight.
- Keep the desktop queue as the source of truth for V1 visibility.

## Data Flow

1. User submits lead form.
2. Client stores payload locally.
3. Client sends to multiple sinks in parallel.
4. Client records delivery receipts.
5. Client retries unfinished sinks.
