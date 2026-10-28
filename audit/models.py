from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

ROLES = [('PLANNER','Planner'),('SUPPLIER','Supplier'),('CARRIER','Carrier / Warehouse Operator'),('ANALYST','Logistics Analyst'),('MANAGER','Operations Manager'),('FINANCE','Finance / Reconciliation')]
ROLE_RESPONSIBILITIES = {
 'PLANNER':'Create and maintain shipments, carrier assignments, cargo weights, dimensions, shipment legs and delivery records. Cannot approve credits or change financial decisions.',
 'SUPPLIER':'Submit freight invoices and supporting documents, review validation results and track invoice history. Cannot change contracts or manager decisions and can only access own invoices.',
 'CARRIER':'Review manager-approved cases, accept or dispute requests, submit counteroffers and track agreed credit notes. Can only access cases assigned to the approved carrier organization.',
 'ANALYST':'Investigate discrepancies, review contract and delivery evidence, record root causes and recommend credit, no credit or further information. Cannot make manager decisions or issue credits.',
 'MANAGER':'Review findings and evidence, approve, reject with reasons or return incomplete cases. Cannot bypass required carrier confirmation or treat approval as an issued credit.',
 'FINANCE':'Record and verify actual credit notes, apply eligible verified credits, record reversals and reconcile financial balances. Cannot invent carrier acceptance or manager approval.',
}
class UserProfile(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='profile')
    full_name=models.CharField(max_length=140)
    requested_role=models.CharField(max_length=20,choices=ROLES)
    approved_role=models.CharField(max_length=20,choices=ROLES,blank=True)
    organization_name=models.CharField(max_length=180,blank=True)
    carrier=models.ForeignKey('Carrier',null=True,blank=True,on_delete=models.SET_NULL)
    supplier=models.ForeignKey('Supplier',null=True,blank=True,on_delete=models.SET_NULL)
    status=models.CharField(max_length=12,choices=[('PENDING','Pending'),('APPROVED','Approved'),('REJECTED','Rejected')],default='PENDING')
    rejection_reason=models.TextField(blank=True)
    reviewed_by=models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL,related_name='registration_reviews')
    reviewed_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    @property
    def responsibilities(self): return ROLE_RESPONSIBILITIES.get(self.approved_role or self.requested_role,'')
    def __str__(self): return f'{self.full_name} ({self.get_status_display()})'

class Carrier(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    code=models.CharField(max_length=20,unique=True)
    name=models.CharField(max_length=180,unique=True)
    contact_email=models.EmailField(blank=True)
    active=models.BooleanField(default=True)
    def __str__(self): return self.name
class Supplier(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    code=models.CharField(max_length=20,unique=True)
    name=models.CharField(max_length=180,unique=True)
    def __str__(self): return self.name
class Customer(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    name=models.CharField(max_length=180)
    city=models.CharField(max_length=80)
    def __str__(self): return self.name
class Product(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    sku=models.CharField(max_length=32,unique=True)
    name=models.CharField(max_length=180)
    category=models.CharField(max_length=100)
    brand=models.CharField(max_length=100,blank=True)
    def __str__(self): return f'{self.name} ({self.sku})'
class Lane(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    origin=models.CharField(max_length=100)
    destination=models.CharField(max_length=100)
    distance_km=models.PositiveIntegerField(default=500)
    class Meta: unique_together=[('origin','destination')]
    def __str__(self): return f'{self.origin} → {self.destination}'
class ServiceType(models.Model):
    code=models.CharField(max_length=30,unique=True)
    name=models.CharField(max_length=100,unique=True)
    description=models.CharField(max_length=255,blank=True)
    def __str__(self): return self.name

class RateCard(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    code=models.CharField(max_length=50,unique=True)
    carrier=models.ForeignKey(Carrier,on_delete=models.PROTECT)
    lane=models.ForeignKey(Lane,on_delete=models.PROTECT)
    service_type=models.CharField(max_length=40,default='Road Express')
    effective_from=models.DateField()
    effective_to=models.DateField(null=True,blank=True)
    currency=models.CharField(max_length=3,default='INR')
    minimum_charge=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('450'))
    rate_per_kg=models.DecimalField(max_digits=10,decimal_places=2,default=Decimal('12.50'))
    fuel_percent=models.DecimalField(max_digits=5,decimal_places=2,default=Decimal('12.00'))
    dim_divisor=models.PositiveIntegerField(default=5000)
    def __str__(self): return self.code
class WeightTier(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    rate_card=models.ForeignKey(RateCard,on_delete=models.CASCADE,related_name='weight_tiers')
    name=models.CharField(max_length=80)
    min_weight_kg=models.DecimalField(max_digits=10,decimal_places=2,default=Decimal('0'))
    max_weight_kg=models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    rate_per_kg=models.DecimalField(max_digits=10,decimal_places=2)
    minimum_charge=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    class Meta: ordering=['min_weight_kg']
    def __str__(self): return f'{self.rate_card.code} · {self.name}'

class Shipment(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    code=models.CharField(max_length=40,unique=True)
    carrier=models.ForeignKey(Carrier,on_delete=models.PROTECT)
    supplier=models.ForeignKey(Supplier,on_delete=models.PROTECT)
    customer=models.ForeignKey(Customer,null=True,blank=True,on_delete=models.SET_NULL)
    product=models.ForeignKey(Product,on_delete=models.PROTECT)
    lane=models.ForeignKey(Lane,on_delete=models.PROTECT)
    rate_card=models.ForeignKey(RateCard,null=True,blank=True,on_delete=models.PROTECT)
    shipment_date=models.DateField()
    expected_delivery=models.DateField(null=True,blank=True)
    actual_delivery=models.DateField(null=True,blank=True)
    delivery_status=models.CharField(max_length=24,default='In transit')
    service_type=models.CharField(max_length=40,default='Road Express')
    quantity=models.PositiveIntegerField(default=1)
    quantity_unit=models.CharField(max_length=24,default='cartons')
    actual_weight_kg=models.DecimalField(max_digits=10,decimal_places=2,default=Decimal('100'))
    length_cm=models.DecimalField(max_digits=8,decimal_places=2,default=Decimal('50'))
    width_cm=models.DecimalField(max_digits=8,decimal_places=2,default=Decimal('40'))
    height_cm=models.DecimalField(max_digits=8,decimal_places=2,default=Decimal('40'))
    notes=models.TextField(blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    @property
    def dimensional_weight_kg(self):
        divisor=self.rate_card.dim_divisor if self.rate_card else 5000
        return (self.length_cm*self.width_cm*self.height_cm*self.quantity/Decimal(divisor)).quantize(Decimal('0.01'))
    @property
    def billable_weight_kg(self): return max(self.actual_weight_kg,self.dimensional_weight_kg)
    def __str__(self): return self.code
class ShipmentAccessorial(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    shipment=models.ForeignKey(Shipment,on_delete=models.CASCADE,related_name='shipment_accessorials')
    accessorial=models.ForeignKey('Accessorial',on_delete=models.PROTECT)
    quantity=models.PositiveSmallIntegerField(default=1)
    evidence_reference=models.CharField(max_length=180,blank=True)
    notes=models.TextField(blank=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['shipment','accessorial'],name='unique_shipment_accessorial')]

class ShipmentLeg(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    shipment=models.ForeignKey(Shipment,on_delete=models.CASCADE,related_name='legs')
    sequence=models.PositiveSmallIntegerField(default=1)
    carrier=models.ForeignKey(Carrier,on_delete=models.PROTECT)
    origin=models.CharField(max_length=100)
    destination=models.CharField(max_length=100)
    departure_date=models.DateField(null=True,blank=True)
    arrival_date=models.DateField(null=True,blank=True)
class WeightMeasurement(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    shipment=models.ForeignKey(Shipment,on_delete=models.CASCADE,related_name='measurements')
    measured_weight_kg=models.DecimalField(max_digits=10,decimal_places=2)
    measured_by=models.CharField(max_length=140,blank=True)
    measured_at=models.DateTimeField(default=timezone.now)
    evidence_reference=models.CharField(max_length=180,blank=True)
class DeliveryRecord(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    shipment=models.ForeignKey(Shipment,on_delete=models.CASCADE,related_name='delivery_records')
    status=models.CharField(max_length=40,default='Delivered')
    recorded_at=models.DateTimeField(default=timezone.now)
    proof_reference=models.CharField(max_length=180,blank=True)
    notes=models.TextField(blank=True)
class Accessorial(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    code=models.CharField(max_length=30,unique=True)
    name=models.CharField(max_length=100)
    amount=models.DecimalField(max_digits=10,decimal_places=2,default=Decimal('0'))
    eligible_scenario=models.CharField(max_length=120,blank=True)
    def __str__(self): return self.name

class RateCardAccessorial(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    rate_card=models.ForeignKey(RateCard,on_delete=models.CASCADE,related_name='accessorial_rules')
    accessorial=models.ForeignKey(Accessorial,on_delete=models.PROTECT)
    charge_method=models.CharField(max_length=20,choices=[('FIXED','Fixed per unit'),('PERCENT_BASE','Percentage of base freight')],default='FIXED')
    amount=models.DecimalField(max_digits=10,decimal_places=2,default=Decimal('0'))
    eligible=models.BooleanField(default=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['rate_card','accessorial'],name='unique_rate_accessorial')]

class FreightInvoice(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    code=models.CharField(max_length=40,unique=True)
    invoice_number=models.CharField(max_length=80,unique=True)
    supplier=models.ForeignKey(Supplier,on_delete=models.PROTECT)
    carrier=models.ForeignKey(Carrier,on_delete=models.PROTECT)
    shipment=models.ForeignKey(Shipment,on_delete=models.PROTECT,related_name='invoices')
    invoice_date=models.DateField()
    submitted_by=models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL)
    submitted_at=models.DateTimeField(default=timezone.now)
    currency=models.CharField(max_length=3,default='INR')
    billed_weight_kg=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    billed_base=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    billed_fuel=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    billed_accessorial=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    billed_total=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    declared_total=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    expected_base=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    expected_fuel=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    expected_accessorial=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    expected_total=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    validation_status=models.CharField(max_length=32,default='PENDING')
    status=models.CharField(max_length=40,default='SUBMITTED')
    supporting_reference=models.CharField(max_length=255,blank=True)
    supporting_document=models.FileField(upload_to='invoice_evidence/',blank=True)
    validation_findings=models.JSONField(default=list,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    @property
    def discrepancy(self): return (self.billed_total or Decimal('0'))-(self.expected_total or Decimal('0'))
    def __str__(self): return self.code
class InvoiceLine(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    invoice=models.ForeignKey(FreightInvoice,on_delete=models.CASCADE,related_name='lines')
    code=models.CharField(max_length=70,unique=True)
    description=models.CharField(max_length=160)
    charge_type=models.CharField(max_length=30)
    billed_amount=models.DecimalField(max_digits=12,decimal_places=2)
    expected_amount=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    evidence_reference=models.CharField(max_length=180,blank=True)
class AuditException(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    code=models.CharField(max_length=40,unique=True)
    invoice=models.ForeignKey(FreightInvoice,on_delete=models.PROTECT,related_name='exceptions')
    issue_type=models.CharField(max_length=80)
    severity=models.CharField(max_length=16,default='Medium')
    original_discrepancy=models.DecimalField(max_digits=12,decimal_places=2)
    status=models.CharField(max_length=50,default='NEW')
    current_cycle=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['invoice'],name='unique_exception_per_invoice')]
    def __str__(self): return self.code
class AnalystReview(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    exception=models.ForeignKey(AuditException,on_delete=models.CASCADE,related_name='reviews')
    actor=models.ForeignKey(User,on_delete=models.PROTECT)
    cycle=models.PositiveIntegerField(default=1)
    findings=models.TextField()
    root_cause=models.CharField(max_length=180,blank=True)
    recommendation=models.CharField(max_length=30,choices=[('CREDIT','Recommend credit'),('NO_CREDIT','No credit'),('INFO','Need information')])
    recommended_amount=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    evidence_reference=models.CharField(max_length=255,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
class ManagerDecision(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    exception=models.ForeignKey(AuditException,on_delete=models.CASCADE,related_name='decisions')
    actor=models.ForeignKey(User,on_delete=models.PROTECT)
    cycle=models.PositiveIntegerField(default=1)
    decision=models.CharField(max_length=20,choices=[('APPROVE','Approve'),('REJECT','Reject'),('RETURN','Return to analyst')])
    approved_amount=models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'))
    comments=models.TextField()
    created_at=models.DateTimeField(default=timezone.now)
class CarrierResponse(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    exception=models.ForeignKey(AuditException,on_delete=models.CASCADE,related_name='carrier_responses')
    actor=models.ForeignKey(User,on_delete=models.PROTECT)
    response=models.CharField(max_length=20,choices=[('ACCEPT','Accept'),('DISPUTE','Dispute'),('COUNTEROFFER','Counteroffer')])
    proposed_amount=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    explanation=models.TextField()
    created_at=models.DateTimeField(default=timezone.now)
class CreditNote(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    code=models.CharField(max_length=60,unique=True)
    external_identifier=models.CharField(max_length=100,blank=True)
    exception=models.ForeignKey(AuditException,on_delete=models.PROTECT,related_name='credit_notes')
    invoice=models.ForeignKey(FreightInvoice,on_delete=models.PROTECT,related_name='credit_notes')
    carrier=models.ForeignKey(Carrier,on_delete=models.PROTECT)
    issued_amount=models.DecimalField(max_digits=12,decimal_places=2)
    currency=models.CharField(max_length=3,default='INR')
    issue_date=models.DateField()
    document_reference=models.CharField(max_length=255,blank=True)
    verification_status=models.CharField(max_length=24,default='PENDING')
    verification_comments=models.TextField(blank=True)
    verified_by=models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL,related_name='verified_credits')
    verified_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['carrier','external_identifier'],condition=~models.Q(external_identifier=''),name='unique_carrier_external_credit_note')]
    @property
    def applied_amount(self):
        return sum((x.amount for x in self.applications.filter(reversed_at__isnull=True)),Decimal('0.00'))
    @property
    def remaining_amount(self): return max(Decimal('0.00'),self.issued_amount-self.applied_amount)
class CreditApplication(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    credit_note=models.ForeignKey(CreditNote,on_delete=models.PROTECT,related_name='applications')
    invoice=models.ForeignKey(FreightInvoice,on_delete=models.PROTECT,related_name='credit_applications')
    actor=models.ForeignKey(User,on_delete=models.PROTECT)
    amount=models.DecimalField(max_digits=12,decimal_places=2)
    reference=models.CharField(max_length=100,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    reversed_at=models.DateTimeField(null=True,blank=True)
    reversal_reason=models.TextField(blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['credit_note','reference'],condition=~models.Q(reference=''),name='unique_credit_application_reference')]
class InvoiceAdjustment(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    application=models.OneToOneField(CreditApplication,on_delete=models.PROTECT,related_name='adjustment')
    invoice=models.ForeignKey(FreightInvoice,on_delete=models.PROTECT,related_name='adjustments')
    amount=models.DecimalField(max_digits=12,decimal_places=2)
    reversed_at=models.DateTimeField(null=True,blank=True)
    reversal_reason=models.TextField(blank=True)
    created_at=models.DateTimeField(default=timezone.now)
class ReconciliationRecord(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    exception=models.ForeignKey(AuditException,on_delete=models.PROTECT,related_name='reconciliations')
    actor=models.ForeignKey(User,on_delete=models.PROTECT)
    approved_amount=models.DecimalField(max_digits=12,decimal_places=2)
    agreed_amount=models.DecimalField(max_digits=12,decimal_places=2)
    issued_amount=models.DecimalField(max_digits=12,decimal_places=2)
    verified_amount=models.DecimalField(max_digits=12,decimal_places=2)
    applied_amount=models.DecimalField(max_digits=12,decimal_places=2)
    remaining_amount=models.DecimalField(max_digits=12,decimal_places=2)
    difference=models.DecimalField(max_digits=12,decimal_places=2)
    status=models.CharField(max_length=24,default='OPEN')
    created_at=models.DateTimeField(default=timezone.now)
class AuditEvent(models.Model):
    is_synthetic=models.BooleanField(default=False, db_index=True)
    actor=models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL)
    entity_type=models.CharField(max_length=40)
    entity_id=models.CharField(max_length=60)
    action=models.CharField(max_length=100)
    previous_state=models.CharField(max_length=60,blank=True)
    new_state=models.CharField(max_length=60,blank=True)
    details=models.TextField(blank=True)
    amount=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    cycle=models.PositiveIntegerField(null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    class Meta: ordering=['-created_at']
