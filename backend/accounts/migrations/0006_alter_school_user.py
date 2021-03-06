# Generated by Django 3.2.5 on 2022-02-01 10:01

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_alter_school_logo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='school',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='school_user', to=settings.AUTH_USER_MODEL),
        ),
    ]
