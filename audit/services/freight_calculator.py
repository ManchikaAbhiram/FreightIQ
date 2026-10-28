from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from audit.models import RateCard
CENT=Decimal('0.01')
def money(value): return Decimal(value).quantize(CENT,rounding=ROUND_HALF_UP)
def calculate_expected(shipment):
    rate=shipment.rate_card or RateCard.objects.filter(carrier=shipment.carrier,lane=shipment.lane,service_type=shipment.service_type,effective_from__lte=shipment.shipment_date).filter(models_q_valid(shipment)).order_by('-effective_from').first()
    if not rate: raise ValidationError('No valid rate card matches this carrier, lane, service and shipment date.')
    if rate.carrier_id != shipment.carrier_id or rate.lane_id != shipment.lane_id: raise ValidationError('Shipment rate card does not match carrier and lane.')
    if rate.service_type != shipment.service_type: raise ValidationError('Shipment service type does not match the selected rate card.')
    if rate.effective_from>shipment.shipment_date or (rate.effective_to and rate.effective_to<shipment.shipment_date): raise ValidationError('Rate card is not valid on shipment date.')
    weight=max(shipment.actual_weight_kg,shipment.dimensional_weight_kg)
    tier=rate.weight_tiers.filter(min_weight_kg__lte=weight).filter(models_q_tier(weight)).order_by('-min_weight_kg').first()
    per_kg=tier.rate_per_kg if tier else rate.rate_per_kg
    minimum=tier.minimum_charge if tier and tier.minimum_charge else rate.minimum_charge
    base=money(max(minimum,weight*per_kg))
    fuel=money(base*rate.fuel_percent/Decimal('100'))
    accessorial_total=Decimal('0.00'); accessorial_breakdown=[]; unsupported=[]
    for shipment_charge in shipment.shipment_accessorials.select_related('accessorial').all():
        rule=rate.accessorial_rules.filter(accessorial=shipment_charge.accessorial,eligible=True).first()
        if not rule:
            unsupported.append(shipment_charge.accessorial.name); continue
        charge=rule.amount*shipment_charge.quantity if rule.charge_method=='FIXED' else base*rule.amount/Decimal('100')*shipment_charge.quantity
        charge=money(charge); accessorial_total+=charge
        accessorial_breakdown.append({'name':shipment_charge.accessorial.name,'quantity':shipment_charge.quantity,'amount':charge,'evidence_reference':shipment_charge.evidence_reference})
    accessorial_total=money(accessorial_total)
    return {'rate_card':rate,'billable_weight':weight,'base':base,'fuel':fuel,'accessorial':accessorial_total,'accessorial_breakdown':accessorial_breakdown,'unsupported_accessorials':unsupported,'total':money(base+fuel+accessorial_total)}
def models_q_valid(shipment):
    from django.db.models import Q
    return Q(effective_to__isnull=True)|Q(effective_to__gte=shipment.shipment_date)

def models_q_tier(weight):
    from django.db.models import Q
    return Q(max_weight_kg__isnull=True)|Q(max_weight_kg__gte=weight)
