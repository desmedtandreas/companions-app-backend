# Generated by Django 5.1.2 on 2024-12-06 12:40

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('add_on_analysis', '0003_rename_fte_fin_data_bezoldigingen_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='fin_data',
            name='ebitda',
        ),
    ]
