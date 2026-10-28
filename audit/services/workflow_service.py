from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError
from audit.models import AnalystReview, ManagerDecision, CarrierResponse, AuditEvent
@transaction.atomic
def analyst_submit(case,user,findings,root_cause,recommendation,amount,evidence=''):
    if user.profile.approved_role!='ANALYST': raise PermissionDenied('Only a Logistics Analyst may submit findings.')
    if recommendation not in ['CREDIT','NO_CREDIT','INFO']: raise ValidationError('Select a valid recommendation.')
    if not findings.strip() or not root_cause.strip(): raise ValidationError('Findings and root cause are required.')
    if recommendation=='CREDIT' and not evidence.strip(): raise ValidationError('Supporting evidence reference is required for a credit recommendation.')
    if case.status not in ['NEW','RETURNED_TO_ANALYST','CARRIER_DISPUTED','CARRIER_COUNTEROFFER','REVERIFY']:
        raise ValidationError('This case is not in an analyst-editable state.')
    try: amount=Decimal(amount)
    except (InvalidOperation,TypeError): raise ValidationError('Enter a valid recommended amount.')
    if recommendation in ['NO_CREDIT','INFO'] and amount!=0: raise ValidationError('No-credit and additional-information recommendations must have a zero amount.')
    if amount<0 or amount>max(case.original_discrepancy,Decimal('0')): raise ValidationError('Recommended credit must be between zero and the positive overcharge.')
    review=AnalystReview.objects.create(exception=case,actor=user,cycle=case.current_cycle,findings=findings,root_cause=root_cause,recommendation=recommendation,recommended_amount=amount,evidence_reference=evidence)
    case.status='MANAGER_REVERIFY' if case.current_cycle>1 else 'MANAGER_REVIEW'; case.save(update_fields=['status','updated_at'])
    AuditEvent.objects.create(actor=user,entity_type='AuditException',entity_id=case.code,action='Analyst recommendation submitted',previous_state='ANALYST_REVIEW',new_state=case.status,details=findings,amount=amount,cycle=case.current_cycle,is_synthetic=case.is_synthetic)
    return review
@transaction.atomic
def manager_decide(case,user,decision,comments,amount=None):
    if user.profile.approved_role!='MANAGER': raise PermissionDenied('Only an Operations Manager may decide this case.')
    if decision not in ['APPROVE','REJECT','RETURN']: raise ValidationError('Select a valid manager decision.')
    if not comments.strip(): raise ValidationError('A decision justification is mandatory.')
    if case.status not in ['MANAGER_REVIEW','MANAGER_REVERIFY']: raise ValidationError('Case is not awaiting manager review.')
    review=case.reviews.order_by('-created_at').first()
    try: approved=Decimal(amount if amount not in (None,'') else (review.recommended_amount if review else 0))
    except (InvalidOperation,TypeError): raise ValidationError('Enter a valid approved amount.')
    if review and review.recommendation=='INFO' and decision=='APPROVE': raise ValidationError('The analyst requested additional information; return or reject this case before approval.')
    if review and review.recommendation=='NO_CREDIT' and decision=='APPROVE' and approved!=0: raise ValidationError('A no-credit recommendation cannot be approved for a positive amount.')
    if approved<0 or approved>max(case.original_discrepancy,Decimal('0')): raise ValidationError('Invalid approved amount.')
    ManagerDecision.objects.create(exception=case,actor=user,cycle=case.current_cycle,decision=decision,approved_amount=approved,comments=comments)
    old=case.status
    case.status={'APPROVE':'CARRIER_RESPONSE','REJECT':'REJECTED','RETURN':'RETURNED_TO_ANALYST'}[decision]
    if decision=='RETURN': case.current_cycle+=1
    case.save(update_fields=['status','current_cycle','updated_at'])
    AuditEvent.objects.create(actor=user,entity_type='AuditException',entity_id=case.code,action=f'Manager {decision.lower()}',previous_state=old,new_state=case.status,details=comments,amount=approved,cycle=case.current_cycle-(1 if decision=='RETURN' else 0),is_synthetic=case.is_synthetic)
@transaction.atomic
def carrier_respond(case,user,response,explanation,amount=None):
    if user.profile.approved_role!='CARRIER': raise PermissionDenied('Only an approved carrier operator may respond.')
    if response not in ['ACCEPT','DISPUTE','COUNTEROFFER']: raise ValidationError('Select a valid carrier response.')
    if case.invoice.carrier_id != user.profile.carrier_id: raise PermissionDenied('This case belongs to another carrier.')
    if case.status!='CARRIER_RESPONSE': raise ValidationError('This case is not awaiting a carrier response.')
    if response in ['DISPUTE','COUNTEROFFER'] and not explanation.strip(): raise ValidationError('An explanation is mandatory.')
    decision=case.decisions.filter(decision='APPROVE').order_by('-created_at').first()
    if response=='COUNTEROFFER' and amount in (None,''): raise ValidationError('A counteroffer amount is required.')
    try: proposed=Decimal(amount) if amount not in (None,'') else (decision.approved_amount if decision else Decimal('0'))
    except (InvalidOperation,TypeError): raise ValidationError('Enter a valid carrier amount.')
    if proposed<0 or proposed>max(case.original_discrepancy,Decimal('0')): raise ValidationError('Invalid counteroffer amount.')
    CarrierResponse.objects.create(exception=case,actor=user,response=response,proposed_amount=proposed,explanation=explanation)
    old=case.status
    if response=='ACCEPT': case.status='CARRIER_ACCEPTED'
    else: case.status='CARRIER_DISPUTED' if response=='DISPUTE' else 'CARRIER_COUNTEROFFER'; case.current_cycle+=1
    case.save(update_fields=['status','current_cycle','updated_at'])
    AuditEvent.objects.create(actor=user,entity_type='AuditException',entity_id=case.code,action=f'Carrier {response.lower()}',previous_state=old,new_state=case.status,details=explanation,amount=proposed,cycle=case.current_cycle,is_synthetic=case.is_synthetic)
