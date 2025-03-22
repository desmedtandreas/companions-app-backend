from django.db import models

class Company(models.Model):
    enterprise_number = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    legal_form = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Address(models.Model):
    company = models.ForeignKey(Company, related_name='addresses', on_delete=models.CASCADE)
    street = models.CharField(max_length=255)
    house_number = models.CharField(max_length=20)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.street} {self.house_number}, {self.postal_code} {self.city}"
    
    def full_address(self):
        return f"{self.street} {self.house_number}, {self.postal_code} {self.city}"