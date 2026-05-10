from django.contrib import admin
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel

class AgentVersionInline(admin.TabularInline):
    model = AgentVersionModel
    extra = 0
    fields = ('version_number', 'created_at')
    readonly_fields = ('version_number', 'created_at')
    show_change_link = True
    can_delete = False

@admin.register(AgentModel)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name',  'created_at', 'updated_at')
   
