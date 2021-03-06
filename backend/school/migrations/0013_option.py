# Generated by Django 3.2.5 on 2022-02-02 17:42

import cloudinary.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0012_exam_is_published'),
    ]

    operations = [
        migrations.CreateModel(
            name='Option',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(max_length=500)),
                ('correct', models.TextField(max_length=500)),
                ('image', cloudinary.models.CloudinaryField(blank=True, max_length=255, null=True, verbose_name='image')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='question_options', to='school.question')),
            ],
        ),
    ]
