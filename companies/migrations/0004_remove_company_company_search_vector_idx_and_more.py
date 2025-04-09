# Generated by Django 5.1.2 on 2025-03-28 16:41

import django.contrib.postgres.indexes
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0003_remove_company_company_name_trgm_and_more'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='company',
            name='company_search_vector_idx',
        ),
        migrations.AddIndex(
            model_name='company',
            index=django.contrib.postgres.indexes.GinIndex(fields=['search_vector'], name='company_search_vector_idx'),
        ),
    ]
