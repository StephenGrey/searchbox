# Generated by Django 2.0.6 on 2018-10-31 09:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0034_auto_20180918_0822'),
    ]

    operations = [
        migrations.AddField(
            model_name='file',
            name='oldpaths_to_delete',
            field=models.TextField(blank=True, null=True, verbose_name='Old paths'),
        ),
    ]