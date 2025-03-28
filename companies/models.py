from django.db import models
from django.db.models.functions import Lower

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
    status = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    start_date = models.DateField()
    maps_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    def __str__(self):
        return self.name
    
    class Meta:
        indexes = [
            models.Index(Lower('name'), name='company_name_lower_idx'),
        ]

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
    administering_company = models.ForeignKey(Company, related_name='participations', blank=True, null=True, on_delete=models.CASCADE)
    representatives = models.ManyToManyField(Person, related_name='roles')
    mandate = models.CharField(max_length=255)
    
    # The company that is managed by administrator
    annual_account = models.ForeignKey(AnnualAccount, related_name='administrators', on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.administering_company:
            return f"{self.representatives.first()} ({self.administering_company.name})"
        return self.representatives.first().first_name + " " + self.representatives.first().last_name
    
    @property
    def is_natural_person(self):
        return self.administering_company is None