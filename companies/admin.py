from django.contrib import admin
from .models import Company, Address

# Register your models here.
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('enterprise_number', 'name', 'legal_form')
    search_fields = ('name', 'enterprise_number')
    list_filter = ('legal_form',)
    ordering = ('name',)
    list_per_page = 20
    actions = ['mark_as_verified']

    def mark_as_verified(self, request, queryset):
        queryset.update(is_verified=True)
        self.message_user(request, "Selected companies have been marked as verified.")
        
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('company', 'street', 'house_number', 'postal_code', 'city', 'country')
    search_fields = ('company__name', 'street', 'postal_code')
    list_filter = ('country',)
    ordering = ('company__name',)
    list_per_page = 20