# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-12-08 07:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scraper', '0007_auto_20171208_0728'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogpost',
            name='thumburl',
            field=models.URLField(blank=True, verbose_name='thumbnail url'),
        ),
    ]
