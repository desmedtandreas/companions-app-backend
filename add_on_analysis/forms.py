from django import forms
from django.forms import TextInput, FileInput

class BTWForm(forms.Form):
    BTWnr = forms.CharField(
        label="BTW nummer", 
        widget=TextInput(attrs={
            'placeholder': 'BE123456789', 
            'class': 'form-control form-control-lg'
            })
        )
    
class UploadFileForm(forms.Form):
    file = forms.FileField(
        widget=FileInput(attrs={
            'class': 'form-control form-control-lg',
            'id': 'fileUpload',
            'aria-label': 'Upload',
        })
    )