from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Count,Sum
from django.db import connection
from pathlib import Path
import csv
from audit.models import *
from audit.services.freight_calculator import money, calculate_expected
class Command(BaseCommand):
    help='Validate freight master data, invoice arithmetic, exceptions and financial balances.'
    def handle(self,*args,**opts):
        errors=[]; counts={}
        models=[Carrier,Supplier,Customer,Product,Lane,ServiceType,RateCard,WeightTier,Accessorial,RateCardAccessorial,Shipment,ShipmentAccessorial,ShipmentLeg,WeightMeasurement,DeliveryRecord,FreightInvoice,InvoiceLine,AuditException,AnalystReview,ManagerDecision,CarrierResponse,CreditNote,CreditApplication,InvoiceAdjustment,ReconciliationRecord,AuditEvent]
        for model in models: counts[model.__name__]=model.objects.count()
        for inv in FreightInvoice.objects.select_related('shipment','carrier','supplier'):
            if inv.invoice_date < inv.shipment.shipment_date: errors.append(f'{inv.code}: invoice date precedes shipment date')
            if inv.shipment.actual_delivery and inv.shipment.actual_delivery < inv.shipment.shipment_date: errors.append(f'{inv.shipment.code}: delivery date precedes shipment date')
            if money(inv.billed_base+inv.billed_fuel+inv.billed_accessorial)!=money(inv.billed_total): errors.append(f'{inv.code}: billed total arithmetic mismatch')
            if inv.shipment.carrier_id!=inv.carrier_id: errors.append(f'{inv.code}: carrier/shipment mismatch')
            if inv.shipment.supplier_id!=inv.supplier_id: errors.append(f'{inv.code}: supplier/shipment mismatch')
            if inv.validation_status in ['OVERCHARGE','UNDERCHARGE'] and not inv.exceptions.exists(): errors.append(f'{inv.code}: discrepancy without exception')
            try:
                calc=calculate_expected(inv.shipment)
                expected=money(calc['total'])
                if money(inv.expected_total)!=expected: errors.append(f'{inv.code}: expected total differs from freight calculator')
            except Exception as exc: errors.append(f'{inv.code}: expected charge cannot be recalculated: {exc}')
            lines=list(inv.lines.all())
            if lines:
                if money(sum((line.billed_amount for line in lines),Decimal('0'))) != money(inv.billed_total): errors.append(f'{inv.code}: invoice line billed amounts do not reconcile')
                if money(sum((line.expected_amount for line in lines),Decimal('0'))) != money(inv.expected_total): errors.append(f'{inv.code}: invoice line expected amounts do not reconcile')
            for exc in inv.exceptions.all():
                if exc.original_discrepancy!=money(inv.billed_total-inv.expected_total): errors.append(f'{exc.code}: exception discrepancy differs from invoice')
        for note in CreditNote.objects.all():
            applied=note.applied_amount
            if applied>note.issued_amount: errors.append(f'{note.code}: applied credit exceeds issued amount')
            if note.verification_status!='VERIFIED' and applied>0: errors.append(f'{note.code}: unverified credit has applications')
        for app in CreditApplication.objects.all():
            if not InvoiceAdjustment.objects.filter(application=app).exists(): errors.append(f'Application {app.pk}: missing invoice adjustment')
            if app.amount<=0: errors.append(f'Application {app.pk}: non-positive amount')
            adjustment=InvoiceAdjustment.objects.filter(application=app).first()
            if adjustment and (adjustment.amount != app.amount or adjustment.invoice_id != app.invoice_id): errors.append(f'Application {app.pk}: invoice adjustment mismatch')
        for exc in AuditException.objects.all():
            if exc.status=='RECONCILED' and not exc.reconciliations.filter(status='RECONCILED').exists(): errors.append(f'{exc.code}: reconciled without matching record')
        for rec in ReconciliationRecord.objects.all():
            if rec.remaining_amount < 0: errors.append(f'Reconciliation {rec.pk}: negative remaining balance')
            if rec.applied_amount > rec.verified_amount: errors.append(f'Reconciliation {rec.pk}: applied exceeds verified amount')
            if rec.issued_amount > rec.approved_amount and rec.status=='RECONCILED': errors.append(f'Reconciliation {rec.pk}: reconciled with excessive issuance')
        gt_path=Path('data/ground_truth/ground_truth.csv')
        if gt_path.exists():
            with gt_path.open(newline='',encoding='utf-8-sig') as f:
                for gt in csv.DictReader(f):
                    inv=FreightInvoice.objects.filter(code=gt.get('record_identifier')).first()
                    if not inv: continue
                    if gt.get('expected_validation_outcome') and inv.validation_status!=gt['expected_validation_outcome']: errors.append(f'Ground truth mismatch for {inv.code}: expected {gt["expected_validation_outcome"]}, found {inv.validation_status}')
                    if gt.get('expected_financial_result') and money(inv.discrepancy)!=money(gt['expected_financial_result']): errors.append(f'Ground truth financial mismatch for {inv.code}')
        unique=AuditException.objects.filter(original_discrepancy__gt=0).values_list('original_discrepancy',flat=True).distinct().count()
        vals=list(AuditException.objects.filter(original_discrepancy__gt=0).values_list('original_discrepancy',flat=True))
        stats={'positive_exception_count':len(vals),'unique_positive_discrepancies':unique,'minimum':str(min(vals)) if vals else None,'maximum':str(max(vals)) if vals else None,'average':str(sum(vals,Decimal('0'))/len(vals)) if vals else None}
        import json
        state_counts={'invoice_status':{r['status']:r['n'] for r in FreightInvoice.objects.values('status').annotate(n=Count('id'))},'validation_status':{r['validation_status']:r['n'] for r in FreightInvoice.objects.values('validation_status').annotate(n=Count('id'))},'exception_status':{r['status']:r['n'] for r in AuditException.objects.values('status').annotate(n=Count('id'))},'credit_note_verification':{r['verification_status']:r['n'] for r in CreditNote.objects.values('verification_status').annotate(n=Count('id'))}}
        report={'passed':not errors,'counts':counts,'workflow_state_counts':state_counts,'financial_totals':{'billed':str(FreightInvoice.objects.aggregate(v=Sum('billed_total'))['v'] or Decimal('0')),'expected':str(FreightInvoice.objects.aggregate(v=Sum('expected_total'))['v'] or Decimal('0')),'positive_discrepancy':str(sum((x for x in AuditException.objects.filter(original_discrepancy__gt=0).values_list('original_discrepancy',flat=True)),Decimal('0')))},'error_count':len(errors),'errors':errors[:200],'discrepancy_statistics':stats,'synthetic_records':sum((m.objects.filter(is_synthetic=True).aggregate(n=Count('id'))['n'] or 0) for m in models if any(f.name=='is_synthetic' for f in m._meta.fields))}
        path=Path('data/exports/validation_report.json'); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        self.stdout.write(json.dumps(report,indent=2))
        if errors: raise SystemExit(1)
