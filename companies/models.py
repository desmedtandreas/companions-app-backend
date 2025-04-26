from django.db import models
from django.db.models.functions import Lower
from taggit.managers import TaggableManager

class CodeLabel(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=255)
    
    class Meta:
        unique_together = ("code", "category")
    
    def __str__(self):
        return f"[{self.category}] {self.code} → {self.name}"

class Company(models.Model):
    number = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    status_code = models.CharField(max_length=255)
    enterprise_type_code = models.CharField(max_length=255)
    legalform_code = models.CharField(max_length=255, blank=True, null=True)
    start_date = models.DateField()
    website = models.CharField(max_length=255,blank=True, null=True)
    maps_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    fin_fetch = models.DateField(blank=True, null=True)
    tags = TaggableManager(blank=True)

    def __str__(self):
        return self.name
    
    class Meta:
        indexes = [
            models.Index(Lower('name'), name='company_name_lower_idx'),
            ]
    
    @property
    def status(self):
        status_map = {
            '000': 'Actief',
            '0' : 'Stopgezet',
            '050' : 'Opening Faillissement'
        }
        
        try:
            status = self.status_code
            if status in status_map:
                return status_map[status]
            else:
                return None
        except Exception:
            return None
        
    @property
    def legalform(self):
        try:
            return CodeLabel.objects.get(code=self.legalform_code, category="JuridicalForm").name
        except CodeLabel.DoesNotExist:
            return None
        
    def legalform_short(self):
        abbr = {
            'Besloten Vennootschap': 'BV',
            'Naamloze Vennootschap': 'NV',
            'Commanditaire Vennootschap': 'CommV',
        }
    
        try:
            legalform = self.legalform
            if legalform in abbr:
                return abbr[legalform]
            else:
                return None
        except CodeLabel.DoesNotExist:
            return None
            
        
    @property
    def enterprise_type(self):
        try:
            return CodeLabel.objects.get(code=self.enterprise_type_code, category="TypeOfEnterprise").name
        except CodeLabel.DoesNotExist:
            return None
        

class Address(models.Model):
    company = models.ForeignKey(Company, related_name='addresses', db_index=True, on_delete=models.CASCADE)
    type = models.CharField(max_length=100, db_index=True)
    street = models.CharField(max_length=255, db_index=True)
    house_number = models.CharField(max_length=20)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    
    class Meta:
        indexes = [
            models.Index(fields=["street", "postal_code", "house_number"]),
        ]

    def __str__(self):
        return f"{self.street} {self.house_number}, {self.postal_code} {self.city}"
    
    def full_address(self):
        return f"{self.street} {self.house_number}, {self.postal_code}"
    
    def formatted_address(self):
        return f"{self.street} {self.house_number} {self.postal_code} {self.city}"
    
class AnnualAccount(models.Model):
    company = models.ForeignKey(Company, related_name='annual_accounts', on_delete=models.CASCADE)
    reference = models.CharField(max_length=255, unique=True)
    end_fiscal_year = models.DateField(default=None, blank=True, null=True)
    
    def __str__(self):
        return self.reference
    
    def get_rubric(self, code):
        try:
            return self.financial_rubrics.get(code=code)
        except FinancialRubric.DoesNotExist:
            return None
        
    def get_previous_account(self):
        try:
            return self.company.annual_accounts.filter(end_fiscal_year__lt=self.end_fiscal_year).order_by('-end_fiscal_year').first()
        except AnnualAccount.DoesNotExist:
            return None
    
    def calculate_kpis(self):
        previous = self.get_previous_account()

        def val(code, account):
            rubric = account.get_rubric(code) if account else None
            return rubric.value if rubric and rubric.value is not None else 0
        
        def safe_capex(current, previous, additional):
            if None in (current, previous, additional):
                return None
            return current.value - previous.value + additional.value

        kpis = {
            "equity": val("10/15", self),
            "turnover": self.get_rubric("70").value if self.get_rubric("70") else None,
            "margin": self.get_rubric("9900").value if self.get_rubric("9900") else val("70", self) - (val("60", self) + val("61", self)),
            "ebitda": val("9901", self) + val("630", self) + val("631/4", self),
            "profit": val("9904", self),
            "remuneration": val("62", self),
            "fte": val("1003", self),
            "real_estate": val("22", self),
            "net_debt": val("54/58", self) - val("17", self) - val("42", self) - val("43", self),
            "capex": safe_capex(self.get_rubric("21/28"), previous.get_rubric("21/28") if previous else None, self.get_rubric("630")),
        }

        return kpis
        
    
class FinancialRubric(models.Model):
    code = models.CharField(max_length=255)
    value = models.DecimalField(max_digits=20, decimal_places=2)
    
    annual_account = models.ForeignKey(AnnualAccount, related_name='financial_rubrics', on_delete=models.CASCADE)
    
    def __str__(self):
        return self.code
    
class Person(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
class Administrator(models.Model):
    administering_company = models.ForeignKey(Company, related_name='administrator_of', blank=True, null=True, on_delete=models.CASCADE)
    representatives = models.ManyToManyField(Person, related_name='roles')
    
    # The company that is managed by administrator
    annual_account = models.ForeignKey(AnnualAccount, related_name='administrators', on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.administering_company:
            return f"{self.representatives.first()} ({self.administering_company.name})"
        return self.representatives.first().first_name + " " + self.representatives.first().last_name
    
    @property
    def is_natural_person(self):
        return self.administering_company is None
    

class Participation(models.Model):
    held_company = models.ForeignKey(Company, related_name='held_by', on_delete=models.CASCADE)
    stocks = models.DecimalField(max_digits=20, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    
    annual_account = models.ForeignKey(AnnualAccount, related_name='participations', on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.held_company.name} ({self.percentage}%)"