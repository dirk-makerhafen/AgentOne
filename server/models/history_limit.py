from django.db import models

class HistoryLimitingRule(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    agent = models.ForeignKey("server.Agent", on_delete=models.CASCADE, related_name='history_limiting_rules')

    group_name  = models.CharField(default="default", max_length=255, help_text="Name of tool or other group this limit belongs to")
    rule_name   = models.CharField(max_length=255, help_text="The unique name of the rule template to override (e.g., 'fs_by_path').")
    description = models.TextField(blank=True, default='', help_text="Optional description of why this override exists.")

    limit_success = models.PositiveIntegerField(null=True, blank=True, help_text="Override for successful calls. Blank uses tool default.")
    limit_failed  = models.PositiveIntegerField(null=True, blank=True, help_text="Override for failed calls. Blank uses tool default.")
    limit_pending = models.PositiveIntegerField(null=True, blank=True, help_text="Override for pending calls. Blank uses tool default.")
    limit_max     = models.PositiveIntegerField(null=True, blank=True, help_text="Override for total calls. Blank uses tool default.")

    class Meta:
        unique_together = ('agent', 'group_name', 'rule_name')
        ordering = ['group_name', 'rule_name']

    def __str__(self):
        return f"{self.agent.name}: {self.group_name}.{self.rule_name}"