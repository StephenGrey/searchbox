# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-01-11 11:30
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0019_auto_20180108_1837'),
    ]

    operations = [
        migrations.AddField(
            model_name='file',
            name='child',
            field=models.BooleanField(default=False, verbose_name='Child document'),
        ),
    ]