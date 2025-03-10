import django_tables2 as tables
from django_tables2.utils import A
from .models import AddOn

class AddOnTable(tables.Table):
    class Meta:
        model = AddOn
        template_name = "django_tables2/bootstrap.html"
        fields = (
            'name', 
            'ebitda', 
            'bezoldigingen', 
            'mva', 
            'capex_noden_avg_3j',
            'netto_schuldpositie',
            'winst_verlies',
            'eigen_vermogen',
            )
        
        EBITDA = tables.Column(accessor="ebitda")
        
        attrs = {'class': 'table table-striped'}
        
        
        