import csv,json
from pathlib import Path
from django.core.management.base import BaseCommand
from audit.models import *
class Command(BaseCommand):
    help='Export database-backed FreightIQ master and transaction records to CSV/JSON.'
    def add_arguments(self,p): p.add_argument('--directory',default='data/exports')
    def handle(self,*args,**o):
        root=Path(o['directory']); root.mkdir(parents=True,exist_ok=True)
        exports={
          'carriers':(Carrier,['code','name','contact_email','active','is_synthetic']),
          'suppliers':(Supplier,['code','name','is_synthetic']),
          'customers':(Customer,['name','city','is_synthetic']),
          'products':(Product,['sku','name','category','brand','is_synthetic']),
          'lanes':(Lane,['origin','destination','distance_km','is_synthetic']),
          'service_types':(ServiceType,['code','name','description']),
          'accessorials':(Accessorial,['code','name','amount','eligible_scenario','is_synthetic']),
          'rate_cards':(RateCard,['code','carrier_code','origin','destination','service_type','effective_from','effective_to','currency','minimum_charge','rate_per_kg','fuel_percent','dim_divisor','is_synthetic']),
          'weight_tiers':(WeightTier,['rate_card_code','name','min_weight_kg','max_weight_kg','rate_per_kg','minimum_charge','is_synthetic']),
          'rate_card_accessorials':(RateCardAccessorial,['rate_card_code','accessorial_code','charge_method','amount','eligible','is_synthetic']),
          'shipments':(Shipment,['code','carrier_code','supplier_code','product_sku','customer_name','origin','destination','rate_card_code','shipment_date','expected_delivery','actual_delivery','delivery_status','service_type','quantity','quantity_unit','actual_weight_kg','length_cm','width_cm','height_cm','notes','is_synthetic']),
          'shipment_accessorials':(ShipmentAccessorial,['shipment_code','accessorial_code','quantity','evidence_reference','notes','is_synthetic']),
          'shipment_legs':(ShipmentLeg,['shipment_code','sequence','carrier_code','origin','destination','departure_date','arrival_date','is_synthetic']),
          'weight_measurements':(WeightMeasurement,['shipment_code','measured_weight_kg','measured_by','measured_at','evidence_reference','is_synthetic']),
          'delivery_records':(DeliveryRecord,['shipment_code','status','recorded_at','proof_reference','notes','is_synthetic']),
          'invoices':(FreightInvoice,['code','invoice_number','supplier_code','carrier_code','shipment_code','invoice_date','currency','billed_weight_kg','billed_base','billed_fuel','billed_accessorial','declared_total','billed_total','expected_base','expected_fuel','expected_accessorial','expected_total','validation_status','status','supporting_reference','is_synthetic']),
          'invoice_lines':(InvoiceLine,['code','invoice_code','description','charge_type','billed_amount','expected_amount','evidence_reference','is_synthetic']),
          'exceptions':(AuditException,['code','invoice_code','issue_type','severity','original_discrepancy','status','current_cycle','created_at','is_synthetic']),
          'analyst_reviews':(AnalystReview,['exception_code','actor_username','cycle','findings','root_cause','recommendation','recommended_amount','evidence_reference','created_at','is_synthetic']),
          'manager_decisions':(ManagerDecision,['exception_code','actor_username','cycle','decision','approved_amount','comments','created_at','is_synthetic']),
          'carrier_responses':(CarrierResponse,['exception_code','actor_username','response','proposed_amount','explanation','created_at','is_synthetic']),
          'credit_notes':(CreditNote,['code','external_identifier','exception_code','invoice_code','carrier_code','issued_amount','currency','issue_date','document_reference','verification_status','verification_comments','verified_by_username','verified_at','is_synthetic']),
          'credit_applications':(CreditApplication,['credit_note_code','invoice_code','actor_username','amount','reference','created_at','reversed_at','reversal_reason','is_synthetic']),
          'invoice_adjustments':(InvoiceAdjustment,['application_id','invoice_code','amount','reversed_at','reversal_reason','created_at','is_synthetic']),
          'reconciliation':(ReconciliationRecord,['exception_code','actor_username','approved_amount','agreed_amount','issued_amount','verified_amount','applied_amount','remaining_amount','difference','status','created_at','is_synthetic']),
          'audit_events':(AuditEvent,['created_at','actor_username','entity_type','entity_id','action','previous_state','new_state','details','amount','cycle','is_synthetic']),
        }
        for name,(model,fields) in exports.items():
            records=[]
            with (root/f'{name}.csv').open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.writer(f); w.writerow(fields)
                for obj in model.objects.iterator(chunk_size=1000):
                    values=[self.value(obj,field) for field in fields]
                    w.writerow(['' if v is None else str(v) for v in values])
                    records.append(dict(zip(fields,['' if v is None else str(v) for v in values])))
            (root/f'{name}.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')
        gt=[]
        for exc in AuditException.objects.filter(invoice__is_synthetic=True).select_related('invoice'):
            gt.append({'record_identifier':exc.invoice.code,'exception_identifier':exc.code,'issue_type':exc.issue_type,'expected_validation_outcome':exc.invoice.validation_status,'expected_workflow_outcome':'Investigation required','expected_financial_result':str(exc.original_discrepancy),'severity':exc.severity,'explanation':'Discrepancy is derived from billed total minus the contract-calculated expected amount.'})
        gt_dir=Path('data/ground_truth'); gt_dir.mkdir(parents=True,exist_ok=True)
        (gt_dir/'ground_truth.json').write_text(json.dumps(gt,indent=2),encoding='utf-8')
        with (gt_dir/'ground_truth.csv').open('w',newline='',encoding='utf-8-sig') as f:
            fields=['record_identifier','exception_identifier','issue_type','expected_validation_outcome','expected_workflow_outcome','expected_financial_result','severity','explanation']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(gt)
        self.stdout.write(self.style.SUCCESS(f'Exported {len(exports)} entity datasets to {root}; {len(gt)} ground-truth records written separately.'))
    def value(self,obj,field):
        refs={
          'carrier_code':lambda o:o.carrier.code,'supplier_code':lambda o:o.supplier.code,'product_sku':lambda o:o.product.sku,
          'rate_card_code':lambda o:o.rate_card.code if o.rate_card_id else '',
          'shipment_code':lambda o:o.shipment.code,'invoice_code':lambda o:o.invoice.code,'exception_code':lambda o:o.exception.code,
          'accessorial_code':lambda o:o.accessorial.code,'customer_name':lambda o:o.customer.name if getattr(o,'customer_id',None) else '',
          'origin':lambda o:o.origin if hasattr(o,'origin') else o.lane.origin,'destination':lambda o:o.destination if hasattr(o,'destination') else o.lane.destination,
          'actor_username':lambda o:o.actor.username if o.actor_id else '', 'verified_by_username':lambda o:o.verified_by.username if o.verified_by_id else '',
          'application_id':lambda o:o.application_id,
        }
        if field in refs: return refs[field](obj)
        if field=='currency': return obj.currency
        return getattr(obj,field,'')
