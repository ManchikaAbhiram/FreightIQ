from django.contrib import admin
from .models import *
admin.site.site_header='FreightIQ Administration'
admin.site.site_title='FreightIQ Admin'
admin.site.index_title='System administration and master data'
for model in [UserProfile,Carrier,Supplier,Customer,Product,Lane,ServiceType,RateCard,WeightTier,Accessorial,RateCardAccessorial,Shipment,ShipmentAccessorial,ShipmentLeg,WeightMeasurement,DeliveryRecord,FreightInvoice,InvoiceLine,AuditException,AnalystReview,ManagerDecision,CarrierResponse,CreditNote,CreditApplication,InvoiceAdjustment,ReconciliationRecord,AuditEvent]:
    try: admin.site.register(model)
    except admin.sites.AlreadyRegistered: pass
