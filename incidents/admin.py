from django.contrib import admin
from incidents.models import Incident, Document

admin.site.register(Incident)
admin.site.register(Document)