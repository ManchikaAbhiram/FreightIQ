import random
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from audit.models import *
from audit.services.invoice_validator import validate_invoice

CARRIERS = [
    'DTDC Express', 'Blue Dart Express', 'Delhivery', 'XpressBees',
    'DHL Express India', 'FedEx India', 'Safexpress', 'Gati Express',
    'TCI Express', 'VRL Logistics', 'Mahindra Logistics',
    'Allcargo Logistics', 'Ecom Express', 'Shadowfax',
    'India Post Logistics', 'Deccan Route Logistics',
    'Hyderabad Metro Cargo', 'Telangana Road Freight',
    'Southern Cross Transport', 'Western Ghats Logistics',
    'Eastern Corridor Freight', 'Northern Star Distribution',
    'Coastal Link Cargo', 'Bharat Transit Network',
    'Pioneer Road Carriers', 'Summit Freight Services',
    'Riverstone Cargo Network', 'Skybridge Distribution',
    'Copperline Freight Services', 'Meridian Transit Services',
    'Asteron Road Freight', 'Novacrest Cargo Systems',
    'Silverleaf Transit Partners', 'Cedarline Transport Works',
    'SwiftHarbor Cargo', 'BluePeak Freight Network',
    'Kaveri Cargo Movers', 'Godavari Freight Lines',
    'Krishna Valley Logistics', 'Deccan Express Carriers',
    'Charminar Cargo Services', 'Warangal Freight Solutions',
    'Andhra Coastal Logistics', 'Coromandel Cargo Network',
    'Malabar Roadways', 'Konkan Freight Connect',
    'Vindhya Transport Services', 'Aravalli Cargo Lines',
    'Narmada Logistics Group', 'Tungabhadra Transit',
    'Penna River Freight', 'Mahanadi Cargo Services',
    'Brahmaputra Distribution', 'Indus Valley Carriers',
    'Ganga Freight Network', 'Yamuna Logistics',
    'Western Star Cargo', 'Eastern Gate Transport',
    'Southern Route Carriers', 'Central India Freight',
    'MetroLink Logistics India', 'PrimeTrack Cargo',
    'Reliable Route Transport', 'Evergreen Freight India',
    'ApexLine Logistics', 'RapidWay Cargo Services',
    'TrueRoute Distribution', 'FirstMile Freight Network',
    'LastMile Cargo Connect', 'CargoSpring Logistics',
    'LoadBridge Transport', 'RoadRunner Freight India',
    'FleetPath Logistics', 'RouteWise Cargo', 'TransitPro India',
    'CargoCraft Logistics', 'FreightNest Transport',
    'BlueHorizon Carriers', 'SilverRoute Logistics',
    'Golden Mile Freight', 'RedEarth Cargo Services',
    'GreenField Transport Network', 'UrbanGate Logistics',
    'HighwayStar Carriers', 'SwiftLane Freight India',
    'CargoOrbit Logistics', 'NorthGate Transport Services',
    'SouthGate Freight Network', 'EastWest Cargo Lines',
    'Continental Route Logistics', 'ReliableHaul India',
    'PrimeHaul Transport', 'AnchorPoint Cargo',
    'CrownRoute Logistics', 'Bridgeway Freight Services',
    'OpenRoad Distribution', 'PaceLine Transport',
    'FleetBridge Cargo', 'HarborView Logistics',
    'CrossTown Freight Network'
]

SUPPLIERS = [
    'Asteron Industrial Components Pvt Ltd',
    'Veyra Home Appliances India',
    'Novacrest Electricals Pvt Ltd',
    'Silverleaf Consumer Products',
    'Kestrel Automotive Supply',
    'Juniper Household Goods',
    'LumenEdge Electronics India',
    'Westhaven Packaging Works',
    'Arclight Controls India',
    'Evercrest Mobility Parts',
    'Deccan Auto Components',
    'Sunrise Electronics Pvt Ltd',
    'Godavari Medical Supplies',
    'Charminar Industrial Traders',
    'Kaveri Packaging Solutions',
    'Southern Star Appliances',
    'Bharat Switchgear Industries',
    'Pioneer Bearings India',
    'MetroCare Healthcare Supplies',
    'GreenField Consumer Goods',
    'Apex Automotive Spares',
    'BluePeak Lighting Systems',
    'Crownfield Engineering Works',
    'Riverbend Plastics India',
    'Summit Electrical Systems',
    'Oakwell Retail Products',
    'Harborline Industrial Supply',
    'PrimeRoute Components',
    'SilverOak Medical Devices',
    'WestGate Textile Mills'
]

PRODUCTS = [
    ('Brake assemblies', 'Automotive components', 'Kestrel'),
    ('Oil filters', 'Automotive components', 'Kestrel'),
    ('Wheel bearings', 'Automotive components', 'Asteron'),
    ('Hydraulic pumps', 'Industrial machinery', 'Asteron'),
    ('LED lighting panels', 'Electronics', 'Novacrest'),
    ('Smart television units', 'Home appliances', 'Veyra'),
    ('Refrigeration control boards', 'Electronics', 'Novacrest'),
    ('Electrical switchgear', 'Electrical equipment', 'LumenEdge'),
    ('Packaged household cleaners', 'FMCG', 'Juniper'),
    ('Personal-care product cartons', 'Consumer goods', 'Silverleaf'),
    ('Industrial power supplies', 'Electronics', 'LumenEdge'),
    ('Transmission components', 'Automotive components', 'Kestrel'),
    ('Medical examination gloves', 'Medical supplies', 'Godavari'),
    ('Diagnostic test kits', 'Medical supplies', 'Godavari'),
    ('Cotton garment cartons', 'Textiles', 'WestGate'),
    ('Corrugated packaging boxes', 'Packaging', 'Kaveri'),
    ('Solar inverter units', 'Electrical equipment', 'BluePeak'),
    ('Copper electrical cables', 'Electrical equipment', 'Bharat'),
    ('Stainless steel fasteners', 'Industrial components', 'Deccan'),
    ('Water purifier assemblies', 'Home appliances', 'Southern Star'),
    ('Laptop docking stations', 'Electronics', 'Sunrise'),
    ('Mobile phone accessories', 'Electronics', 'Sunrise'),
    ('Automotive air filters', 'Automotive components', 'Apex'),
    ('Industrial safety helmets', 'Safety equipment', 'Pioneer'),
    ('PVC pipe fittings', 'Building materials', 'Riverbend'),
    ('Food-grade storage containers', 'Household goods', 'Oakwell'),
    ('Pharmaceutical packaging cartons', 'Packaging', 'MetroCare'),
    ('Textile dyeing chemicals', 'Industrial supplies', 'WestGate'),
    ('Electric motor assemblies', 'Industrial machinery', 'Summit'),
    ('Precision machine tools', 'Industrial machinery', 'Crownfield'),
    ('Printed circuit boards', 'Electronics', 'Arclight'),
    ('Refrigerator compressor parts', 'Home appliances', 'Veyra'),
    ('Agricultural pump sets', 'Industrial machinery', 'Kaveri'),
    ('Office stationery cartons', 'Consumer goods', 'Oakwell'),
    ('Ceramic tile cartons', 'Building materials', 'Harborline'),
    ('Bicycle spare parts', 'Mobility parts', 'Evercrest'),
    ('Battery management modules', 'Electronics', 'LumenEdge'),
    ('Packaged dry food cartons', 'FMCG', 'GreenField'),
    ('Protective glass panels', 'Electronics', 'Sunrise'),
    ('Industrial valve assemblies', 'Industrial components', 'Deccan')
]

LANES = [
    ('Hyderabad', 'Bengaluru', 570),
    ('Hyderabad', 'Chennai', 625),
    ('Hyderabad', 'Pune', 560),
    ('Chennai', 'Bengaluru', 350),
    ('Mumbai', 'Pune', 150),
    ('Delhi', 'Jaipur', 280),
    ('Bengaluru', 'Coimbatore', 365),
    ('Pune', 'Ahmedabad', 660),
    ('Hyderabad', 'Vijayawada', 275),
    ('Chennai', 'Coimbatore', 505),
    ('Bengaluru', 'Hyderabad', 570),
    ('Pune', 'Mumbai', 150),
    ('Hyderabad', 'Visakhapatnam', 620),
    ('Delhi', 'Lucknow', 550),
    ('Mumbai', 'Ahmedabad', 530),
    ('Bengaluru', 'Mysuru', 145),
    ('Chennai', 'Madurai', 460),
    ('Pune', 'Nagpur', 710),
    ('Kolkata', 'Bhubaneswar', 440),
    ('Jaipur', 'Delhi', 280)
]


class Command(BaseCommand):
    help = 'Generate reproducible, linked fictional FreightIQ business records.'

    def add_arguments(self, p):
        p.add_argument('--seed', type=int, default=20261022)
        p.add_argument('--carriers', type=int, default=100)
        p.add_argument('--shipments', type=int, default=20000)
        p.add_argument('--invoices', type=int, default=15000)
        p.add_argument(
            '--reset',
            action='store_true',
            help='Delete only records explicitly marked synthetic before regenerating'
        )

    @transaction.atomic
    def handle(self, *args, **o):
        rng = random.Random(o['seed'])
        ncar = o['carriers']
        nship = o['shipments']
        ninv = min(o['invoices'], nship)

        if o['reset']:
            AuditEvent.objects.filter(is_synthetic=True).delete()
            ShipmentAccessorial.objects.filter(is_synthetic=True).delete()
            RateCardAccessorial.objects.filter(is_synthetic=True).delete()
            ReconciliationRecord.objects.filter(is_synthetic=True).delete()
            InvoiceAdjustment.objects.filter(is_synthetic=True).delete()
            CreditApplication.objects.filter(is_synthetic=True).delete()
            CreditNote.objects.filter(is_synthetic=True).delete()
            CarrierResponse.objects.filter(is_synthetic=True).delete()
            ManagerDecision.objects.filter(is_synthetic=True).delete()
            AnalystReview.objects.filter(is_synthetic=True).delete()
            AuditException.objects.filter(is_synthetic=True).delete()
            InvoiceLine.objects.filter(is_synthetic=True).delete()
            FreightInvoice.objects.filter(is_synthetic=True).delete()
            DeliveryRecord.objects.filter(is_synthetic=True).delete()
            WeightMeasurement.objects.filter(is_synthetic=True).delete()
            ShipmentLeg.objects.filter(is_synthetic=True).delete()
            Shipment.objects.filter(is_synthetic=True).delete()
            RateCard.objects.filter(is_synthetic=True).delete()
            Accessorial.objects.filter(is_synthetic=True).delete()
            Lane.objects.filter(is_synthetic=True).delete()
            Product.objects.filter(is_synthetic=True).delete()
            Customer.objects.filter(is_synthetic=True).delete()
            Supplier.objects.filter(is_synthetic=True).delete()
            Carrier.objects.filter(is_synthetic=True).delete()

        carriers = list(
            Carrier.objects.filter(is_synthetic=True).order_by('code')[:ncar]
        )

        if len(carriers) < ncar:
            new = [
                Carrier(
                    code=f'SYN-CAR-{i:06d}',
                    name=CARRIERS[(i - 1) % len(CARRIERS)],
                    is_synthetic=True
                )
                for i in range(len(carriers) + 1, ncar + 1)
            ]
            Carrier.objects.bulk_create(new, ignore_conflicts=True)

        carriers = list(
            Carrier.objects.filter(is_synthetic=True).order_by('code')[:ncar]
        )

        for i, carrier in enumerate(carriers, start=1):
            expected_name = CARRIERS[(i - 1) % len(CARRIERS)]
            if carrier.name != expected_name:
                carrier.name = expected_name
                carrier.save(update_fields=['name'])

        suppliers = list(
            Supplier.objects.filter(is_synthetic=True).order_by('code')
        )
        existing_supplier_codes = set(
            Supplier.objects.filter(is_synthetic=True).values_list('code', flat=True)
        )

        Supplier.objects.bulk_create(
            [
                Supplier(
                    code=f'SYN-SUP-{i:04d}',
                    name=name,
                    is_synthetic=True
                )
                for i, name in enumerate(SUPPLIERS, 1)
                if f'SYN-SUP-{i:04d}' not in existing_supplier_codes
            ],
            ignore_conflicts=True
        )

        suppliers = list(
            Supplier.objects.filter(is_synthetic=True).order_by('code')
        )

        for i, supplier in enumerate(suppliers, start=1):
            if i <= len(SUPPLIERS) and supplier.name != SUPPLIERS[i - 1]:
                supplier.name = SUPPLIERS[i - 1]
                supplier.save(update_fields=['name'])

        products = list(
            Product.objects.filter(is_synthetic=True).order_by('sku')
        )
        existing_product_skus = set(
            Product.objects.filter(is_synthetic=True).values_list('sku', flat=True)
        )

        Product.objects.bulk_create(
            [
                Product(
                    sku=f'SYN-SKU-{i:04d}',
                    name=x[0],
                    category=x[1],
                    brand=x[2],
                    is_synthetic=True
                )
                for i, x in enumerate(PRODUCTS, 1)
                if f'SYN-SKU-{i:04d}' not in existing_product_skus
            ],
            ignore_conflicts=True
        )

        products = list(
            Product.objects.filter(is_synthetic=True).order_by('sku')
        )

        for i, product in enumerate(products, start=1):
            if i <= len(PRODUCTS):
                pname, pcategory, pbrand = PRODUCTS[i - 1]
                updates = []

                for field, value in [
                    ('name', pname),
                    ('category', pcategory),
                    ('brand', pbrand)
                ]:
                    if getattr(product, field) != value:
                        setattr(product, field, value)
                        updates.append(field)

                if updates:
                    product.save(update_fields=updates)

        customer_specs = [
            ('Harborline Retail Distribution Center', 'Hyderabad'),
            ('Crownfield Mobility Assembly Plant', 'Bengaluru'),
            ('Sunward Electrical Systems Warehouse', 'Chennai'),
            ('Oakwell Consumer Markets Depot', 'Pune'),
            ('Summit Industrial Supply Hub', 'Mumbai'),
            ('Deccan Medical Distribution Center', 'Hyderabad'),
            ('Western Auto Parts Warehouse', 'Pune'),
            ('Southern Electronics Fulfillment Center', 'Chennai'),
            ('Bengaluru Consumer Goods Depot', 'Bengaluru'),
            ('Delhi Industrial Supply Hub', 'Delhi'),
            ('Ahmedabad Components Warehouse', 'Ahmedabad'),
            ('Kolkata Regional Distribution Center', 'Kolkata'),
            ('Jaipur Retail Fulfillment Hub', 'Jaipur'),
            ('Visakhapatnam Portside Warehouse', 'Visakhapatnam'),
            ('Vijayawada Regional Depot', 'Vijayawada')
        ]

        customers = list(
            Customer.objects.filter(is_synthetic=True).order_by('id')
        )

        if not customers:
            Customer.objects.bulk_create(
                [
                    Customer(name=name, city=city, is_synthetic=True)
                    for name, city in customer_specs
                ]
            )
            customers = list(
                Customer.objects.filter(is_synthetic=True).order_by('id')
            )

        for i, customer in enumerate(customers[:len(customer_specs)]):
            cname, ccity = customer_specs[i]
            updates = []

            if customer.name != cname:
                customer.name = cname
                updates.append('name')

            if customer.city != ccity:
                customer.city = ccity
                updates.append('city')

            if updates:
                customer.save(update_fields=updates)

        lanes = list(
            Lane.objects.filter(is_synthetic=True).order_by('id')
        )

        if not lanes:
            Lane.objects.bulk_create(
                [
                    Lane(
                        origin=origin,
                        destination=destination,
                        distance_km=distance,
                        is_synthetic=True
                    )
                    for origin, destination, distance in LANES
                ]
            )
            lanes = list(
                Lane.objects.filter(is_synthetic=True).order_by('id')
            )

        rates = list(RateCard.objects.filter(is_synthetic=True))
        existing_pairs = {(r.carrier_id, r.lane_id) for r in rates}

        missing_rates = [
            RateCard(
                code=f'SYN-RATE-{c.pk:05d}-{lane.pk:03d}',
                carrier=c,
                lane=lane,
                service_type='Road Express',
                effective_from=date(2025, 1, 1),
                effective_to=date(2027, 12, 31),
                minimum_charge=Decimal(rng.randrange(350, 850)),
                rate_per_kg=Decimal(rng.randrange(8, 19)) + Decimal('0.50'),
                fuel_percent=Decimal(rng.randrange(8, 17)),
                dim_divisor=5000,
                currency='INR',
                is_synthetic=True
            )
            for c in carriers
            for lane in lanes
            if (c.id, lane.id) not in existing_pairs
        ]

        RateCard.objects.bulk_create(
            missing_rates,
            batch_size=1000,
            ignore_conflicts=True
        )

        rates = list(RateCard.objects.filter(is_synthetic=True))
        existing_tier_rate_ids = set(
            WeightTier.objects.filter(is_synthetic=True)
            .values_list('rate_card_id', flat=True)
        )
        tiers = []

        for rate in rates:
            if rate.id in existing_tier_rate_ids:
                continue

            tiers.extend([
                WeightTier(
                    rate_card=rate,
                    name='Light freight',
                    min_weight_kg=Decimal('0'),
                    max_weight_kg=Decimal('100'),
                    rate_per_kg=rate.rate_per_kg + Decimal('2'),
                    minimum_charge=rate.minimum_charge,
                    is_synthetic=True
                ),
                WeightTier(
                    rate_card=rate,
                    name='Standard freight',
                    min_weight_kg=Decimal('100.01'),
                    max_weight_kg=Decimal('500'),
                    rate_per_kg=rate.rate_per_kg,
                    minimum_charge=rate.minimum_charge,
                    is_synthetic=True
                ),
                WeightTier(
                    rate_card=rate,
                    name='Heavy freight',
                    min_weight_kg=Decimal('500.01'),
                    max_weight_kg=None,
                    rate_per_kg=max(Decimal('5'), rate.rate_per_kg - Decimal('1')),
                    minimum_charge=rate.minimum_charge,
                    is_synthetic=True
                )
            ])

        WeightTier.objects.bulk_create(
            tiers,
            batch_size=2000,
            ignore_conflicts=True
        )

        ServiceType.objects.get_or_create(
            code='ROAD-EXPRESS',
            defaults={
                'name': 'Road Express',
                'description': 'Standard contracted road freight service.'
            }
        )

        accessorial_specs = [
            ('REMOTE', 'Remote-area delivery',
             'Fixed charge for remote destination access.'),
            ('OVERSIZE', 'Oversize handling',
             'Handling charge for oversized cargo.'),
            ('WAITING', 'Waiting-time charge',
             'Contracted waiting-time charge.'),
            ('LIFTGATE', 'Liftgate delivery',
             'Equipment charge for delivery where a loading lift is required.'),
            ('REDELIVERY', 'Redelivery after failed attempt',
             'Charge for a documented second delivery attempt.')
        ]

        accessorials = {}

        for code, name, desc in accessorial_specs:
            obj, _ = Accessorial.objects.get_or_create(
                code=f'SYN-ACC-{code}',
                defaults={
                    'name': name,
                    'amount': Decimal('200.00'),
                    'eligible_scenario': desc,
                    'is_synthetic': True
                }
            )
            accessorials[code] = obj

        existing_rules = set(
            RateCardAccessorial.objects.filter(is_synthetic=True)
            .values_list('rate_card_id', 'accessorial_id')
        )
        rule_rows = []

        for rate in rates:
            for code, _, _ in accessorial_specs:
                accessorial = accessorials[code]

                if (rate.id, accessorial.id) in existing_rules:
                    continue

                method = 'PERCENT_BASE' if code == 'WAITING' else 'FIXED'
                amount = (
                    Decimal('5.00') if code == 'WAITING'
                    else Decimal('225.00') if code == 'REMOTE'
                    else Decimal('280.00')
                )

                rule_rows.append(
                    RateCardAccessorial(
                        rate_card=rate,
                        accessorial=accessorial,
                        charge_method=method,
                        amount=amount,
                        eligible=True,
                        is_synthetic=True
                    )
                )

        
        RateCardAccessorial.objects.bulk_create(
            rule_rows,
            batch_size=2000,
            ignore_conflicts=True
        )

        rate_map = {
            (r.carrier_id, r.lane_id): r for r in rates
        }

        rate_by_carrier = {
            c.id: [r for r in rates if r.carrier_id == c.id]
            for c in carriers
        }


        shipments = list(
            Shipment.objects.filter(is_synthetic=True).order_by('id')
        )

        if len(shipments) < nship:
            new = []
            base = date(2026, 1, 1)

            for i in range(len(shipments) + 1, nship + 1):
                carrier = rng.choice(carriers)
                lane = rng.choice(lanes)
                rate = (
                    rate_map.get((carrier.id, lane.id))
                    or rng.choice(rate_by_carrier[carrier.id])
                )
                supplier = rng.choice(suppliers)
                product = rng.choice(products)
                shipped = base + timedelta(days=rng.randrange(0, 290))
                weight = (
                    Decimal(rng.randrange(25, 1800))
                    + Decimal(rng.randrange(0, 100)) / 100
                )

                delivered = rng.random() < 0.83
                actual = (
                    shipped + timedelta(
                        days=max(
                            1,
                            round(lane.distance_km / 450)
                            + rng.randrange(0, 3)
                        )
                    )
                    if delivered else None
                )

                new.append(
                    Shipment(
                        code=f'SYN-SHP-2026-{i:06d}',
                        carrier=carrier,
                        supplier=supplier,
                        customer=rng.choice(customers),
                        product=product,
                        lane=lane,
                        rate_card=rate,
                        shipment_date=shipped,
                        expected_delivery=shipped + timedelta(
                            days=max(1, round(lane.distance_km / 450) + 1)
                        ),
                        actual_delivery=actual,
                        delivery_status='Delivered' if delivered else 'In transit',
                        service_type='Road Express',
                        quantity=rng.randrange(2, 120),
                        quantity_unit='cartons',
                        actual_weight_kg=weight,
                        created_at=timezone.make_aware(
                            timezone.datetime.combine(
                                shipped,
                                timezone.datetime.min.time()
                            )
                        ),
                        length_cm=Decimal(rng.randrange(25, 120)),
                        width_cm=Decimal(rng.randrange(20, 100)),
                        height_cm=Decimal(rng.randrange(15, 90)),
                        is_synthetic=True
                    )
                )

            Shipment.objects.bulk_create(new, batch_size=1000)
            shipments = list(
                Shipment.objects.filter(is_synthetic=True).order_by('id')
            )

        # Attach accessorials using deterministic shipment-number rules.
        existing_shipment_accessorials = set(
            ShipmentAccessorial.objects.filter(is_synthetic=True)
            .values_list('shipment_id', 'accessorial_id')
        )
        shipment_accessorial_rows = []

        for shipment in shipments:
            if not shipment.code.startswith('SYN-SHP-'):
                continue

            try:
                idx = int(shipment.code.rsplit('-', 1)[-1])
            except ValueError:
                continue

            for divisor, code in [
                (17, 'REMOTE'),
                (23, 'OVERSIZE'),
                (29, 'WAITING'),
                (31, 'LIFTGATE'),
                (37, 'REDELIVERY')
            ]:
                accessorial = accessorials[code]

                if (
                    idx % divisor == 0
                    and (shipment.id, accessorial.id)
                    not in existing_shipment_accessorials
                ):
                    shipment_accessorial_rows.append(
                        ShipmentAccessorial(
                            shipment=shipment,
                            accessorial=accessorial,
                            quantity=1,
                            evidence_reference=f'ACC-EVIDENCE-{shipment.code}',
                            notes='Synthetic scenario generated from fixed seed.',
                            is_synthetic=True
                        )
                    )

        ShipmentAccessorial.objects.bulk_create(
            shipment_accessorial_rows,
            batch_size=2000,
            ignore_conflicts=True
        )

        # Create shipment-leg, weight-measurement, and delivery records.
        existing = set(
            ShipmentLeg.objects.filter(is_synthetic=True)
            .values_list('shipment_id', flat=True)
        )

        ShipmentLeg.objects.bulk_create(
            [
                ShipmentLeg(
                    shipment=s,
                    sequence=1,
                    carrier=s.carrier,
                    origin=s.lane.origin,
                    destination=s.lane.destination,
                    departure_date=s.shipment_date,
                    arrival_date=s.actual_delivery,
                    is_synthetic=True
                )
                for s in shipments if s.id not in existing
            ],
            batch_size=1000
        )

        existing = set(
            WeightMeasurement.objects.filter(is_synthetic=True)
            .values_list('shipment_id', flat=True)
        )

        WeightMeasurement.objects.bulk_create(
            [
                WeightMeasurement(
                    shipment=s,
                    measured_weight_kg=s.actual_weight_kg,
                    measured_by='Deccan Freight Weighbridge',
                    measured_at=timezone.make_aware(
                        timezone.datetime.combine(
                            s.shipment_date,
                            timezone.datetime.min.time()
                        )
                    ),
                    evidence_reference=f'WB-{s.code}',
                    is_synthetic=True
                )
                for s in shipments if s.id not in existing
            ],
            batch_size=1000
        )

        existing = set(
            DeliveryRecord.objects.filter(is_synthetic=True)
            .values_list('shipment_id', flat=True)
        )

        DeliveryRecord.objects.bulk_create(
            [
                DeliveryRecord(
                    shipment=s,
                    status=s.delivery_status,
                    recorded_at=timezone.make_aware(
                        timezone.datetime.combine(
                            s.actual_delivery
                            or s.expected_delivery
                            or s.shipment_date,
                            timezone.datetime.min.time()
                        )
                    ),
                    proof_reference=(
                        f'POD-{s.code}' if s.actual_delivery else ''
                    ),
                    notes=(
                        'Synthetic delivery evidence.'
                        if s.actual_delivery
                        else 'Shipment remains in transit.'
                    ),
                    is_synthetic=True
                )
                for s in shipments if s.id not in existing
            ],
            batch_size=1000
        )

        # Generate freight invoices.
        invoices = list(
            FreightInvoice.objects.filter(is_synthetic=True).order_by('id')
        )

        if len(invoices) < ninv:
            existing_ships = set(
                FreightInvoice.objects.values_list('shipment_id', flat=True)
            )
            available = [
                s for s in shipments if s.id not in existing_ships
            ][:ninv - len(invoices)]

            new = []

            for idx, shipment in enumerate(
                available, start=len(invoices) + 1
            ):
                calc = calculate_for_generator(shipment)

                billed_base = calc[0]
                billed_fuel = calc[1]
                billed_access = calc[2]

                # Deterministic charge discrepancies.
                if idx % 7 == 0:
                    billed_base += (
                        Decimal('175.00') + Decimal(idx) / Decimal('100')
                    ).quantize(Decimal('.01'))
                elif idx % 11 == 0:
                    billed_fuel += (
                        Decimal('175.00') + Decimal(idx) / Decimal('100')
                    ).quantize(Decimal('.01'))
                elif idx % 13 == 0:
                    billed_access += (
                        Decimal('175.00') + Decimal(idx) / Decimal('100')
                    ).quantize(Decimal('.01'))

                total = billed_base + billed_fuel + billed_access
                billed_weight = (
                    calc[3] + Decimal('10.00')
                    if idx % 17 == 0 else calc[3]
                )

                new.append(
                    FreightInvoice(
                        code=f'SYN-FINV-2026-{idx:06d}',
                        invoice_number=f'FREIGHT-INV-2026-{idx:06d}',
                        supplier=shipment.supplier,
                        carrier=shipment.carrier,
                        shipment=shipment,
                        invoice_date=shipment.shipment_date + timedelta(days=1),
                        currency='INR',
                        billed_weight_kg=billed_weight,
                        billed_base=billed_base,
                        billed_fuel=billed_fuel,
                        billed_accessorial=billed_access,
                        billed_total=total,
                        expected_base=calc[0],
                        expected_fuel=calc[1],
                        expected_accessorial=calc[2],
                        expected_total=calc[0] + calc[1] + calc[2],
                        validation_status='PENDING',
                        status='SUBMITTED',
                        supporting_reference=f'INV-DOC-{idx:06d}.pdf',
                        submitted_at=timezone.make_aware(
                            timezone.datetime.combine(
                                shipment.shipment_date + timedelta(days=2),
                                timezone.datetime.min.time()
                            )
                        ),
                        created_at=timezone.make_aware(
                            timezone.datetime.combine(
                                shipment.shipment_date + timedelta(days=2),
                                timezone.datetime.min.time()
                            )
                        ),
                        is_synthetic=True
                    )
                )

            FreightInvoice.objects.bulk_create(new, batch_size=1000)
            invoices = list(
                FreightInvoice.objects.filter(is_synthetic=True).order_by('id')
            )

        # Validate invoices using the application's validator.
        for invoice in invoices:
            if invoice.validation_status == 'PENDING':
                validate_invoice(invoice, None)

            last_part = invoice.invoice_number.rsplit('-', 1)[-1]
            idx = int(last_part) if last_part.isdigit() else 0
            exception = invoice.exceptions.first()

            if exception and invoice.code.startswith('SYN-FINV-'):
                if idx % 7 == 0:
                    exception.issue_type = 'Incorrect billed base freight'
                elif idx % 11 == 0:
                    exception.issue_type = 'Incorrect fuel surcharge'
                elif idx % 13 == 0:
                    exception.issue_type = 'Unsupported accessorial charge'
                elif idx % 17 == 0:
                    exception.issue_type = 'Incorrect billed weight'
                else:
                    exception.issue_type = 'Contractual charge discrepancy'

                exception.save(update_fields=['issue_type'])

        # Store line-level charge details.
        existing_line_invoice_ids = set(
            InvoiceLine.objects.filter(is_synthetic=True)
            .values_list('invoice_id', flat=True)
        )
        line_rows = []

        for invoice in invoices:
            if invoice.id in existing_line_invoice_ids:
                continue

            charge_lines = [
                (
                    'Contracted base freight',
                    'BASE',
                    invoice.billed_base,
                    invoice.expected_base
                ),
                (
                    'Fuel surcharge',
                    'FUEL',
                    invoice.billed_fuel,
                    invoice.expected_fuel
                ),
                (
                    'Accessorial charges',
                    'ACCESSORIAL',
                    invoice.billed_accessorial,
                    invoice.expected_accessorial
                )
            ]

            for seq, (label, kind, billed, expected) in enumerate(
                charge_lines, 1
            ):
                line_rows.append(
                    InvoiceLine(
                        invoice=invoice,
                        code=f'{invoice.code}-L{seq:02d}',
                        description=label,
                        charge_type=kind,
                        billed_amount=billed,
                        expected_amount=expected,
                        evidence_reference=invoice.supporting_reference,
                        is_synthetic=True
                    )
                )

        InvoiceLine.objects.bulk_create(
            line_rows,
            batch_size=2000,
            ignore_conflicts=True
        )

        # Create demonstration review and approval workflows.
        cases = list(
            AuditException.objects.filter(
                invoice__is_synthetic=True,
                invoice__validation_status='OVERCHARGE',
                original_discrepancy__gt=0
            ).order_by('id')
        )

        actor = User.objects.filter(is_superuser=True).first()

        if cases and not actor:
            actor, _ = User.objects.get_or_create(
                username='freightiq_seed_actor',
                defaults={
                    'is_active': False,
                    'is_staff': False,
                    'email': 'seed-actor@invalid.example'
                }
            )

            if actor.has_usable_password():
                actor.set_unusable_password()
                actor.save(update_fields=['password'])

        for i, case in enumerate(cases[:8]):
            if case.reviews.exists():
                continue

            review = AnalystReview.objects.create(
                exception=case,
                actor=actor,
                cycle=case.current_cycle,
                findings=(
                    'Synthetic demonstration finding: billed base freight '
                    'exceeds the contract calculation. Contract, shipment '
                    'weight and invoice evidence were compared.'
                ),
                root_cause='Base freight above contracted rate',
                recommendation='CREDIT',
                recommended_amount=max(
                    Decimal('0.00'), case.original_discrepancy
                ),
                evidence_reference=case.invoice.supporting_reference,
                created_at=seeded_at(case, 1),
                is_synthetic=True
            )

            if i in [1, 2, 4, 6, 7]:
                ManagerDecision.objects.create(
                    exception=case,
                    actor=actor,
                    cycle=case.current_cycle,
                    decision='APPROVE',
                    approved_amount=review.recommended_amount,
                    comments=(
                        'Synthetic demo approval based on recorded contract '
                        'and shipment evidence.'
                    ),
                    created_at=seeded_at(case, 2),
                    is_synthetic=True
                )
                case.status = 'CARRIER_RESPONSE'

            elif i == 3:
                ManagerDecision.objects.create(
                    exception=case,
                    actor=actor,
                    cycle=case.current_cycle,
                    decision='RETURN',
                    approved_amount=review.recommended_amount,
                    comments='Synthetic demo return: attach a clearer supporting document.',
                    created_at=seeded_at(case, 2),
                    is_synthetic=True
                )
                case.status = 'RETURNED_TO_ANALYST'
                case.current_cycle = 2

            elif i == 5:
                ManagerDecision.objects.create(
                    exception=case,
                    actor=actor,
                    cycle=case.current_cycle,
                    decision='APPROVE',
                    approved_amount=review.recommended_amount,
                    comments='Synthetic demo approval for carrier response.',
                    created_at=seeded_at(case, 2),
                    is_synthetic=True
                )

                CarrierResponse.objects.create(
                    exception=case,
                    actor=actor,
                    response='DISPUTE',
                    proposed_amount=review.recommended_amount,
                    explanation=(
                        'Synthetic demo carrier dispute requesting evidence '
                        'of the billed weight.'
                    ),
                    created_at=seeded_at(case, 3),
                    is_synthetic=True
                )
                case.status = 'CARRIER_DISPUTED'
                case.current_cycle = 2

            else:
                case.status = 'MANAGER_REVIEW'

            case.save(update_fields=['status', 'current_cycle', 'updated_at'])

        # Seed finance and re-verification examples.
        staged = cases[8:15]

        for offset, case in enumerate(staged):
            if case.reviews.exists():
                continue

            review = AnalystReview.objects.create(
                exception=case,
                actor=actor,
                cycle=case.current_cycle,
                findings=(
                    'Synthetic case review: compare the invoice line, '
                    'rate-card terms and shipment evidence. The billed '
                    'component exceeds the contract-derived value.'
                ),
                root_cause=case.issue_type,
                recommendation='CREDIT',
                recommended_amount=max(
                    Decimal('0.00'), case.original_discrepancy
                ),
                evidence_reference=case.invoice.supporting_reference,
                created_at=seeded_at(case, 1),
                is_synthetic=True
            )

            if offset in [0, 1, 2, 3, 4]:
                ManagerDecision.objects.create(
                    exception=case,
                    actor=actor,
                    cycle=case.current_cycle,
                    decision='APPROVE',
                    approved_amount=review.recommended_amount,
                    comments='Synthetic demonstration approval after evidence review.',
                    created_at=seeded_at(case, 2),
                    is_synthetic=True
                )

            if offset in [0, 1, 2, 3]:
                CarrierResponse.objects.create(
                    exception=case,
                    actor=actor,
                    response='ACCEPT',
                    proposed_amount=review.recommended_amount,
                    explanation='Synthetic carrier acceptance for demonstration.',
                    created_at=seeded_at(case, 3),
                    is_synthetic=True
                )
                case.status = 'CARRIER_ACCEPTED'

            if offset == 1:
                note = CreditNote.objects.create(
                    code=f'SYN-CN-{case.pk:06d}',
                    external_identifier=f'SYN-EXT-CN-{case.pk:06d}',
                    exception=case,
                    invoice=case.invoice,
                    carrier=case.invoice.carrier,
                    issued_amount=review.recommended_amount,
                    currency=case.invoice.currency,
                    issue_date=case.invoice.submitted_at.date() + timedelta(days=5),
                    document_reference=f'SYN-CN-DOC-{case.pk:06d}',
                    verification_status='PENDING',
                    created_at=seeded_at(case, 5),
                    is_synthetic=True
                )
                case.status = 'FINANCE_RECONCILIATION'

            elif offset == 2:
                note = CreditNote.objects.create(
                    code=f'SYN-CN-{case.pk:06d}',
                    external_identifier=f'SYN-EXT-CN-{case.pk:06d}',
                    exception=case,
                    invoice=case.invoice,
                    carrier=case.invoice.carrier,
                    issued_amount=review.recommended_amount,
                    currency=case.invoice.currency,
                    issue_date=case.invoice.submitted_at.date() + timedelta(days=5),
                    document_reference=f'SYN-CN-DOC-{case.pk:06d}',
                    verification_status='VERIFIED',
                    verification_comments=(
                        'Synthetic note verified against approved and agreed amounts.'
                    ),
                    verified_by=actor,
                    verified_at=seeded_at(case, 7),
                    created_at=seeded_at(case, 5),
                    is_synthetic=True
                )

                partial = (
                    review.recommended_amount / Decimal('2')
                ).quantize(Decimal('.01'))

                if partial > 0:
                    application = CreditApplication.objects.create(
                        credit_note=note,
                        invoice=case.invoice,
                        actor=actor,
                        amount=partial,
                        reference=f'SYN-APP-{case.pk:06d}',
                        created_at=seeded_at(case, 8),
                        is_synthetic=True
                    )

                    InvoiceAdjustment.objects.create(
                        application=application,
                        invoice=case.invoice,
                        amount=partial,
                        created_at=seeded_at(case, 8),
                        is_synthetic=True
                    )

                case.status = 'FINANCE_RECONCILIATION'

            elif offset == 3:
                note = CreditNote.objects.create(
                    code=f'SYN-CN-{case.pk:06d}',
                    external_identifier=f'SYN-EXT-CN-{case.pk:06d}',
                    exception=case,
                    invoice=case.invoice,
                    carrier=case.invoice.carrier,
                    issued_amount=review.recommended_amount,
                    currency=case.invoice.currency,
                    issue_date=case.invoice.submitted_at.date() + timedelta(days=5),
                    document_reference=f'SYN-CN-DOC-{case.pk:06d}',
                    verification_status='VERIFIED',
                    verification_comments='Synthetic note verified.',
                    verified_by=actor,
                    verified_at=seeded_at(case, 7),
                    created_at=seeded_at(case, 5),
                    is_synthetic=True
                )

                if review.recommended_amount > 0:
                    application = CreditApplication.objects.create(
                        credit_note=note,
                        invoice=case.invoice,
                        actor=actor,
                        amount=review.recommended_amount,
                        reference=f'SYN-APP-{case.pk:06d}',
                        created_at=seeded_at(case, 8),
                        is_synthetic=True
                    )

                    InvoiceAdjustment.objects.create(
                        application=application,
                        invoice=case.invoice,
                        amount=review.recommended_amount,
                        created_at=seeded_at(case, 8),
                        is_synthetic=True
                    )

                case.status = 'RECONCILED'

                ReconciliationRecord.objects.create(
                    exception=case,
                    actor=actor,
                    approved_amount=review.recommended_amount,
                    agreed_amount=review.recommended_amount,
                    issued_amount=review.recommended_amount,
                    verified_amount=review.recommended_amount,
                    applied_amount=review.recommended_amount,
                    remaining_amount=Decimal('0'),
                    difference=Decimal('0'),
                    status='RECONCILED',
                    created_at=seeded_at(case, 9),
                    is_synthetic=True
                )

            elif offset == 4:
                CarrierResponse.objects.filter(
                    exception=case,
                    is_synthetic=True
                ).delete()

                CarrierResponse.objects.create(
                    exception=case,
                    actor=actor,
                    response='COUNTEROFFER',
                    proposed_amount=(
                        review.recommended_amount * Decimal('0.75')
                    ).quantize(Decimal('.01')),
                    explanation=(
                        'Synthetic counteroffer: carrier requests a partial '
                        'adjustment supported by its charge review.'
                    ),
                    created_at=seeded_at(case, 3),
                    is_synthetic=True
                )

                case.status = 'CARRIER_COUNTEROFFER'
                case.current_cycle += 1

            elif offset == 5:
                ManagerDecision.objects.create(
                    exception=case,
                    actor=actor,
                    cycle=case.current_cycle,
                    decision='RETURN',
                    approved_amount=review.recommended_amount,
                    comments=(
                        'Synthetic return: attach clearer shipment weight '
                        'evidence before approval.'
                    ),
                    created_at=seeded_at(case, 2),
                    is_synthetic=True
                )

                case.current_cycle += 1

                AnalystReview.objects.create(
                    exception=case,
                    actor=actor,
                    cycle=case.current_cycle,
                    findings=(
                        'Re-verification completed: shipment measurement '
                        'evidence is now attached and the contractual '
                        'overcharge remains supported.'
                    ),
                    root_cause=case.issue_type,
                    recommendation='CREDIT',
                    recommended_amount=max(
                        Decimal('0.00'), case.original_discrepancy
                    ),
                    evidence_reference=case.invoice.supporting_reference,
                    created_at=seeded_at(case, 3),
                    is_synthetic=True
                )

                case.status = 'MANAGER_REVERIFY'

            elif offset == 6:
                ManagerDecision.objects.create(
                    exception=case,
                    actor=actor,
                    cycle=case.current_cycle,
                    decision='REJECT',
                    approved_amount=Decimal('0'),
                    comments=(
                        'Synthetic rejection: evidence does not establish '
                        'a recoverable overcharge.'
                    ),
                    created_at=seeded_at(case, 2),
                    is_synthetic=True
                )

                case.status = 'REJECTED'

            case.save(update_fields=['status', 'current_cycle', 'updated_at'])

        self.stdout.write(
            self.style.SUCCESS(
                f'Generated/reused deterministic synthetic data '
                f'(seed={o["seed"]}): '
                f'carriers={Carrier.objects.filter(is_synthetic=True).count()}, '
                f'shipments={Shipment.objects.filter(is_synthetic=True).count()}, '
                f'invoices={FreightInvoice.objects.filter(is_synthetic=True).count()}, '
                f'exceptions={AuditException.objects.filter(invoice__is_synthetic=True).count()}'
            )
        )


def seeded_at(case, days=0, hours=0):
    base = case.invoice.submitted_at.date() + timedelta(days=days)

    return timezone.make_aware(
        timezone.datetime.combine(
            base,
            timezone.datetime.min.time()
        ) + timedelta(hours=hours)
    )


def calculate_for_generator(shipment):
    from audit.services.freight_calculator import calculate_expected

    calculated = calculate_expected(shipment)

    return (
        calculated['base'],
        calculated['fuel'],
        calculated['accessorial'],
        calculated['billable_weight']
    )