from django.contrib import admin
from incidents.models import Incident, Document, PatternReport

admin.site.register(Incident)
admin.site.register(Document)
admin.site.register(PatternReport)