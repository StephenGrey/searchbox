# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-07 06:42
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0009_auto_20170907_0635'),
    ]

    operations = [
        migrations.AlterField(
            model_name='file',
            name='solrid',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Solr ID'),
        ),
    ]
