# FreightIQ Workflow and Authorization

1. **Registration** — applicant selects one of six public roles; responsibilities are displayed as read-only system content. Profile starts Pending. The system administrator approves or rejects with a reason for rejection.
2. **Shipment preparation** — Planner records carrier, supplier, cargo, lane, weights, dimensions, service and delivery information.
3. **Invoice submission** — Supplier submits invoice components and supporting evidence. The server recalculates billed line total and expected contracted freight.
4. **Validation** — valid invoices move to payable-ready. Positive discrepancies create one linked exception. Undercharges are flagged for review and are not treated as credits owed.
5. **Analyst review** — Analyst records findings, root cause, recommendation, amount and evidence. Each cycle is a new `AnalystReview`.
6. **Manager decision** — Manager approves, rejects with reason, or returns with comments. Each action creates `ManagerDecision`. Returned cases increment the cycle and return to the analyst.
7. **Carrier response** — only the mapped carrier can accept, dispute, or counteroffer. A changed amount requires a fresh carrier response after internal review.
8. **Credit-note receipt** — Finance records the actual received note and document reference only after carrier acceptance. The issued amount is not assumed equal to the approved amount.
9. **Verification** — Finance compares actual amount and currency against manager approval and carrier agreement. Mismatches are retained and are not eligible for normal application.
10. **Application** — verified credits may be partially applied within the available balance. Applications and invoice adjustments are separate persistent records; the transaction uses a database lock and transaction.
11. **Reconciliation** — compare approved, agreed, issued, verified, applied, remaining and difference. A note is not treated as reconciled merely because it was approved.
12. **Audit** — important transitions create AuditEvent rows; case views display review, decision, response, credit and reconciliation history.

## Role boundaries

- Planner: operational shipment records; no financial approval.
- Supplier: own organization invoices and validation information.
- Carrier: mapped carrier cases only; carrier response only at its stage.
- Logistics Analyst: investigate and recommend; no official approval or credit issuance.
- Operations Manager: approve/reject/return; no credit-note verification or application.
- Finance: actual credit-note verification, application, reversal/reconciliation; cannot invent approval or carrier acceptance.
- System Administrator: access governance and application-wide review; created using `createsuperuser`, never public registration.
