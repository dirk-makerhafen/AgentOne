from datetime import datetime, timedelta
from hashlib import sha256
import json
from django.db import models
from django_enum import EnumField

class ContentType(models.TextChoices):
    IMAGE = "IMAGE"
    TEXT = "TEXT"
    JSON = "JSON"

class GenericContent(models.Model):
    sha256 = models.CharField(max_length=64, primary_key=True)
    content = models.TextField()
    content_type = EnumField(ContentType, default=ContentType.TEXT)
    expires_at = models.DateTimeField(null=True, default=None, blank=True)

    def get(self):
        if self.content_type == ContentType.JSON:
            return json.loads(self.content)
        return self.content
    
    @classmethod
    def from_text(cls, text, max_age=None):
        h = sha256(text.encode()).hexdigest()
        item = cls.objects.get_or_create(sha256=h, defaults={"content": text, "content_type": ContentType.TEXT})[0]
        item.extend_expired_at(max_age=max_age)
        return item

    @classmethod
    def from_image(cls, image_data, max_age=None):
        h = sha256(image_data.encode()).hexdigest()
        item = cls.objects.get_or_create(sha256=h, defaults={"content": image_data, "content_type": ContentType.IMAGE})[0]
        item.extend_expired_at(max_age=max_age)
        return item

    @classmethod
    def from_data(cls, data:dict|list, max_age=None):
        data_str = json.dumps(data)
        h = sha256(data_str.encode()).hexdigest()
        item = cls.objects.get_or_create(sha256=h, defaults={"content": data_str, "content_type": ContentType.JSON})[0]
        item.extend_expired_at(max_age=max_age)
        return item

    @classmethod
    def from_file(cls, path, max_age=None):
        content = open(path,"r", encoding="utf-8").read()
        content_type = ContentType.TEXT
        if path[-3:] in [".py", "js" ] or path[-4:] in [".txt", ".css" ] or  path[-5:] in [".html" ]:
            content_type = ContentType.TEXT
        elif path[-4:] in [".jpg","png" ] or path[-5:] in [".jpeg", "tiff" ]:
            content_type = ContentType.IMAGE
        h = sha256(content.encode()).hexdigest()
        item = cls.objects.get_or_create(sha256=h, defaults={"content": content, "content_type": content_type})[0]
        item.extend_expired_at(max_age=max_age)
        return item

    def extend_expired_at(self, max_age):
        if not max_age:
            return
        new_expiry = datetime.now() + timedelta(days=max_age)
        GenericContent.objects.filter(pk=self.pk, expires_at__lt=new_expiry).update(expires_at=new_expiry)
