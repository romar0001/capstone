# Generated by Django 3.2.5 on 2022-03-04 01:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0020_auto_20220304_0914'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studentapplied',
            name='datetime_created',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
