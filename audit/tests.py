
from datetime import date
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied

from audit.models import *
from audit.services.freight_calculator import calculate_expected
from audit.services.invoice_validator import validate_invoice
from audit.services.workflow_service import (
    analyst_submit,
    manager_decide,
    carrier_respond,
)
from audit.services.credit_service import verify_credit, apply_credit


class FreightFixture(TestCase):
    def setUp(self):
        self.carrier = Carrier.objects.create(
            code='CAR-T1',
            name='BluePeak Freight Network',
        )
        self.supplier = Supplier.objects.create(
            code='SUP-T1',
            name='Asteron Industrial Components',
        )
        self.product = Product.objects.create(
            sku='SKU-T1',
            name='Brake assemblies',
            category='Automotive components',
        )
        self.lane = Lane.objects.create(
            origin='Hyderabad',
            destination='Bengaluru',
            distance_km=570,
        )
        self.rate = RateCard.objects.create(
            code='RATE-T1',
            carrier=self.carrier,
            lane=self.lane,
            effective_from=date(2025, 1, 1),
            effective_to=date(2027, 12, 31),
            minimum_charge=Decimal('500'),
            rate_per_kg=Decimal('10'),
            fuel_percent=Decimal('10'),
        )
        self.shipment = Shipment.objects.create(
            code='SHP-T1',
            carrier=self.carrier,
            supplier=self.supplier,
            product=self.product,
            lane=self.lane,
            rate_card=self.rate,
            shipment_date=date(2026, 10, 1),
            actual_weight_kg=Decimal('100'),
            length_cm=Decimal('10'),
            width_cm=Decimal('10'),
            height_cm=Decimal('10'),
        )

        self.analyst = User.objects.create_user(
            'analyst-test',
            password='AsecurePass!234',
        )
        UserProfile.objects.create(
            user=self.analyst,
            full_name='Riya Analyst',
            requested_role='ANALYST',
            approved_role='ANALYST',
            status='APPROVED',
        )

        self.manager = User.objects.create_user(
            'manager-test',
            password='AsecurePass!234',
        )
        UserProfile.objects.create(
            user=self.manager,
            full_name='Arjun Manager',
            requested_role='MANAGER',
            approved_role='MANAGER',
            status='APPROVED',
        )

        self.carrier_user = User.objects.create_user(
            'carrier-test',
            password='AsecurePass!234',
        )
        UserProfile.objects.create(
            user=self.carrier_user,
            full_name='Kiran Carrier',
            requested_role='CARRIER',
            approved_role='CARRIER',
            organization_name=self.carrier.name,
            carrier=self.carrier,
            status='APPROVED',
        )

        self.finance = User.objects.create_user(
            'finance-test',
            password='AsecurePass!234',
        )
        UserProfile.objects.create(
            user=self.finance,
            full_name='Maya Finance',
            requested_role='FINANCE',
            approved_role='FINANCE',
            status='APPROVED',
        )

    def make_invoice(self, extra=Decimal('200')):
        calc = calculate_expected(self.shipment)

        return FreightInvoice.objects.create(
            code='FINV-T1',
            invoice_number='INV-T1',
            supplier=self.supplier,
            carrier=self.carrier,
            shipment=self.shipment,
            invoice_date=date(2026, 10, 2),
            billed_base=calc['base'] + extra,
            billed_fuel=calc['fuel'],
            billed_total=calc['base'] + extra + calc['fuel'],
            expected_base=calc['base'],
            expected_fuel=calc['fuel'],
            expected_total=calc['total'],
            supporting_reference='POD-T1',
        )


class FreightCalculationTests(FreightFixture):
    def test_dimensional_weight_and_expected_total(self):
        calc = calculate_expected(self.shipment)

        self.assertEqual(calc['base'], Decimal('1000.00'))
        self.assertEqual(calc['fuel'], Decimal('100.00'))
        self.assertEqual(calc['total'], Decimal('1100.00'))

    def test_invoice_validation_creates_one_exception(self):
        invoice = self.make_invoice()

        validate_invoice(invoice, self.analyst)
        validate_invoice(invoice, self.analyst)

        self.assertEqual(invoice.exceptions.count(), 1)
        self.assertEqual(
            invoice.exceptions.first().original_discrepancy,
            Decimal('200.00'),
        )

    def test_expired_rate_card_is_rejected(self):
        self.rate.effective_to = date(2026, 9, 1)
        self.rate.save()

        with self.assertRaises(ValidationError):
            calculate_expected(self.shipment)

    def test_incorrect_billed_weight_is_a_validation_failure(self):
        invoice = self.make_invoice(extra=Decimal('0'))
        invoice.billed_weight_kg = Decimal('120.00')
        invoice.declared_total = invoice.billed_total
        invoice.save()

        validate_invoice(invoice, self.analyst)
        invoice.refresh_from_db()

        self.assertEqual(
            invoice.validation_status,
            'VALIDATION_FAILURE',
        )

        self.assertTrue(
            any(
                'Billed weight' in finding
                for finding in invoice.validation_findings
            ),
            msg=(
                'Expected billed-weight finding, got: '
                f'{invoice.validation_findings}'
            ),
        )

        self.assertEqual(invoice.exceptions.count(), 1)


class WorkflowTests(FreightFixture):
    def setUp(self):
        super().setUp()

        self.invoice = self.make_invoice()
        validate_invoice(self.invoice, self.analyst)
        self.case = self.invoice.exceptions.first()

    def test_analyst_cannot_make_manager_decision(self):
        with self.assertRaises(PermissionDenied):
            manager_decide(
                self.case,
                self.analyst,
                'APPROVE',
                'ok',
                '200',
            )

    def test_manager_requires_reason_for_rejection(self):
        analyst_submit(
            self.case,
            self.analyst,
            'Rate exceeds contract',
            'Base freight',
            'CREDIT',
            '200',
            'POD-T1',
        )

        with self.assertRaises(ValidationError):
            manager_decide(
                self.case,
                self.manager,
                'REJECT',
                '',
                '0',
            )

    def test_full_approval_and_carrier_acceptance(self):
        analyst_submit(
            self.case,
            self.analyst,
            'Rate exceeds contract',
            'Base freight',
            'CREDIT',
            '200',
            'POD-T1',
        )

        manager_decide(
            self.case,
            self.manager,
            'APPROVE',
            'Contract evidence verified',
            '200',
        )

        carrier_respond(
            self.case,
            self.carrier_user,
            'ACCEPT',
            'We accept the approved amount.',
            '200',
        )

        self.case.refresh_from_db()
        self.assertEqual(self.case.status, 'CARRIER_ACCEPTED')

    def test_carrier_cannot_access_other_carrier_case(self):
        other = Carrier.objects.create(
            code='CAR-T2',
            name='Meridian Transit Services',
        )

        profile = self.carrier_user.profile
        profile.carrier = other
        profile.save()

        with self.assertRaises(PermissionDenied):
            carrier_respond(
                self.case,
                self.carrier_user,
                'ACCEPT',
                'Accept',
                '200',
            )


class AuthenticationTests(TestCase):
    def test_registration_does_not_allow_admin_role(self):
        response = self.client.get(reverse('register'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            'System Administrator</option>',
        )

    def test_pending_user_cannot_access_dashboard(self):
        user = User.objects.create_user(
            'pending-test',
            password='AsecurePass!234',
        )

        UserProfile.objects.create(
            user=user,
            full_name='Pending User',
            requested_role='ANALYST',
            status='PENDING',
        )

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('waiting_for_approval'),
        )

    def test_logout_requires_post_and_clears_session(self):
        user = User.objects.create_user(
            'logout-test',
            password='AsecurePass!234',
        )

        UserProfile.objects.create(
            user=user,
            full_name='Logout User',
            requested_role='ANALYST',
            approved_role='ANALYST',
            status='APPROVED',
        )

        self.client.force_login(user)
        response = self.client.post(reverse('logout'))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(
            self.client.get(reverse('dashboard')).status_code,
            302,
        )


class FinanceTests(FreightFixture):
    def setUp(self):
        super().setUp()

        self.invoice = self.make_invoice()
        validate_invoice(self.invoice, self.analyst)
        self.case = self.invoice.exceptions.first()

        analyst_submit(
            self.case,
            self.analyst,
            'Contract rate mismatch',
            'Base freight',
            'CREDIT',
            '200',
            'POD-T1',
        )

        manager_decide(
            self.case,
            self.manager,
            'APPROVE',
            'Rate-card evidence supports the adjustment.',
            '200',
        )

        carrier_respond(
            self.case,
            self.carrier_user,
            'ACCEPT',
            'We accept the approved amount.',
            '200',
        )

        self.note = CreditNote.objects.create(
            code='CN-T1',
            exception=self.case,
            invoice=self.invoice,
            carrier=self.carrier,
            issued_amount=Decimal('200.00'),
            currency='INR',
            issue_date=date(2026, 10, 20),
            document_reference='CN-DOC-T1',
        )

    def test_verified_credit_can_be_partially_applied(self):
        verify_credit(
            self.note,
            self.finance,
            True,
            'Invoice, currency and accepted amount checked.',
        )

        app = apply_credit(
            self.note,
            self.finance,
            '75.00',
            'APP-UNIQUE-T1',
        )

        self.note.refresh_from_db()

        self.assertEqual(
            self.note.applied_amount,
            Decimal('75.00'),
        )
        self.assertEqual(
            self.note.remaining_amount,
            Decimal('125.00'),
        )
        self.assertEqual(
            app.adjustment.amount,
            Decimal('75.00'),
        )

    def test_duplicate_application_reference_is_rejected(self):
        verify_credit(
            self.note,
            self.finance,
            True,
            'Verified.',
        )

        apply_credit(
            self.note,
            self.finance,
            '50.00',
            'APP-DUPLICATE-T1',
        )

        with self.assertRaises(ValidationError):
            apply_credit(
                self.note,
                self.finance,
                '50.00',
                'APP-DUPLICATE-T1',
            )

    def test_unverified_credit_cannot_be_applied(self):
        with self.assertRaises(ValidationError):
            apply_credit(
                self.note,
                self.finance,
                '10.00',
                'APP-PENDING-T1',
            )
