# ADR-001 — Monorepo with Next.js + FastAPI + PostgreSQL, minimal infrastructure

- Status: Accepted (2026-02) · Relates to: PRINCIPLE 1, spec §43–44
- **Context**: The product spans 30 modules and multiple AI surfaces. The temptation is to pre-build microservices.
- **Problem**: Choose an architecture that is shippable by one autonomous agent loop yet does not block the eventual scale-out.
- **Options**: (a) Next.js full-stack only; (b) Next.js + FastAPI monolith + Postgres/pgvector; (c) microservices incl. Java Spring Boot from day one; (d) serverless + managed vector DB.
- **Decision**: (b). `apps/web` owns UI/BFF/auth-experience/streaming; `apps/api` owns AI, agents, RAG, providers, jobs, analytics; PostgreSQL + pgvector is the single source of truth. (a) rejected: Python AI ecosystem, RAG and agent runtime do not belong in the request path of the UI framework. (c) rejected: no measured bottleneck; Java is deferred to Core Domain/Community/Billing scale (spec §44). (d) rejected: pgvector keeps relational and vector state in one transactional store.
- **Consequences**: One deploy pair, one schema, one migration history. Redis/worker/search/event-bus remain *additive* swaps behind service interfaces. Cold-start cost: two runtimes to install locally.
