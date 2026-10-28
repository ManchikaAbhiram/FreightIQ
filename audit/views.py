from decimal import Decimal, InvalidOperation
from datetime import date
import csv
import uuid
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from audit.models import (UserProfile,ROLE_RESPONSIBILITIES,Carrier,Supplier,Shipment,FreightInvoice,InvoiceLine,AuditException,AuditEvent,AnalystReview,ManagerDecision,CarrierResponse,CreditNote,CreditApplication,ReconciliationRecord)
from audit.forms import RegistrationForm,ShipmentForm,InvoiceForm
from audit.services.invoice_validator import validate_invoice
from audit.services.workflow_service import analyst_submit,manager_decide,carrier_respond
from audit.services.credit_service import verify_credit,apply_credit,reconcile,reverse_application


@never_cache
def home(request):
    return redirect('login')
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('dashboard')

        profile = UserProfile.objects.filter(
            user=request.user
        ).first()

        if profile and profile.status == 'APPROVED':
            return redirect('dashboard')

        if profile and profile.status == 'PENDING':
            return redirect('waiting_for_approval')

        messages.info(
            request,
            'Your account does not currently have approved access. '
            'Please contact the system administrator.'
        )
        logout(request)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is None:
            messages.error(
                request,
                'Incorrect username or password.'
            )
        elif not user.is_superuser:
            profile = UserProfile.objects.filter(
                user=user
            ).first()

            if not profile or profile.status != 'APPROVED':
                if profile and profile.status == 'PENDING':
                    message = (
                        'Your registration is pending administrator approval.'
                    )
                elif profile and profile.status == 'REJECTED':
                    message = (
                        'Your registration was rejected. '
                        'Please contact the administrator.'
                    )
                else:
                    message = (
                        'Your account profile was not found. '
                        'Please contact the administrator.'
                    )

                messages.error(request, message)

            else:
                login(request, user)
                return redirect('dashboard')

        else:
            login(request, user)
            return redirect('dashboard')

    response = render(request, 'registration/login.html')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
@never_cache
def logout_view(request):
    if request.method!='POST': return HttpResponseForbidden('Logout requires a CSRF-protected POST request.')
    logout(request); messages.success(request,'You have been logged out successfully.'); return redirect('login')
def register(request):
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            UserProfile.objects.create(
                user=user,
                full_name=form.cleaned_data['full_name'],
                requested_role=form.cleaned_data['requested_role'],
                organization_name=form.cleaned_data['organization_name'].strip(),
                status='PENDING',
            )
            AuditEvent.objects.create(
                actor=user,
                entity_type='Registration',
                entity_id=user.username,
                action='Registration submitted',
                new_state='PENDING',
                details=(
                    f"Requested role: {form.cleaned_data['requested_role']}; "
                    f"organization: {form.cleaned_data['organization_name'].strip()}"
                ),
            )
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('waiting_for_approval')
    return render(
        request,
        'registration/register.html',
        {'form': form, 'responsibilities': ROLE_RESPONSIBILITIES},
    )



@login_required
def waiting_for_approval(request):
    """Show the access-review status page."""
    profile = UserProfile.objects.filter(
        user=request.user
    ).first()

    if profile and profile.status == 'APPROVED':
        return redirect('dashboard')

    if profile and profile.status == 'REJECTED':
        return render(
            request,
            'registration/registration_rejected.html',
        )

    return render(
        request,
        'registration/waiting_for_approval.html',
    )

def get_role(user):
    if user.is_superuser: return 'ADMIN'
    try: return user.profile.approved_role or user.profile.requested_role
    except UserProfile.DoesNotExist: return ''
def admin_required(user): return user.is_superuser
def role_required(*roles):
    def decorator(view):
        @login_required
        def wrapped(request,*args,**kwargs):
            if get_role(request.user) not in roles: raise PermissionDenied('You do not have permission to access this workspace.')
            return view(request,*args,**kwargs)
        return wrapped
    return decorator
@never_cache
@login_required
def dashboard(request):
    role=get_role(request.user)
    if role=='ADMIN': return redirect('admin_workspace')
    if role=='SUPPLIER': invoices=FreightInvoice.objects.filter(supplier=request.user.profile.supplier) if request.user.profile.supplier_id else FreightInvoice.objects.none()
    elif role=='CARRIER': invoices=FreightInvoice.objects.filter(carrier=request.user.profile.carrier) if request.user.profile.carrier_id else FreightInvoice.objects.none()
    else: invoices=FreightInvoice.objects.all()
    cases=AuditException.objects.all()
    if role=='SUPPLIER': cases=cases.filter(invoice__in=invoices)
    if role=='CARRIER': cases=cases.filter(invoice__in=invoices)
    counts={'shipments':Shipment.objects.count(),'invoices':invoices.count(),'exceptions':cases.count(),'open_cases':cases.exclude(status__in=['REJECTED','RECONCILED']).count(),'billed':invoices.aggregate(v=Sum('billed_total'))['v'] or Decimal('0'),'discrepancy':cases.aggregate(v=Sum('original_discrepancy'))['v'] or Decimal('0')}
    queues={
      'PLANNER':('Shipment Registry',Shipment.objects.select_related('carrier','supplier','product','lane').all().order_by('-shipment_date')[:8]),
      'SUPPLIER':('My Recent Invoices',invoices.order_by('-submitted_at')[:8]),
      'CARRIER':('Carrier Cases',cases.order_by('-created_at')[:8]),
      'ANALYST':('New Exceptions',cases.filter(status__in=['NEW','RETURNED_TO_ANALYST','CARRIER_DISPUTED','CARRIER_COUNTEROFFER','REVERIFY']).order_by('-created_at')[:8]),
      'MANAGER':('Awaiting Manager Review',cases.filter(status__in=['MANAGER_REVIEW','MANAGER_REVERIFY']).order_by('-created_at')[:8]),
      'FINANCE':('Finance Cases',cases.filter(status__in=['CARRIER_ACCEPTED','FINANCE_RECONCILIATION']).order_by('-created_at')[:8]),
    }
    title,records=queues.get(role,('Workspace',[]))
    if role=='PLANNER':
        kpis=[('Total shipments',Shipment.objects.count(),'Operational registry','bi-truck','/shipments/'),('In transit',Shipment.objects.filter(delivery_status='In transit').count(),'Awaiting delivery','bi-box-seam','/shipments/'),('Delivered',Shipment.objects.filter(delivery_status='Delivered').count(),'Delivery recorded','bi-check2-circle','/shipments/'),('Missing proof',Shipment.objects.filter(delivery_records__isnull=True).distinct().count(),'Delivery records required','bi-exclamation-circle','/shipments/')]
    elif role=='SUPPLIER':
        kpis=[('Submitted invoices',invoices.count(),'Your organization only','bi-receipt','/invoices/'),('Validation failures',invoices.exclude(validation_status='VALID').count(),'Requires attention','bi-exclamation-diamond','/invoices/'),('Pending invoices',invoices.filter(status__in=['SUBMITTED','REVIEW_REQUIRED']).count(),'In process','bi-hourglass-split','/invoices/'),('Processed invoices',invoices.filter(status__in=['READY_FOR_PAYABLE','RECONCILED']).count(),'Ready or completed','bi-check2-circle','/invoices/')]
    elif role=='CARRIER':
        kpis=[('Pending responses',cases.filter(status='CARRIER_RESPONSE').count(),'Awaiting carrier action','bi-reply','/cases/'),('Accepted requests',cases.filter(status='CARRIER_ACCEPTED').count(),'Agreed cases','bi-check2-circle','/cases/'),('Disputes',cases.filter(status='CARRIER_DISPUTED').count(),'Returned for review','bi-exclamation-circle','/cases/'),('Counteroffers',cases.filter(status='CARRIER_COUNTEROFFER').count(),'Proposed revisions','bi-arrow-left-right','/cases/')]
    elif role=='ANALYST':
        kpis=[('New exceptions',cases.filter(status='NEW').count(),'Awaiting investigation','bi-search','/cases/'),('Open investigations',cases.filter(status__in=['NEW','RETURNED_TO_ANALYST','CARRIER_DISPUTED','CARRIER_COUNTEROFFER','REVERIFY']).count(),'Assigned work queue','bi-clipboard2-check','/cases/'),('Manager returns',cases.filter(status='RETURNED_TO_ANALYST').count(),'Re-verification required','bi-arrow-return-left','/cases/'),('Completed reviews',AnalystReview.objects.filter(actor=request.user).count(),'Your submitted reviews','bi-check2-circle','/cases/')]
    elif role=='MANAGER':
        kpis=[('Fresh requests',cases.filter(status='MANAGER_REVIEW').count(),'First-time reviews','bi-inbox','/cases/'),('Re-verifications',cases.filter(status='MANAGER_REVERIFY').count(),'Revised cases','bi-arrow-repeat','/cases/'),('Approved requests',ManagerDecision.objects.filter(actor=request.user,decision='APPROVE').count(),'Your approvals','bi-check2-circle','/cases/'),('Rejected requests',ManagerDecision.objects.filter(actor=request.user,decision='REJECT').count(),'Your decisions','bi-x-circle','/cases/')]
    else:
        notes=CreditNote.objects.all()
        kpis=[('Notes received',notes.count(),'Actual notes recorded','bi-receipt','/finance/'),('Verified credits',notes.filter(verification_status='VERIFIED').count(),'Eligibility checked','bi-patch-check','/finance/'),('Credits applied',sum((n.applied_amount for n in notes),Decimal('0')),'Active applications · ₹','bi-cash-coin','/finance/'),('Reconciliation gaps',ReconciliationRecord.objects.exclude(status='RECONCILED').count(),'Open financial differences','bi-exclamation-diamond','/finance/')]
    return render(request,'audit/dashboard.html',{'role':role,'counts':counts,'kpis':kpis,'invoice_status_data':list(invoices.values('status').annotate(total=Count('id')).order_by('status')),'queue_title':title,'records':records,'recent_events':AuditEvent.objects.order_by('-created_at')[:6] if role=='ADMIN' else []})
@role_required('ADMIN')
def admin_workspace(request):
    return render(request,'audit/admin_workspace.html',{'pending':UserProfile.objects.filter(status='PENDING').select_related('user').order_by('created_at'),'approved':UserProfile.objects.filter(status='APPROVED').select_related('user').order_by('-reviewed_at')[:15],'rejected':UserProfile.objects.filter(status='REJECTED').select_related('user').order_by('-reviewed_at')[:15],'events':AuditEvent.objects.order_by('-created_at')[:20],'counts':{'pending':UserProfile.objects.filter(status='PENDING').count(),'approved':UserProfile.objects.filter(status='APPROVED').count(),'rejected':UserProfile.objects.filter(status='REJECTED').count(),'users':User.objects.count()}})
@role_required('ADMIN')
@transaction.atomic
def registration_decision(request,pk,decision):
    if request.method!='POST': return HttpResponseForbidden('POST required.')
    profile=get_object_or_404(UserProfile.objects.select_for_update(),pk=pk)
    if profile.status!='PENDING': messages.error(request,'This registration has already been reviewed.'); return redirect('admin_workspace')
    reason=request.POST.get('reason','').strip()
    if decision not in ['approve','reject']: raise PermissionDenied
    if decision=='reject' and not reason: messages.error(request,'A rejection reason is required.'); return redirect('admin_workspace')
    profile.reviewed_by=request.user; profile.reviewed_at=timezone.now(); profile.rejection_reason=reason
    if decision=='approve':
        role=profile.requested_role
        if role=='SUPPLIER':
            supplier=Supplier.objects.filter(name__iexact=profile.organization_name).first()
            if not supplier: messages.error(request,'Supplier organization must match an existing supplier master record before approval.'); return redirect('admin_workspace')
            profile.supplier=supplier
        if role=='CARRIER':
            carrier=Carrier.objects.filter(name__iexact=profile.organization_name).first()
            if not carrier: messages.error(request,'Carrier organization must match an existing carrier master record before approval.'); return redirect('admin_workspace')
            profile.carrier=carrier
        profile.approved_role=role; profile.status='APPROVED'; profile.user.is_active=True; profile.user.save(update_fields=['is_active'])
        from django.contrib.auth.models import Group
        group,_=Group.objects.get_or_create(name=role.title()); profile.user.groups.add(group)
    else: profile.status='REJECTED'; profile.user.is_active=True; profile.user.save(update_fields=['is_active'])
    profile.save(); AuditEvent.objects.create(actor=request.user,entity_type='Registration',entity_id=profile.user.username,action=f'Registration {decision}d',new_state=profile.status,details=reason or f'Approved role {profile.approved_role}')
    messages.success(request,f'Registration {decision}d successfully.'); return redirect('admin_workspace')
@role_required('PLANNER','ADMIN')
def shipment_list(request):
    qs=Shipment.objects.select_related('carrier','supplier','product','lane').all()
    term=request.GET.get('q','').strip(); start=request.GET.get('start_date',''); end=request.GET.get('end_date','')
    if term: qs=qs.filter(Q(code__icontains=term)|Q(product__name__icontains=term)|Q(carrier__name__icontains=term)|Q(lane__origin__icontains=term)|Q(lane__destination__icontains=term))
    if start: qs=qs.filter(shipment_date__gte=start)
    if end: qs=qs.filter(shipment_date__lte=end)
    sort=request.GET.get('sort','-shipment_date'); allowed=['-shipment_date','shipment_date','code','-code','actual_weight_kg','-actual_weight_kg']; sort=sort if sort in allowed else '-shipment_date'
    page_obj=Paginator(qs.order_by(sort),25).get_page(request.GET.get('page'))
    return render(request,'audit/shipments.html',{'shipments':page_obj.object_list,'page_obj':page_obj,'q':term,'start_date':start,'end_date':end,'sort':sort})
@role_required('PLANNER','ADMIN')
def shipment_create(request):
    form=ShipmentForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        shipment=form.save(); AuditEvent.objects.create(actor=request.user,entity_type='Shipment',entity_id=shipment.code,action='Shipment created',new_state=shipment.delivery_status); messages.success(request,'Shipment created.'); return redirect('shipment_list')
    return render(request,'audit/form_page.html',{'form':form,'title':'Create shipment','subtitle':'Capture operational shipment and cargo details.'})
@role_required('SUPPLIER','ANALYST','MANAGER','FINANCE','ADMIN','CARRIER')
def invoice_list(request):
    qs=FreightInvoice.objects.select_related('supplier','carrier','shipment').all(); role=get_role(request.user)
    if role=='SUPPLIER': qs=qs.filter(supplier=request.user.profile.supplier) if request.user.profile.supplier_id else qs.none()
    if role=='CARRIER': qs=qs.filter(carrier=request.user.profile.carrier) if request.user.profile.carrier_id else qs.none()
    term=request.GET.get('q','').strip(); status=request.GET.get('status',''); start=request.GET.get('start_date',''); end=request.GET.get('end_date','')
    if term: qs=qs.filter(Q(code__icontains=term)|Q(invoice_number__icontains=term)|Q(shipment__code__icontains=term)|Q(supplier__name__icontains=term)|Q(carrier__name__icontains=term))
    if status: qs=qs.filter(status=status)
    if start: qs=qs.filter(invoice_date__gte=start)
    if end: qs=qs.filter(invoice_date__lte=end)
    sort=request.GET.get('sort','-submitted_at'); allowed=['-submitted_at','submitted_at','invoice_date','-invoice_date','billed_total','-billed_total']; sort=sort if sort in allowed else '-submitted_at'
    page_obj=Paginator(qs.order_by(sort),25).get_page(request.GET.get('page'))
    return render(request,'audit/invoices.html',{'invoices':page_obj.object_list,'page_obj':page_obj,'q':term,'status':status,'start_date':start,'end_date':end,'sort':sort,'statuses':FreightInvoice.objects.values_list('status','status').distinct()})
@role_required('SUPPLIER','ADMIN')
def invoice_create(request):
    form=InvoiceForm(request.POST or None,request.FILES or None)
    if get_role(request.user)=='SUPPLIER':
        form.fields['supplier'].queryset=Supplier.objects.filter(pk=request.user.profile.supplier_id) if request.user.profile.supplier_id else Supplier.objects.none()
    if request.method=='POST' and form.is_valid():
        invoice=form.save(commit=False); invoice.code=f'FINV-{timezone.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6].upper()}'; invoice.submitted_by=request.user; invoice.submitted_at=timezone.now()
        if invoice.shipment_id and not invoice.supplier_id: invoice.supplier=invoice.shipment.supplier
        if invoice.shipment_id and not invoice.carrier_id: invoice.carrier=invoice.shipment.carrier
        invoice.save(); validate_invoice(invoice,request.user)
        for seq,(label,kind,billed,expected) in enumerate([('Contracted base freight','BASE',invoice.billed_base,invoice.expected_base),('Fuel surcharge','FUEL',invoice.billed_fuel,invoice.expected_fuel),('Accessorial charges','ACCESSORIAL',invoice.billed_accessorial,invoice.expected_accessorial)],1):
            InvoiceLine.objects.get_or_create(code=f'{invoice.code}-L{seq:02d}',defaults={'invoice':invoice,'description':label,'charge_type':kind,'billed_amount':billed,'expected_amount':expected,'evidence_reference':invoice.supporting_reference})
        messages.success(request,'Invoice submitted and validated.'); return redirect('invoice_detail',pk=invoice.pk)
    return render(request,'audit/form_page.html',{'form':form,'title':'Submit freight invoice','subtitle':'Submit billed charges and supporting evidence for contract validation.'})
@role_required('SUPPLIER','CARRIER','ANALYST','MANAGER','FINANCE','ADMIN')
def invoice_detail(request,pk):
    invoice=get_object_or_404(FreightInvoice.objects.select_related('shipment__lane','shipment__product','shipment__rate_card','carrier','supplier'),pk=pk); role=get_role(request.user)
    if role=='SUPPLIER' and (not request.user.profile.supplier_id or invoice.supplier_id!=request.user.profile.supplier_id): raise PermissionDenied
    if role=='CARRIER' and (not request.user.profile.carrier_id or invoice.carrier_id!=request.user.profile.carrier_id): raise PermissionDenied
    cases=invoice.exceptions.prefetch_related('reviews','decisions','carrier_responses','credit_notes').all()
    events=AuditEvent.objects.filter(Q(entity_id=invoice.code)|Q(entity_type='AuditException',entity_id__in=cases.values_list('code',flat=True))|Q(entity_type='CreditNote',entity_id__in=CreditNote.objects.filter(exception__in=cases).values_list('code',flat=True))).select_related('actor').order_by('-created_at')[:80]
    return render(request,'audit/invoice_detail.html',{'invoice':invoice,'cases':cases,'role':role,'events':events,'eligible_invoices':FreightInvoice.objects.filter(carrier=invoice.carrier,currency=invoice.currency).exclude(status='RECONCILED').order_by('-invoice_date')[:100]})
@role_required('ANALYST','MANAGER','CARRIER','FINANCE','ADMIN')
def case_queue(request):
    role=get_role(request.user)
    qs=AuditException.objects.select_related('invoice','invoice__shipment','invoice__carrier','invoice__supplier').all()
    if role=='CARRIER': qs=qs.filter(invoice__carrier=request.user.profile.carrier) if request.user.profile.carrier_id else qs.none()
    status=request.GET.get('status','').strip(); term=request.GET.get('q','').strip(); start=request.GET.get('start_date',''); end=request.GET.get('end_date','')
    if status: qs=qs.filter(status=status)
    if term: qs=qs.filter(Q(code__icontains=term)|Q(invoice__code__icontains=term)|Q(invoice__invoice_number__icontains=term)|Q(invoice__shipment__code__icontains=term)|Q(invoice__carrier__name__icontains=term))
    if start: qs=qs.filter(created_at__date__gte=start)
    if end: qs=qs.filter(created_at__date__lte=end)
    sort=request.GET.get('sort','-updated_at'); allowed=['-updated_at','updated_at','created_at','-created_at','original_discrepancy','-original_discrepancy']; sort=sort if sort in allowed else '-updated_at'
    page_obj=Paginator(qs.order_by(sort),25).get_page(request.GET.get('page'))
    status_choices=AuditException.objects.values_list('status','status').distinct().order_by('status')
    return render(request,'audit/case_queue.html',{'cases':page_obj.object_list,'page_obj':page_obj,'status':status,'q':term,'start_date':start,'end_date':end,'sort':sort,'statuses':status_choices,'role':role})

@role_required('ANALYST','MANAGER','CARRIER','ADMIN')
def case_action(request,pk):
    if request.method!='POST': return HttpResponseForbidden('POST required.')
    case=get_object_or_404(AuditException.objects.select_related('invoice__carrier'),pk=pk); action=request.POST.get('action','')
    try:
        if action=='analyst_submit': analyst_submit(case,request.user,request.POST.get('findings',''),request.POST.get('root_cause',''),request.POST.get('recommendation','CREDIT'),request.POST.get('amount','0'),request.POST.get('evidence',''))
        elif action=='manager_decide': manager_decide(case,request.user,request.POST.get('decision',''),request.POST.get('comments',''),request.POST.get('amount'))
        elif action=='carrier_respond': carrier_respond(case,request.user,request.POST.get('response',''),request.POST.get('explanation',''),request.POST.get('amount'))
        else: raise PermissionDenied('Unknown action.')
        messages.success(request,'Case action recorded. Previous history has been preserved.')
    except (ValidationError,PermissionDenied,ValueError,InvalidOperation,TypeError) as exc: messages.error(request,str(exc))
    return redirect('invoice_detail',pk=case.invoice_id)
@role_required('FINANCE','ADMIN')
def finance_workspace(request):
    cases=AuditException.objects.filter(status__in=['CARRIER_ACCEPTED','FINANCE_RECONCILIATION','RECONCILED']).select_related('invoice','invoice__carrier').order_by('-updated_at')
    notes=CreditNote.objects.select_related('exception','invoice','carrier').order_by('-created_at')
    return render(request,'audit/finance.html',{'cases':cases,'notes':notes,'eligible_invoices':FreightInvoice.objects.order_by('-invoice_date')[:100],'verified':notes.filter(verification_status='VERIFIED').count(),'pending':notes.filter(verification_status='PENDING').count(),'applied':sum((n.applied_amount for n in notes),Decimal('0'))})
@role_required('FINANCE','ADMIN')
def credit_action(request,pk):
    if request.method!='POST': return HttpResponseForbidden('POST required.')
    case=get_object_or_404(AuditException,pk=pk); action=request.POST.get('action')
    try:
        if action=='issue':
            if get_role(request.user)!='FINANCE': raise PermissionDenied('Finance role required.')
            if case.status!='CARRIER_ACCEPTED': raise ValidationError('Carrier must accept before a credit note is recorded.')
            decision=case.decisions.filter(decision='APPROVE').order_by('-created_at').first(); response=case.carrier_responses.filter(response='ACCEPT').order_by('-created_at').first()
            amount=Decimal(request.POST.get('amount','0'))
            external_identifier=request.POST.get('note_identifier','').strip(); document_reference=request.POST.get('reference','').strip()
            if amount<=0: raise ValidationError('Issued amount must be positive.')
            currency=request.POST.get('currency',case.invoice.currency).strip().upper()
            if not external_identifier or not document_reference: raise ValidationError('Actual credit-note identifier and document reference are required.')
            if len(currency)!=3 or not currency.isalpha(): raise ValidationError('Currency must be a three-letter code such as INR.')
            if CreditNote.objects.filter(carrier=case.invoice.carrier,external_identifier=external_identifier).exists(): raise ValidationError('This carrier credit-note identifier has already been recorded.')
            if not case.decisions.filter(decision='APPROVE').exists() or not case.carrier_responses.filter(response='ACCEPT').exists(): raise ValidationError('A manager approval and carrier acceptance are required before recording a credit note.')
            note=CreditNote.objects.create(code=f'CN-{timezone.now():%Y%m%d%H%M%S}-{case.pk}',external_identifier=external_identifier,exception=case,invoice=case.invoice,carrier=case.invoice.carrier,issued_amount=amount,currency=currency,issue_date=date.fromisoformat(request.POST.get('issue_date') or date.today().isoformat()),document_reference=document_reference,is_synthetic=case.is_synthetic)
            previous=case.status; case.status='FINANCE_RECONCILIATION'; case.save(update_fields=['status','updated_at'])
            AuditEvent.objects.create(actor=request.user,entity_type='CreditNote',entity_id=note.code,action='Actual credit note recorded',new_state='PENDING',details=f'Carrier note {external_identifier} recorded; not yet verified.',amount=amount,is_synthetic=case.is_synthetic)
            AuditEvent.objects.create(actor=request.user,entity_type='AuditException',entity_id=case.code,action='Actual credit note received',previous_state=previous,new_state=case.status,details=f'Actual note {external_identifier} recorded for verification.',amount=amount,is_synthetic=case.is_synthetic)
            messages.success(request,'Actual credit note recorded; finance verification is still required.')
        elif action=='verify':
            note=get_object_or_404(CreditNote,pk=request.POST.get('note_id'),exception=case); verify_credit(note,request.user,request.POST.get('approved')=='yes',request.POST.get('comments','')); messages.success(request,f'Credit note status: {note.verification_status}.')
        elif action=='apply':
            note=get_object_or_404(CreditNote,pk=request.POST.get('note_id'),exception=case); target_id=request.POST.get('target_invoice_id'); target=get_object_or_404(FreightInvoice,pk=target_id,carrier=note.carrier,currency=note.currency) if target_id else note.invoice; apply_credit(note,request.user,request.POST.get('amount','0'),request.POST.get('reference',''),target_invoice=target); messages.success(request,f'Credit application recorded against {target.code}.')
        elif action=='reverse':
            app=get_object_or_404(CreditApplication,pk=request.POST.get('application_id'),credit_note__exception=case); reverse_application(app,request.user,request.POST.get('reason','')); messages.success(request,'Credit application reversal recorded.')
        elif action=='reconcile': rec=reconcile(case,request.user); messages.success(request,f'Reconciliation status: {rec.status}. Difference ₹{rec.difference}.' )
        else: raise PermissionDenied('Unknown finance action.')
    except (ValidationError,PermissionDenied,ValueError,InvalidOperation,TypeError) as exc: messages.error(request,str(exc))
    return redirect('finance_workspace')
@role_required('ADMIN','FINANCE')
def audit_history(request): return render(request,'audit/audit_history.html',{'events':AuditEvent.objects.select_related('actor').all()[:500]})
@login_required
def export_csv(request,kind):
    allowed={
      'invoices':FreightInvoice,'shipments':Shipment,'exceptions':AuditException,'events':AuditEvent,
      'invoice_lines':InvoiceLine,'reviews':AnalystReview,'decisions':ManagerDecision,'responses':CarrierResponse,
      'credit_notes':CreditNote,'credit_applications':CreditApplication,'reconciliation':ReconciliationRecord,
    }
    if kind not in allowed: raise PermissionDenied
    role=get_role(request.user); model=allowed[kind]
    role_scope={
      'invoices':['ADMIN','FINANCE','ANALYST','MANAGER','SUPPLIER','CARRIER'],
      'shipments':['ADMIN','FINANCE','ANALYST','MANAGER','PLANNER'],
      'exceptions':['ADMIN','FINANCE','ANALYST','MANAGER','SUPPLIER','CARRIER'],
      'events':['ADMIN','FINANCE'], 'invoice_lines':['ADMIN','FINANCE','ANALYST','MANAGER','SUPPLIER','CARRIER'],
      'reviews':['ADMIN','FINANCE','ANALYST','MANAGER'], 'decisions':['ADMIN','FINANCE','MANAGER'],
      'responses':['ADMIN','FINANCE','ANALYST','MANAGER','CARRIER'],
      'credit_notes':['ADMIN','FINANCE','CARRIER'], 'credit_applications':['ADMIN','FINANCE'], 'reconciliation':['ADMIN','FINANCE'],
    }
    if role not in role_scope[kind]: raise PermissionDenied
    qs=model.objects.all()
    if kind in ['invoices','invoice_lines']:
        if kind=='invoices':
            if role=='SUPPLIER': qs=qs.filter(supplier=request.user.profile.supplier) if request.user.profile.supplier_id else qs.none()
            if role=='CARRIER': qs=qs.filter(carrier=request.user.profile.carrier) if request.user.profile.carrier_id else qs.none()
        else:
            if role=='SUPPLIER': qs=qs.filter(invoice__supplier=request.user.profile.supplier) if request.user.profile.supplier_id else qs.none()
            if role=='CARRIER': qs=qs.filter(invoice__carrier=request.user.profile.carrier) if request.user.profile.carrier_id else qs.none()
    elif kind in ['exceptions','reviews','decisions','responses','credit_notes','credit_applications','reconciliation']:
        if role=='SUPPLIER':
            if not request.user.profile.supplier_id: qs=qs.none()
            elif kind=='exceptions': qs=qs.filter(invoice__supplier=request.user.profile.supplier)
            elif kind=='reviews': qs=qs.filter(exception__invoice__supplier=request.user.profile.supplier)
            elif kind=='decisions': qs=qs.filter(exception__invoice__supplier=request.user.profile.supplier)
            elif kind=='responses': qs=qs.filter(exception__invoice__supplier=request.user.profile.supplier)
            elif kind=='credit_notes': qs=qs.none()
        if role=='CARRIER':
            if not request.user.profile.carrier_id: qs=qs.none()
            elif kind=='exceptions': qs=qs.filter(invoice__carrier=request.user.profile.carrier)
            elif kind=='responses': qs=qs.filter(exception__invoice__carrier=request.user.profile.carrier)
            elif kind=='credit_notes': qs=qs.filter(carrier=request.user.profile.carrier)
            elif kind=='credit_applications': qs=qs.none()
    term=request.GET.get('q','').strip(); status=request.GET.get('status','')
    search_fields={'invoices':['code','invoice_number','shipment__code'],'shipments':['code','product__name','carrier__name'],'exceptions':['code','invoice__code','issue_type'],'events':['entity_id','action'],'invoice_lines':['code','invoice__code','description'],'reviews':['exception__code','findings'],'decisions':['exception__code','comments'],'responses':['exception__code','explanation'],'credit_notes':['code','exception__code','invoice__code'],'credit_applications':['reference','credit_note__code','invoice__code'],'reconciliation':['exception__code','status']}
    if term:
        query=Q()
        for field in search_fields[kind]: query |= Q(**{f'{field}__icontains':term})
        qs=qs.filter(query)
    if status and hasattr(model,'status'): qs=qs.filter(status=status)
    start=request.GET.get('start_date'); end=request.GET.get('end_date')
    date_field='invoice_date' if kind=='invoices' else ('shipment_date' if kind=='shipments' else ('created_at' if any(f.name=='created_at' for f in model._meta.fields) else None))
    if start and date_field: qs=qs.filter(**{f'{date_field}__date__gte':start} if date_field=='created_at' else {f'{date_field}__gte':start})
    if end and date_field: qs=qs.filter(**{f'{date_field}__date__lte':end} if date_field=='created_at' else {f'{date_field}__lte':end})
    fields={
      'invoices':['code','invoice_number','supplier','carrier','shipment','invoice_date','billed_total','expected_total','validation_status','status'],
      'shipments':['code','carrier','supplier','product','lane','shipment_date','delivery_status','actual_weight_kg'],
      'exceptions':['code','invoice','issue_type','original_discrepancy','status','current_cycle'],
      'events':['created_at','actor','entity_type','entity_id','action','new_state','amount','details'],
      'invoice_lines':['code','invoice','description','charge_type','billed_amount','expected_amount','evidence_reference'],
      'reviews':['exception','actor','cycle','findings','recommendation','recommended_amount','created_at'],
      'decisions':['exception','actor','cycle','decision','approved_amount','comments','created_at'],
      'responses':['exception','actor','response','proposed_amount','explanation','created_at'],
      'credit_notes':['code','exception','invoice','carrier','issued_amount','currency','issue_date','verification_status','verification_comments'],
      'credit_applications':['credit_note','invoice','actor','amount','reference','created_at','reversed_at','reversal_reason'],
      'reconciliation':['exception','actor','approved_amount','agreed_amount','issued_amount','verified_amount','applied_amount','remaining_amount','difference','status','created_at'],
    }[kind]
    response=HttpResponse(content_type='text/csv; charset=utf-8'); response['Content-Disposition']=f'attachment; filename="freightiq_{kind}.csv"'; response.write('\ufeff'); writer=csv.writer(response); writer.writerow(fields)
    for obj in qs.iterator(): writer.writerow([str(getattr(obj,f,'')) for f in fields])
    return response
