# Provider Registry Policy

## Default Rules

- Users only choose a provider and paste a key in the main flow.
- Base URL and model presets are prefilled from the registry.
- Advanced override stays hidden unless explicitly opened.
- Windows clients use the native desktop execution path; no extra terminal environment is a customer requirement.

## Registry Guarantees

- Every preset must have a locked base URL.
- Every coding-plan preset must include a fallback model candidate list.
- Every preset must have an official documentation source link.
- Any endpoint drift should fail tests before release.

## Supported Vendors

- Z.AI
- MiniMax
- ByteDance / Volcano Ark
- Alibaba Cloud Bailian
- Tencent LKEAP
