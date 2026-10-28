from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from audit.models import UserProfile, ROLES, Shipment, FreightInvoice, Carrier, Supplier, Lane, Product, Customer
class RegistrationForm(forms.Form):
    full_name=forms.CharField(max_length=140,widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Full name'}))
    username=forms.CharField(max_length=150,widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Username'}))
    password=forms.CharField(widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Password'}))
    confirm_password=forms.CharField(widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Confirm password'}))
    requested_role=forms.ChoiceField(choices=ROLES,widget=forms.Select(attrs={'class':'form-select','id':'role-select'}))
    organization_name=forms.CharField(max_length=180,required=False,widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Organization name'}))
    def clean_username(self):
        username=self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exists(): raise forms.ValidationError('This username is already in use.')
        return username
    def clean(self):
        data=super().clean()
        if data.get('password') and data.get('confirm_password') and data['password']!=data['confirm_password']: self.add_error('confirm_password','Passwords do not match.')
        if data.get('password'): validate_password(data['password'])
        role=data.get('requested_role')
        if role in ['SUPPLIER','CARRIER'] and not data.get('organization_name','').strip(): self.add_error('organization_name','Organization is required for this role.')
        return data
class ShipmentForm(forms.ModelForm):
    class Meta:
        model=Shipment; fields=['code','carrier','supplier','customer','product','lane','rate_card','shipment_date','expected_delivery','actual_delivery','delivery_status','service_type','quantity','quantity_unit','actual_weight_kg','length_cm','width_cm','height_cm','notes']
        widgets={f:forms.DateInput(attrs={'type':'date','class':'form-control'}) for f in ['shipment_date','expected_delivery','actual_delivery']}
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        for f in self.fields.values(): f.widget.attrs.setdefault('class','form-control')
class InvoiceForm(forms.ModelForm):
    class Meta:
        model=FreightInvoice; fields=['invoice_number','supplier','carrier','shipment','invoice_date','currency','billed_weight_kg','billed_base','billed_fuel','billed_accessorial','declared_total','supporting_reference','supporting_document']
        widgets={'invoice_date':forms.DateInput(attrs={'type':'date','class':'form-control'})}
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        for f in self.fields.values(): f.widget.attrs.setdefault('class','form-control')

    def clean_currency(self):
        value=self.cleaned_data['currency'].strip().upper()
        if len(value)!=3 or not value.isalpha(): raise forms.ValidationError('Currency must be a three-letter code such as INR.')
        return value
