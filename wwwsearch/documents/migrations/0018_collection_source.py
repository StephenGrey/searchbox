# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-01-08 18:23
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0017_auto_20180108_1816'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='source',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='documents.Source'),
        ),
    ]
