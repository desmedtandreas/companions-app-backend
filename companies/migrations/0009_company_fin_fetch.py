# Generated by Django 5.1.2 on 2025-04-08 16:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0008_rename_annualaccount_participation_annual_account'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='fin_fetch',
            field=models.DateField(blank=True, null=True),
        ),
    ]
