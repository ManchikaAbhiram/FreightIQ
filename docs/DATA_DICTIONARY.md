# FreightIQ Data Dictionary

All primary keys are Django-generated integer IDs. Business identifiers are unique strings and are not intended to change after creation. Monetary values use `DecimalField` with two decimal places; synthetic amounts use INR unless the rate card says otherwise. Dates are local business dates; timestamps are timezone-aware in `Asia/Kolkata`.

| Entity | Key fields | Required relationships / rules |
|---|---|---|
| UserProfile | full_name, requested_role, approved_role, organization_name, status, rejection_reason | One-to-one with Django User. Status is Pending, Approved or Rejected. Approved role is assigned only by administrator review. |
| Carrier | code, name, contact_email, active | Unique code and name. Carrier accounts require an approved mapping to a Carrier record. |
| Supplier | code, name | Unique code and name. Supplier invoice visibility is organization-scoped. |
| Customer | name, city | Optional shipment recipient. |
| Product | sku, name, category, brand | SKU unique; names describe fictional cargo. |
| Lane | origin, destination, distance_km | Origin/destination pair unique. Distance is approximate km. |
| ServiceType | code, name, description | Named service catalog; rate cards and shipments currently retain service codes as text for simple CSV interoperability. |
| RateCard | code, carrier, lane, service_type, effective_from/to, currency, minimum_charge, rate_per_kg, fuel_percent, dim_divisor | Validity must include shipment date. Currency is ISO-style three-letter code. Divisor defaults to 5000. |
| WeightTier | rate_card, name, min/max_weight_kg, rate_per_kg, minimum_charge | Optional tier band. Open-ended maximum is allowed for the highest tier. |
| RateCardAccessorial | rate_card, accessorial, charge_method, amount, eligible | Fixed-per-unit or percentage-of-base charge eligibility. |
| Shipment | code, carrier, supplier, product, lane, rate_card, shipment_date, weights, dimensions, delivery_status | Code unique. Weight in kg; dimensions in cm; quantity uses quantity_unit. Rate card must match carrier/lane/service and date. |
| ShipmentAccessorial | shipment, accessorial, quantity, evidence_reference, notes | A shipment must explicitly record the scenario before the calculator includes a contracted accessorial. |
| ShipmentLeg | shipment, sequence, carrier, origin/destination, departure/arrival | Sequence identifies the leg order within a shipment. |
| WeightMeasurement | shipment, measured_weight_kg, measured_by, measured_at, evidence_reference | Weight in kg. Historical measurements are additive. |
| DeliveryRecord | shipment, status, recorded_at, proof_reference, notes | Evidence references should point to a document or operational record. |
| FreightInvoice | code, invoice_number, supplier, carrier, shipment, invoice_date, currency, billed_weight_kg, billed components, declared_total, expected components, validation_status, status | Code and invoice number unique. Billed total is recalculated from charge components. Billed weight is compared with the contract calculation when supplied. A declared total is compared with component arithmetic when provided. |
| InvoiceLine | invoice, code, description, charge_type, billed_amount, expected_amount, evidence_reference | Code unique. One invoice may have multiple charge lines. |
| AuditException | code, invoice, issue_type, severity, original_discrepancy, status, current_cycle | Code unique; discrepancy is billed minus expected. Repeated validation must not duplicate the exception. |
| AnalystReview | exception, actor, cycle, findings, root_cause, recommendation, recommended_amount, evidence_reference | Each submission creates a new row; analysts cannot make manager decisions. |
| ManagerDecision | exception, actor, cycle, decision, approved_amount, comments | Rejection and return require comments; each decision is retained. |
| CarrierResponse | exception, actor, response, proposed_amount, explanation | Dispute/counteroffer require explanation; each response is retained. |
| CreditNote | code, external_identifier, exception, invoice, carrier, issued_amount, currency, issue_date, document_reference, verification_status | Represents an actual received note, not merely an approval. Normal application requires VERIFIED status. |
| CreditApplication | credit_note, invoice, actor, amount, reference, reversed_at/reversal_reason | Positive amount; total active applications cannot exceed note balance. Reversals are explicit. |
| InvoiceAdjustment | application, invoice, amount | One-to-one with CreditApplication. |
| ReconciliationRecord | exception, approved/agreed/issued/verified/applied/remaining amounts, difference, status | Snapshot values are calculated from persisted workflow and finance records. |
| AuditEvent | actor, entity_type/id, action, previous/new state, details, amount, cycle, created_at | Append-only by application convention; supports the chronological case timeline. |

## Lifecycle values

- Registration: `PENDING`, `APPROVED`, `REJECTED`.
- Invoice validation: `PENDING`, `VALID`, `OVERCHARGE`, `UNDERCHARGE`, `VALIDATION_FAILURE`.
- Invoice processing: `SUBMITTED`, `READY_FOR_PAYABLE`, `EXCEPTION`, `REVIEW_REQUIRED`.
- Exception: `NEW`, `MANAGER_REVIEW`, `MANAGER_REVERIFY`, `RETURNED_TO_ANALYST`, `CARRIER_RESPONSE`, `CARRIER_ACCEPTED`, `CARRIER_DISPUTED`, `CARRIER_COUNTEROFFER`, `FINANCE_RECONCILIATION`, `RECONCILED`, `REJECTED`.
- Credit verification: `PENDING`, `VERIFIED`, `MISMATCH`.

## Calculation conventions

Dimensional kg = length_cm × width_cm × height_cm × quantity ÷ divisor. Billable kg is the greater of actual and dimensional kg. Base freight uses the selected weight-tier rate and minimum charge when present, otherwise the rate-card fallback. Fuel surcharge is base × fuel percent. Amounts are rounded half-up to two decimals. Discrepancy = billed total − expected total.
