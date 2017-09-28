# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-08 08:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0010_auto_20170907_0642'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collection',
            name='path',
            field=models.FilePathField(allow_files=False, allow_folders=True, max_length=150, path=b'/Users/Stephen/Documents/', recursive=True, verbose_name='File path'),
        ),
        migrations.AlterField(
            model_name='file',
            name='filepath',
            field=models.FilePathField(path=b'/Users/Stephen/Documents/', recursive=True, verbose_name='File path'),
        ),
    ]
