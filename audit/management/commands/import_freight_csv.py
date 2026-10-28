import csv
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from audit.models import FreightInvoice,Shipment,Supplier,Carrier,Product,Lane,RateCard,WeightTier,Customer,InvoiceLine,AuditEvent,Accessorial,RateCardAccessorial,ShipmentAccessorial,ServiceType,ShipmentLeg,WeightMeasurement,DeliveryRecord
from audit.services.invoice_validator import validate_invoice

def rows(path):
    if not path.exists(): return []
    with path.open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def yes(value): return str(value or '').lower() in ['1','true','yes','y']
def dec(value,default='0'): return Decimal(str(value or default))
def dte(value,default=None): return date.fromisoformat(value) if value else default
class Command(BaseCommand):
    help='Import linked master, shipment and invoice CSVs idempotently from the data directory.'
    def add_arguments(self,p): p.add_argument('--directory',default='data')
    @transaction.atomic
    def handle(self,*args,**o):
        root=Path(o['directory']); created={}; errors=[]
        def process(path,fn):
            if not path.exists(): return
            for line,row in enumerate(rows(path),start=2):
                try: fn(row)
                except Exception as exc: errors.append(f'{path}:{line}: {exc}')
        def carrier_fn(r):
            Carrier.objects.update_or_create(code=r['code'],defaults={'name':r['name'],'contact_email':r.get('contact_email',''),'active':yes(r.get('active','true')),'is_synthetic':yes(r.get('is_synthetic','true'))})
        def supplier_fn(r): Supplier.objects.update_or_create(code=r['code'],defaults={'name':r['name'],'is_synthetic':yes(r.get('is_synthetic','true'))})
        def product_fn(r): Product.objects.update_or_create(sku=r['sku'],defaults={'name':r['name'],'category':r['category'],'brand':r.get('brand',''),'is_synthetic':yes(r.get('is_synthetic','true'))})
        def customer_fn(r): Customer.objects.get_or_create(name=r['name'],city=r['city'],defaults={'is_synthetic':yes(r.get('is_synthetic','true'))})
        def lane_fn(r): Lane.objects.get_or_create(origin=r['origin'],destination=r['destination'],defaults={'distance_km':int(r.get('distance_km') or 500),'is_synthetic':yes(r.get('is_synthetic','true'))})
        process(root/'master'/'carriers.csv',carrier_fn); process(root/'master'/'suppliers.csv',supplier_fn); process(root/'master'/'products.csv',product_fn); process(root/'master'/'customers.csv',customer_fn); process(root/'master'/'lanes.csv',lane_fn)
        process(root/'master'/'service_types.csv',lambda r: ServiceType.objects.update_or_create(code=r['code'],defaults={'name':r['name'],'description':r.get('description','')}))
        process(root/'master'/'accessorials.csv',lambda r: Accessorial.objects.update_or_create(code=r['code'],defaults={'name':r['name'],'amount':dec(r.get('amount')),'eligible_scenario':r.get('eligible_scenario',''),'is_synthetic':yes(r.get('is_synthetic','true'))}))
        def rate_fn(r):
            carrier=Carrier.objects.get(code=r['carrier_code']); lane=Lane.objects.get(origin=r['origin'],destination=r['destination'])
            RateCard.objects.update_or_create(code=r['code'],defaults={'carrier':carrier,'lane':lane,'service_type':r.get('service_type') or 'Road Express','effective_from':dte(r.get('effective_from'),date(2025,1,1)),'effective_to':dte(r.get('effective_to')),'currency':r.get('currency') or 'INR','minimum_charge':dec(r.get('minimum_charge'),'450'),'rate_per_kg':dec(r.get('rate_per_kg'),'12.50'),'fuel_percent':dec(r.get('fuel_percent'),'12'),'dim_divisor':int(r.get('dim_divisor') or 5000),'is_synthetic':yes(r.get('is_synthetic','true'))})
        process(root/'master'/'rate_cards.csv',rate_fn)
        def rule_fn(r):
            rate=RateCard.objects.get(code=r['rate_card_code']); acc=Accessorial.objects.get(code=r['accessorial_code'])
            RateCardAccessorial.objects.update_or_create(rate_card=rate,accessorial=acc,defaults={'charge_method':r.get('charge_method') or 'FIXED','amount':dec(r.get('amount')),'eligible':yes(r.get('eligible','true')),'is_synthetic':yes(r.get('is_synthetic','true'))})
        process(root/'master'/'rate_card_accessorials.csv',rule_fn)
        def tier_fn(r):
            rate=RateCard.objects.get(code=r['rate_card_code'])
            WeightTier.objects.update_or_create(rate_card=rate,name=r['name'],defaults={'min_weight_kg':dec(r.get('min_weight_kg')),'max_weight_kg':dec(r.get('max_weight_kg')) if r.get('max_weight_kg') else None,'rate_per_kg':dec(r['rate_per_kg']),'minimum_charge':dec(r.get('minimum_charge')),'is_synthetic':yes(r.get('is_synthetic','true'))})
        process(root/'master'/'weight_tiers.csv',tier_fn)
        def shipment_fn(r):
            carrier=Carrier.objects.get(code=r['carrier_code']); supplier=Supplier.objects.get(code=r['supplier_code']); product=Product.objects.get(sku=r['product_sku']); lane=Lane.objects.get(origin=r['origin'],destination=r['destination']); rate=RateCard.objects.filter(code=r.get('rate_card_code','')).first()
            customer=Customer.objects.filter(name=r.get('customer_name','')).first() if r.get('customer_name') else None
            sh,_=Shipment.objects.update_or_create(code=r['code'],defaults={'carrier':carrier,'supplier':supplier,'product':product,'lane':lane,'rate_card':rate,'customer':customer,'shipment_date':dte(r['shipment_date']),'expected_delivery':dte(r.get('expected_delivery')),'actual_delivery':dte(r.get('actual_delivery')),'delivery_status':r.get('delivery_status') or 'In transit','service_type':r.get('service_type') or 'Road Express','quantity':int(r.get('quantity') or 1),'quantity_unit':r.get('quantity_unit') or 'cartons','actual_weight_kg':dec(r.get('actual_weight_kg'),'100'),'length_cm':dec(r.get('length_cm'),'50'),'width_cm':dec(r.get('width_cm'),'40'),'height_cm':dec(r.get('height_cm'),'40'),'notes':r.get('notes',''),'is_synthetic':yes(r.get('is_synthetic','true'))})
            ShipmentLeg.objects.get_or_create(shipment=sh,sequence=1,defaults={'carrier':carrier,'origin':sh.lane.origin,'destination':sh.lane.destination,'departure_date':sh.shipment_date,'arrival_date':sh.actual_delivery,'is_synthetic':sh.is_synthetic})
            WeightMeasurement.objects.get_or_create(shipment=sh,measured_weight_kg=sh.actual_weight_kg,defaults={'measured_by':'CSV import','measured_at':timezone.now(),'evidence_reference':f'CSV-WEIGHT-{sh.code}','is_synthetic':sh.is_synthetic})
            DeliveryRecord.objects.get_or_create(shipment=sh,status=sh.delivery_status,defaults={'recorded_at':timezone.now(),'proof_reference':f'POD-{sh.code}' if sh.actual_delivery else '', 'notes':'Imported delivery status.','is_synthetic':sh.is_synthetic})
        process(root/'transactions'/'shipments.csv',shipment_fn)
        def shipment_accessorial_fn(r):
            sh=Shipment.objects.get(code=r['shipment_code']); acc=Accessorial.objects.get(code=r['accessorial_code'])
            ShipmentAccessorial.objects.update_or_create(shipment=sh,accessorial=acc,defaults={'quantity':int(r.get('quantity') or 1),'evidence_reference':r.get('evidence_reference',''),'notes':r.get('notes',''),'is_synthetic':yes(r.get('is_synthetic','true'))})
        process(root/'transactions'/'shipment_accessorials.csv',shipment_accessorial_fn)
        def invoice_fn(r):
            number=(r.get('invoice_number') or r.get('code') or '').strip()
            if not number: raise ValueError('invoice_number or code is required')
            if FreightInvoice.objects.filter(invoice_number=number).exists() or (r.get('code') and FreightInvoice.objects.filter(code=r['code']).exists()):
                created['skipped']=created.get('skipped',0)+1; return
            ship_code=r.get('shipment_code') or r.get('shipment') or r.get('shipment_id')
            shipment=Shipment.objects.filter(code=ship_code).first() if ship_code else None
            if not shipment and ship_code and str(ship_code).isdigit(): shipment=Shipment.objects.filter(pk=int(ship_code)).first()
            if not shipment: raise ValueError(f'unknown shipment reference: {ship_code}')
            supplier=Supplier.objects.filter(code=r.get('supplier_code','')).first() if r.get('supplier_code') else shipment.supplier
            carrier=Carrier.objects.filter(code=r.get('carrier_code','')).first() if r.get('carrier_code') else shipment.carrier
            if not supplier or not carrier: raise ValueError('supplier or carrier reference could not be resolved')
            invoice_date=dte(r.get('invoice_date'),date.today())
            submitted_at=timezone.make_aware(timezone.datetime.combine(invoice_date+timedelta(days=1),timezone.datetime.min.time()))
            inv=FreightInvoice.objects.create(code=r.get('code') or f'IMP-{number[:34]}',invoice_number=number,supplier=supplier,carrier=carrier,shipment=shipment,invoice_date=invoice_date,submitted_at=submitted_at,created_at=submitted_at,currency=r.get('currency') or 'INR',billed_weight_kg=dec(r.get('billed_weight_kg')) if r.get('billed_weight_kg') else None,billed_base=dec(r.get('billed_base')),billed_fuel=dec(r.get('billed_fuel')),billed_accessorial=dec(r.get('billed_accessorial')),declared_total=dec(r.get('declared_total')) if r.get('declared_total') else None,supporting_reference=r.get('supporting_reference',''),is_synthetic=yes(r.get('is_synthetic','true')))
            validate_invoice(inv,None)
            for seq,(label,kind,billed,expected) in enumerate([('Contracted base freight','BASE',inv.billed_base,inv.expected_base),('Fuel surcharge','FUEL',inv.billed_fuel,inv.expected_fuel),('Accessorial charges','ACCESSORIAL',inv.billed_accessorial,inv.expected_accessorial)],1): InvoiceLine.objects.get_or_create(code=f'{inv.code}-L{seq:02d}',defaults={'invoice':inv,'description':label,'charge_type':kind,'billed_amount':billed,'expected_amount':expected,'evidence_reference':inv.supporting_reference,'is_synthetic':inv.is_synthetic})
            AuditEvent.objects.create(entity_type='FreightInvoice',entity_id=inv.code,action='Invoice imported from CSV',new_state=inv.validation_status,details=f'Source file: {root}/transactions/invoices.csv',is_synthetic=inv.is_synthetic)
            created['invoices']=created.get('invoices',0)+1
        invoice_path=root/'transactions'/'invoices.csv'
        if not invoice_path.exists(): invoice_path=root/'invoices.csv'
        if not invoice_path.exists(): invoice_path=root/'exports'/'invoices.csv'
        process(invoice_path,invoice_fn)
        self.stdout.write(f'Import summary: invoices created={created.get("invoices",0)}, existing invoices skipped={created.get("skipped",0)}, row errors={len(errors)}')
        for e in errors[:100]: self.stderr.write(e)
        if errors: raise CommandError('CSV import completed with row errors; correct the reported references and retry.')
