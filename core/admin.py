from django.contrib import admin

from core.models.prompt import Prompt
from django.contrib import admin
from .models.prompt import Prompt
from .models.prompt_variant import PromptVariant
from .models.prompt_relation import AgentPromptRelation


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'source', 'key')
    list_display_links = ('pk',  'key')
    search_fields = ('key','source')
    list_per_page = 50
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PromptVariant)
class PromptVariantAdmin(admin.ModelAdmin):
    list_display = ('prompt', 'owner', 'agent', 'is_enabled', 'created_at', 'next_version_link')
    list_filter = ('is_enabled', 'owner', 'agent', 'prompt__source', 'prompt__key')
    search_fields = ('value',)
    raw_id_fields = ('prompt', 'owner', 'agent', 'next_version')

    def next_version_link(self, obj):
        if obj.next_version:
            return f'#{obj.next_version.pk}'
        return None
    next_version_link.short_description = 'Next Version'

@admin.register(AgentPromptRelation)
class AgentPromptRelationAdmin(admin.ModelAdmin):
    list_display = ('id', 'agent', 'prompt', 'role', 'insert_at', 'index')
    list_filter = ('agent', 'prompt', 'role', 'insert_at')
    search_fields = ('agent__name', 'prompt__key')
    autocomplete_fields = ('agent', 'prompt')

