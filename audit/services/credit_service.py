
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from audit.models import (
    CreditNote,
    CreditApplication,
    InvoiceAdjustment,
    ReconciliationRecord,
    AuditEvent,
)


def _require_finance(user):
    if user.is_superuser:
        return

    profile = getattr(user, 'profile', None)

    if not profile or profile.approved_role != 'FINANCE':
        raise PermissionDenied('Finance role required.')


@transaction.atomic
def verify_credit(note, user, approved, comments=''):
    _require_finance(user)

    note = (
        CreditNote.objects
        .select_for_update()
        .select_related('exception', 'invoice')
        .get(pk=note.pk)
    )

    decision = (
        note.exception.decisions
        .filter(decision='APPROVE')
        .order_by('-created_at')
        .first()
    )

    response = (
        note.exception.carrier_responses
        .filter(response='ACCEPT')
        .order_by('-created_at')
        .first()
    )

    agreed_amount = (
        response.proposed_amount
        if response and response.proposed_amount is not None
        else decision.approved_amount if decision else Decimal('0.00')
    )

    eligible = bool(
        decision
        and response
        and approved
        and note.issued_amount <= min(
            decision.approved_amount,
            agreed_amount,
        )
        and note.currency == note.invoice.currency
    )

    note.verification_status = (
        'VERIFIED' if eligible else 'MISMATCH'
    )

    note.verification_comments = comments or (
        'Verified against approved and agreed amount.'
        if eligible
        else 'Amount, currency, approval or carrier agreement mismatch.'
    )

    note.verified_by = user
    note.verified_at = timezone.now()

    note.save(update_fields=[
        'verification_status',
        'verification_comments',
        'verified_by',
        'verified_at',
    ])

    AuditEvent.objects.create(
        actor=user,
        entity_type='CreditNote',
        entity_id=note.code,
        action='Credit note verified',
        new_state=note.verification_status,
        details=note.verification_comments,
        amount=note.issued_amount,
        is_synthetic=note.is_synthetic,
    )

    return note


@transaction.atomic
def apply_credit(note, user, amount, reference='', target_invoice=None):
    _require_finance(user)

    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError('Enter a valid application amount.')

    if not amount.is_finite() or amount <= 0:
        raise ValidationError('Application amount must be positive.')

    reference = (reference or '').strip()

    if not reference:
        raise ValidationError(
            'A unique application reference is required.'
        )

    note = (
        CreditNote.objects
        .select_for_update()
        .select_related('invoice')
        .get(pk=note.pk)
    )

    if note.verification_status != 'VERIFIED':
        raise ValidationError(
            'Only verified credit notes can be applied.'
        )

    target_invoice = target_invoice or note.invoice

    if target_invoice.carrier_id != note.carrier_id:
        raise ValidationError(
            'Credit can only be applied to an invoice for the same carrier.'
        )

    if target_invoice.currency != note.currency:
        raise ValidationError(
            'Credit and target invoice currencies must match.'
        )

    if CreditApplication.objects.filter(
        credit_note=note,
        reference=reference,
    ).exists():
        raise ValidationError(
            'This application reference has already been used '
            'for the credit note.'
        )

    available = note.remaining_amount

    if amount > available:
        raise ValidationError(
            f'Application exceeds available balance ₹{available}.'
        )

    application = CreditApplication.objects.create(
        credit_note=note,
        invoice=target_invoice,
        actor=user,
        amount=amount,
        reference=reference,
        is_synthetic=note.is_synthetic,
    )

    InvoiceAdjustment.objects.create(
        application=application,
        invoice=target_invoice,
        amount=amount,
        is_synthetic=note.is_synthetic,
    )

    AuditEvent.objects.create(
        actor=user,
        entity_type='CreditNote',
        entity_id=note.code,
        action='Credit applied',
        amount=amount,
        details=f'Applied to {target_invoice.code}',
        is_synthetic=note.is_synthetic,
    )

    return application


@transaction.atomic
def reconcile(case, user):
    _require_finance(user)

    case = (
        type(case).objects
        .select_for_update()
        .get(pk=case.pk)
    )

    eligible_statuses = {
        'CARRIER_ACCEPTED',
        'FINANCE_RECONCILIATION',
        'RECONCILED',
    }

    if case.status not in eligible_statuses:
        raise ValidationError(
            'This case is not eligible for finance reconciliation.'
        )

    decision = (
        case.decisions
        .filter(decision='APPROVE')
        .order_by('-created_at')
        .first()
    )

    response = (
        case.carrier_responses
        .filter(response='ACCEPT')
        .order_by('-created_at')
        .first()
    )

    notes = list(case.credit_notes.all())

    approved = (
        decision.approved_amount
        if decision
        else Decimal('0.00')
    )

    agreed = (
        response.proposed_amount
        if response and response.proposed_amount is not None
        else Decimal('0.00')
    )

    issued = sum(
        (note.issued_amount for note in notes),
        Decimal('0.00'),
    )

    verified = sum(
        (
            note.issued_amount
            for note in notes
            if note.verification_status == 'VERIFIED'
        ),
        Decimal('0.00'),
    )

    applied = sum(
        (note.applied_amount for note in notes),
        Decimal('0.00'),
    )

    remaining = sum(
        (
            note.remaining_amount
            for note in notes
            if note.verification_status == 'VERIFIED'
        ),
        Decimal('0.00'),
    )

    difference = approved - issued

    has_invalid_applied_credit = any(
        note.verification_status != 'VERIFIED'
        and note.applied_amount > 0
        for note in notes
    )

    status = (
        'RECONCILED'
        if (
            decision is not None
            and response is not None
            and difference == 0
            and approved == agreed
            and issued == verified
            and verified == applied
            and remaining == 0
            and not has_invalid_applied_credit
        )
        else 'DISCREPANCY'
    )

    # Compare the current financial snapshot with the latest record.
    # If nothing has changed, reuse the existing record.
    existing = (
        ReconciliationRecord.objects
        .filter(exception=case)
        .order_by('-created_at', '-id')
        .first()
    )

    if existing:
        same_snapshot = (
            existing.approved_amount == approved
            and existing.agreed_amount == agreed
            and existing.issued_amount == issued
            and existing.verified_amount == verified
            and existing.applied_amount == applied
            and existing.remaining_amount == remaining
            and existing.difference == difference
            and existing.status == status
        )

        if same_snapshot:
            desired_case_status = (
                'RECONCILED'
                if status == 'RECONCILED'
                else 'FINANCE_RECONCILIATION'
            )

            if case.status != desired_case_status:
                case.status = desired_case_status
                case.save(update_fields=['status', 'updated_at'])

            return existing

    # Create a new record only when the snapshot or result has changed.
    rec = ReconciliationRecord.objects.create(
        exception=case,
        actor=user,
        approved_amount=approved,
        agreed_amount=agreed,
        issued_amount=issued,
        verified_amount=verified,
        applied_amount=applied,
        remaining_amount=remaining,
        difference=difference,
        status=status,
        is_synthetic=case.is_synthetic,
    )

    case.status = (
        'RECONCILED'
        if status == 'RECONCILED'
        else 'FINANCE_RECONCILIATION'
    )

    case.save(update_fields=['status', 'updated_at'])

    AuditEvent.objects.create(
        actor=user,
        entity_type='AuditException',
        entity_id=case.code,
        action='Reconciliation completed',
        new_state=status,
        details=(
            f'Approved ₹{approved}; '
            f'agreed ₹{agreed}; '
            f'issued ₹{issued}; '
            f'verified ₹{verified}; '
            f'applied ₹{applied}; '
            f'remaining ₹{remaining}; '
            f'difference ₹{difference}'
        ),
        amount=difference,
        is_synthetic=case.is_synthetic,
    )

    return rec


@transaction.atomic
def reverse_application(application, user, reason):
    _require_finance(user)

    reason = (reason or '').strip()

    if not reason:
        raise ValidationError(
            'A reversal reason is mandatory.'
        )

    application = (
        CreditApplication.objects
        .select_for_update()
        .select_related('credit_note')
        .get(pk=application.pk)
    )

    if application.reversed_at:
        raise ValidationError(
            'This credit application has already been reversed.'
        )

    application.reversed_at = timezone.now()
    application.reversal_reason = reason

    application.save(update_fields=[
        'reversed_at',
        'reversal_reason',
    ])

    adjustment = (
        InvoiceAdjustment.objects
        .select_for_update()
        .get(application=application)
    )

    adjustment.reversed_at = application.reversed_at
    adjustment.reversal_reason = reason

    adjustment.save(update_fields=[
        'reversed_at',
        'reversal_reason',
    ])

    AuditEvent.objects.create(
        actor=user,
        entity_type='CreditApplication',
        entity_id=str(application.pk),
        action='Credit application reversed',
        previous_state='APPLIED',
        new_state='REVERSED',
        details=reason,
        amount=application.amount,
        is_synthetic=application.is_synthetic,
    )

    return application
