# Data Governance Policy (M12)

## Purpose

This document defines the data governance policies for FOOTBALL OS. It ensures
data quality, security, privacy, and compliance across the platform.

## Data Classification

| Classification | Description | Examples | Access Control |
|----------------|-------------|----------|----------------|
| Public | Intended for public consumption | Published tactical guides, community posts | Read: all authenticated users |
| Internal | Internal operational data | System metrics, logs, aggregated analytics | Read: authenticated users with appropriate roles |
| Confidential | Sensitive user/business data | User profiles, payment info, private messages | Read: owner + admins only |
| Restricted | Highly sensitive data | Authentication credentials, API keys, encryption keys | Read: system services only |

## Data Retention

| Data Category | Retention Period | Disposal Method |
|---------------|------------------|-----------------|
| User account data | Duration of account + 90 days | Secure deletion |
| Authentication logs | 13 months | Automated purge |
| API request logs | 90 days | Automated purge |
| Video assets (demo) | 30 days | Automated purge |
| Video assets (user) | Duration of account + 90 days | Secure deletion |
| Training/scouting data | Duration of career + 1 year | Anonymization then deletion |
| Financial/payment records | 7 years (legal requirement) | Secure archival |
| Model call records | 2 years | Aggregation then deletion |
| Audit trails | 3 years | Automated purge |

## Data Access

- **Principle of least privilege**: Users and services access only data required for their function
- **Role-based access control (RBAC)**: Access granted via roles (player, coach, manager, admin)
- **Ownership-based access**: Users access their own data; admins access tenant data
- **Audit logging**: All data access by admins is logged with reason

## Data Quality

- **Validation at entry**: All inputs validated at API boundary (Pydantic models)
- **Constraints at rest**: Database constraints enforce referential integrity
- **Reconciliation**: Periodic jobs verify data consistency (alembic check, seed verification)
- **Monitoring**: Metrics track data quality indicators (null rates, constraint violations)

## Privacy

- **Data minimization**: Collect only data necessary for stated purpose
- **Purpose limitation**: Data used only for declared purpose
- **User rights**: Export, rectification, erasure via `/auth/account` endpoints
- **Data portability**: JSON export via `GET /auth/account`
- **Right to erasure**: `DELETE /auth/account` with password confirmation

## Security

- **Encryption at rest**: PostgreSQL Transparent Data Encryption (TDE) in production
- **Encryption in transit**: TLS 1.3 for all connections
- **Secrets management**: API keys in environment variables, rotated quarterly
- **Password hashing**: scrypt with N=16384, r=8, p=1
- **Token security**: JWT with short TTL, refresh tokens with rotation and reuse detection

## Backup & Recovery

See `BACKUP_RECOVERY.md` for backup procedures and RTO/RPO targets.

## Compliance

- **GDPR**: Applies to EU users; DPA available on request
- **Data processing agreements**: Required for subprocessors
- **Breach notification**: 72-hour notification to supervisory authority and affected users

## Roles & Responsibilities

| Role | Responsibilities |
|------|------------------|
| Data Controller | Overall accountability; DPO liaison |
| Data Protection Officer | Monitor compliance; handle DSARs; breach reporting |
| Engineering Lead | Implement technical controls; code review for data handling |
| Security Lead | Threat modeling; incident response; vulnerability management |

## Change Management

- Schema changes via alembic migrations (reviewed, tested, staged)
- Data migrations tested on staging before production
- Rollback plan required for destructive changes
- Post-deployment verification of data integrity

## Incident Response

1. Detect: Monitoring alerts, user reports
2. Contain: Isolate affected systems; revoke compromised credentials
3. Assess: Determine scope, impact, root cause
4. Notify: DPO, users, regulators per GDPR timelines
5. Remediate: Patch, rotate credentials, restore from backup
6. Review: Post-incident review; update controls

## Review Cycle

This policy reviewed quarterly by DPO and Engineering Lead.
Last reviewed: 2026-10-09
Next review: 2027-01-09