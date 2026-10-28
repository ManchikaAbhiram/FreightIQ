from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.core.exceptions import ValidationError
from audit.models import AuditException, AuditEvent
from .freight_calculator import calculate_expected, money
@transaction.atomic
def validate_invoice(invoice, actor=None):
    findings=[]
    submitted_currency=invoice.currency
    if invoice.carrier_id != invoice.shipment.carrier_id: findings.append('Carrier does not match shipment assignment.')
    if invoice.supplier_id != invoice.shipment.supplier_id: findings.append('Supplier does not match shipment supplier.')
    if not invoice.supporting_reference and not invoice.supporting_document: findings.append('Supporting document reference is missing.')
    try:
        calc=calculate_expected(invoice.shipment)
        if invoice.billed_weight_kg is not None and money(invoice.billed_weight_kg)!=money(calc['billable_weight']): findings.append(f'Billed weight {money(invoice.billed_weight_kg)} kg does not match calculated billable weight {money(calc["billable_weight"])} kg.')
        invoice.expected_base=calc['base']; invoice.expected_fuel=calc['fuel']; invoice.expected_accessorial=calc['accessorial']; invoice.expected_total=calc['total']
        if calc.get('unsupported_accessorials'): findings.append('Unsupported accessorials on shipment: '+', '.join(calc['unsupported_accessorials']))
        if invoice.billed_accessorial>0 and not invoice.shipment.shipment_accessorials.exists(): findings.append('Billed accessorial charges have no matching documented shipment accessorial.')
        contract_currency=calc['rate_card'].currency
        if submitted_currency != contract_currency: findings.append(f'Invoice currency {submitted_currency} does not match contract currency {contract_currency}.')
    except ValidationError as exc:
        findings.append(str(exc)); invoice.expected_total=Decimal('0.00')
    line_total=money(invoice.billed_base+invoice.billed_fuel+invoice.billed_accessorial)
    if invoice.declared_total is not None and money(invoice.declared_total)!=line_total: findings.append(f'Declared invoice total {money(invoice.declared_total)} does not equal charge-line total {line_total}.')
    invoice.billed_total=line_total
    discrepancy=money(invoice.billed_total-invoice.expected_total)
    if not findings and discrepancy == 0:
        invoice.validation_status='VALID'; invoice.status='READY_FOR_PAYABLE'
    elif discrepancy > 0:
        invoice.validation_status='OVERCHARGE'; invoice.status='EXCEPTION'
        AuditException.objects.get_or_create(invoice=invoice,defaults={'code':f'FEX-{invoice.code}','issue_type':'Contractual charge discrepancy','original_discrepancy':discrepancy,'status':'NEW','is_synthetic':invoice.is_synthetic,'created_at':invoice.submitted_at+timedelta(minutes=1)})
    elif discrepancy < 0:
        invoice.validation_status='UNDERCHARGE'; invoice.status='REVIEW_REQUIRED'
        AuditException.objects.get_or_create(invoice=invoice,defaults={'code':f'FEX-{invoice.code}','issue_type':'Undercharge review','original_discrepancy':discrepancy,'status':'NEW','is_synthetic':invoice.is_synthetic,'created_at':invoice.submitted_at+timedelta(minutes=1)})
    else:
        invoice.validation_status='VALIDATION_FAILURE'; invoice.status='REVIEW_REQUIRED'
        AuditException.objects.get_or_create(invoice=invoice,defaults={'code':f'FEX-{invoice.code}','issue_type':'Non-financial validation failure','original_discrepancy':discrepancy,'status':'NEW','is_synthetic':invoice.is_synthetic,'created_at':invoice.submitted_at+timedelta(minutes=1)})
    invoice.validation_findings=findings
    invoice.save()
    AuditEvent.objects.create(actor=actor,entity_type='FreightInvoice',entity_id=invoice.code,action='Invoice validated',new_state=invoice.validation_status,details='; '.join(findings) or f'Billed ₹{invoice.billed_total}; expected ₹{invoice.expected_total}; discrepancy ₹{discrepancy}',amount=discrepancy,is_synthetic=invoice.is_synthetic,created_at=invoice.submitted_at+timedelta(minutes=2))
    return invoice
