# Generated by Django 5.1.2 on 2025-07-24 13:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lists', '0002_label_listitem_label'),
    ]

    operations = [
        migrations.CreateModel(
            name='Municipality',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('code', models.CharField(max_length=5, unique=True)),
            ],
        ),
        migrations.AddField(
            model_name='list',
            name='municipality_scores',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
    ]
