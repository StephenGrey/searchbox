# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

# Register your models here.
from .models import Collection, File, SolrCore

admin.site.register(Collection)
admin.site.register(File)
admin.site.register(SolrCore)


