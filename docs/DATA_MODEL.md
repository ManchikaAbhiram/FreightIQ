# FreightIQ Data Model

## Master data

- **Carrier** — carrier identity, contact and active status.
- **Supplier** — invoice originator identity.
- **Customer** — delivery recipient identity and city.
- **Product** — SKU, descriptive name, category and fictional brand.
- **Lane** — origin, destination and approximate distance.
- **ServiceType** — named service catalog entry.
- **RateCard** — carrier/lane/service contract with validity dates, currency, minimum charge, fallback rate, fuel percentage and dimensional divisor.
- **WeightTier** — optional per-rate-card weight bands, rate per kg and minimum charge.
- **Accessorial** — named accessorial reference charge.
- **RateCardAccessorial** — rate-specific eligibility and fixed/percentage pricing rule.
- **ShipmentAccessorial** — documented accessorial event attached to a shipment.

## Operational records

- **Shipment** references carrier, supplier, optional customer, product, lane and optional rate card. It stores dates, service, quantity, actual weight, dimensions and delivery status.
- **ShipmentLeg** stores a sequenced carrier leg and departure/arrival information.
- **WeightMeasurement** stores measured weight, actor/reference and timestamp.
- **DeliveryRecord** stores delivery status, proof reference, notes and timestamp.
- **FreightInvoice** references a shipment, supplier, carrier and submitting user; stores billed component totals, declared total, expected components, validation findings, status and evidence.
- **InvoiceLine** stores line-level billed/expected charge detail.

## Workflow and financial records

- **AuditException** links a discrepant invoice to a lifecycle state and original discrepancy.
- **AnalystReview** stores immutable findings, root cause, recommendation, amount, evidence and review cycle.
- **ManagerDecision** stores each approval, rejection or return and mandatory comments where applicable.
- **CarrierResponse** stores each acceptance, dispute or counteroffer, explanation and proposed amount.
- **CreditNote** stores actual received note amount, currency, date, reference and verification state.
- **CreditApplication** stores each application and explicit reversal information.
- **InvoiceAdjustment** is the persistent accounting adjustment linked one-to-one to an application.
- **ReconciliationRecord** snapshots approved, agreed, issued, verified, applied and remaining amounts with difference and status.
- **AuditEvent** records actor, entity, action, previous/new state, details, amount, cycle and timestamp.
- **UserProfile** stores requested and approved roles, organization, registration status, carrier mapping and review metadata.

Synthetic data entities include an `is_synthetic` flag so a demo reset can target generated records only.
