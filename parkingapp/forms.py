from django import forms
from .models import CustomerProfile
from .models import Payment


class SignUpForm(forms.ModelForm):
    class Meta:
        model=CustomerProfile
        fields=['full_name','phone_number','email']
        widgets={
            'full_name':forms.TextInput(attrs={'placeholder':'Enter Full Name'}),
            'phone_number':forms.NumberInput(attrs={'placeholder':"Enter Phone Number"}),
            'email':forms.TextInput(attrs={'placeholder':'Enter Email'})}
            #'password':forms.PasswordInput(attrs={'placeholder':"Enter Password"})
             #  }

class LoginForm(forms.Form):
    email=forms.CharField(max_length=120)
    #password=forms.CharField(max_length=100)



class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount']
