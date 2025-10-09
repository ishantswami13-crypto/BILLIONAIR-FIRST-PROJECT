# Schema & Migration Plan

This document tracks database changes required across the roadmap phases. Use it to seed Alembic migrations in the order listed.

## Global considerations
- Adopt Alembic for versioned migrations (`flask db init/migrate/upgrade`).
- Ensure every migration is reversible and includes data backfills where needed.
- For SQLite development, gate complex DDL behind feature flags or run SQL fallbacks.

## Phase 1 (Professional Trust Layer)
| Change | Table | Notes |
| --- | --- | --- |
| Add `invoice_number` | `sales` | Sequence per shop, unique constraint. |
| Add `signature_blob` & `watermark_path` | `sales` or `shop_profile` | Store branding artefacts. |
| Add `logo_path`, `primary_colour`, `secondary_colour`, `invoice_prefix` | `shop_profile` | Branding options. |
| Add `before_state`, `after_state`, `resource_type`, `resource_id`, `ip_address`, `user_agent` | `audit_log` | Enables diff view. |
| Add `locked_until` flag | `settings` | Marks end-of-day lock. |

## Phase 2 (Money & Insight Layer)
| Change | Table | Notes |
| --- | --- | --- |
| Add `category_id` | `expenses` | FK into new `expense_categories`. |
| Create `expense_categories` | new | `id`, `name`, `color`, `rules_json`. |
| Create `sales_heatmap` materialized view | optional | Aggregated sales by hour (or generate on the fly). |
| Create `customer_metrics` | optional | Precomputed LTV, visit count, last purchase. |
| Create `recommendations` | optional | Cache heuristic results per shop. |

## Phase 3 (Automation & Assistant Layer)
| Change | Table | Notes |
| --- | --- | --- |
| Create `assistant_sessions` | new | `id`, `user_id`, `created_at`. |
| Create `assistant_messages` | new | `id`, `session_id`, `role`, `content`, `created_at`. |
| Add `last_reminder_at`, `reminder_count`, `reminder_opt_out` | `credits` | WhatsApp reminders. |
| Create `reminder_log` | new | Trace each reminder send attempt. |

## Phase 4 (Smart Connect Layer)
| Change | Table | Notes |
| --- | --- | --- |
| Add `role` enum & `last_login_at` | `users` | Replace current string role with enum. |
| Create `user_invites` | new | Manage pending invitations. |
| Create `api_webhooks` | new | `id`, `event`, `target_url`, `secret`, `status`. |
| Create `webhook_events` | new | Delivery log with retry metadata. |

## Phase 5 (Premium UI/UX & Business Model)
| Change | Table | Notes |
| --- | --- | --- |
| Create `plans` | new | `id`, `slug`, `name`, `price`, `currency`. |
| Create `plan_features` | new | Map plan -> feature flag. |
| Add `plan_id`, `trial_ends_at` | `users` or `shop_profile` | Associates shop with plan. |
| Add `feature_flags` JSON | optional | Overrides per tenant. |

## Phase 6 (Social Proof & Authority)
- No schema changes expected (pure UI/marketing).

## Phase 7 (Audit & Security Enhancements)
| Change | Table | Notes |
| --- | --- | --- |
| Add `export_token`, `status`, `expires_at` | `audit_log` or new `exports` table | Track exports requested. |
| Extend `backups` metadata | e.g. `backups` table | `id`, `path`, `checksum`, `created_at`, `retained`. |
| Add `locked_by`/`locked_at` | `sales` | Captures post-report locks or override data. |

## Migration rollout checklist
1. Write migration script.
2. Run locally (`flask db upgrade`).
3. Regenerate models if using typed stubs (optional).
4. Test CRUD flows covering new columns.
5. Deploy to staging, verify, then production.
