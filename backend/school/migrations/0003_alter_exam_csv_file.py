# Generated by Django 3.2.5 on 2022-02-01 08:05

import cloudinary.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0002_auto_20220201_1547'),
    ]

    operations = [
        migrations.AlterField(
            model_name='exam',
            name='csv_file',
            field=cloudinary.models.CloudinaryField(max_length=255, null=True),
        ),
    ]
