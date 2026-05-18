from django.db import models
from server.models.base_model import BaseModel
from django.core.exceptions import ValidationError

class DebugLogEntry(BaseModel):
    session = models.ForeignKey("server.SessionModel", on_delete=models.CASCADE, related_name='debug_log_entries')
    event = models.CharField(max_length=64)
    status = models.CharField(max_length=16)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 
