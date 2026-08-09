---
artifact: adr
version: "1.0"
created: 2026-08-08
status: accepted
---

# ADR-005: Azure demonstration scope — code-only, never provisioned

## Status

Accepted — supersedes the live-provisioning plan for Azure described in ADR-001.

**Date:** 2026-08-08
**Deciders:** Victor Pinheiro

## Context

ADR-001 originally planned a one-time live demonstration of the Azure reference architecture (ADLS Gen2 + Synapse Serverless SQL + Microsoft Purview): provision resources, run the pipeline against them, capture evidence, then tear down immediately (`az group delete`) to bound cost exposure to a single short window.

Research into current Microsoft Purview pricing found that Purview is not reliably free even for a brief proof-of-concept scan — a documented case exists of a user incurring charges from a single small-scale PoC scan, inside what they believed was free-tier usage. ADLS Gen2 and Synapse Serverless SQL remain low-risk (storage and query costs for this project's data volume are fractions of a cent), but "low-risk" is not "zero-risk," and the project's standing constraint (established from ADR-001 onward) is exactly zero financial exposure, not minimized exposure.

## Decision

No Azure resource is provisioned live, for any duration, at any point in this project. The Azure demonstration consists entirely of **Infrastructure as Code**: complete, syntactically valid Bicep templates for the reference architecture (storage, Synapse workspace with serverless SQL pool, Purview account), validated locally via `az bicep build` — which compiles Bicep to ARM JSON and surfaces syntax errors without requiring an Azure login or subscription.

This replaces the "stand up once, capture evidence, tear down" plan from ADR-001 with a "write once, validate offline, never deploy" approach.

## Consequences

### Positive

- Financial exposure is exactly zero, with no dependency on cost estimates, free-tier assumptions, or careful timing of teardown — the risk this ADR removes entirely, rather than minimizes.
- The Bicep code itself remains a genuine, reviewable artifact of cloud competency — a technical reviewer can read the templates and assess design decisions without needing to trust a screenshot.
- Consistent with the project's established pattern (SEADE, the 2023 Gazette population correction): when a small residual risk or cost isn't worth the effort or exposure to close, the limitation is documented, not forced.

### Negative

- No live execution evidence exists — a reviewer cannot see the pipeline actually writing to ADLS or a Synapse query actually returning results. This is weaker proof than a working live demo, and is not compensated for; it's accepted as the trade-off for zero cost.
- The Bicep templates are unvalidated against a real Azure deployment (`az bicep build` catches syntax errors, not deployment-time issues like resource naming conflicts, quota limits, or region availability). This is a known, accepted limitation of code-only validation.

## Alternatives Considered

### Live demonstration excluding Purview only (ADLS + Synapse live, Purview code-only)

Considered, since ADLS and Synapse Serverless costs are genuinely negligible for this project's data volume. Rejected because the project's owner explicitly does not want to carry any financial risk, however small — the decision is about risk tolerance, not expected cost.

### Live demonstration on a free-trial Azure subscription with a hard spending limit

Considered. Rejected because Azure account creation requires a payment method on file, which itself was a source of concern established early in this project (ADR-001) — introducing a card into the equation, even with safeguards, reopens exactly the exposure the project has consistently avoided.

## References

- ADR-001 — original infrastructure decision and zero-cost constraint.
- `infra/` — Bicep templates (storage, Synapse, Purview).
