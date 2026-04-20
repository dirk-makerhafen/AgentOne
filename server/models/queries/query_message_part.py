import json
import math
from django.db import models
from django_enum import EnumField
import base64
from jinja2 import Template, Environment, BaseLoader
from server.models.enums.message_enums import MessageContentType
from server.models.base_model import BaseModel
from server.models.content import  GenericContent


_JINJA_ENV = Environment(loader=BaseLoader())
class QueryMessagePart(BaseModel):
    # refernces
    query_message             = models.ForeignKey("server.QueryMessage"           , on_delete=models.CASCADE, related_name='query_message_parts')
    conversation_message      = models.ForeignKey("server.ConversationMessage"    , default=None, null=True, on_delete=models.SET_DEFAULT, related_name='query_message_parts')
    conversation_message_part = models.ForeignKey("server.ConversationMessagePart", default=None, null=True, on_delete=models.SET_DEFAULT, related_name='query_message_parts')
    fsLogEntry                = models.ForeignKey("builtin_filesystem.FsLogEntry" , default=None, null=True, on_delete=models.SET_DEFAULT, related_name='query_message_parts')

    tokens = models.IntegerField(default=None, blank=True, null=True)
    index  = models.FloatField(default=0)

    content          = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_message_parts_content")
    content_prefix   = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_message_parts_prefix")
    content_postfix  = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_message_parts_postfix")
    content_template = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_message_parts_template")
    content_type     = EnumField(MessageContentType, default=MessageContentType.TEXT)

    tags = models.JSONField(default=list, null=True, blank=True, help_text="List of tags used")
    
    class Meta:
        ordering = ("index","pk")

    def compile(self, fail_on_error=True):
        part_content = ""
        content = None
        content_type = self.content_type
        content_template = None
        if self.conversation_message_part:
            content_template = self.conversation_message_part.content_template
            content_type =  self.conversation_message_part.content_type
            content =   self.conversation_message_part.content
            print("compile here1")
        else:
            content_template = self.content_template
            content_type =  self.content_type
            content =   self.content
            print("compile here2")
        print("compile here", content_template, content, content_type)
        # 1. Base Content Extraction
        if content_template:
            print("compile here3", content_template.content)
            # Use content_template as a Jinja2 template
            try:
                rtemplate = _JINJA_ENV.from_string(content_template.content)
                data = {}
                if self.query_message and self.query_message.query:
                        # Attempt to pull more context if needed
                        data["message"] = self
                def load_image(image_path):
                    load_image_marker = "LOAD_IMAGE"
                    return f"!__{load_image_marker}__!{image_path}!__{load_image_marker}__!"
                    try:
                        with open(image_path, "rb") as f:
                            encoded = base64.b64encode(f.read()).decode("ascii")
                            img = f"data:image/jpeg;base64,{encoded}"
                    except Exception as e:
                        img = f"error: {e}"
                    return {"type": "image_url", "image_url": {"url": img}}
                if content:
                    print("compile here4")
                    context = {**json.loads(content.content), **data, "load_image": load_image}
                    #context,_= load_model_references(context)
                    part_content = rtemplate.render(**context)
                    load_image_marker = "LOAD_IMAGE"
                    if f"!__{load_image_marker}__!" in part_content:
                        path = part_content.split(f"!__{load_image_marker}__!")[1]
                        try:
                            with open(path, "rb") as f:
                                encoded = base64.b64encode(f.read()).decode("ascii")
                                img = f"data:image/jpeg;base64,{encoded}"
                        except Exception as e:
                            img = f"error: {e}"
                        part_content =  {"type": "image_url", "image_url": {"url": img}}
                    print("compile here5", part_content)

            except  Exception as e: 
                if fail_on_error:
                    raise e
                part_content = f"Error in Template String:{e}\n{content_template.content}"

        elif content:
            part_content = content.content

        elif self.fsLogEntry:
            content_type = "text"
            if self.fsLogEntry.load_mode == "summary":
                part_content = f"# SUMMARY '{self.fsLogEntry.path}':\n{self.fsLogEntry.summary}"
            else:
                part_content = f"# FILE '{self.fsLogEntry.path}':\n{self.fsLogEntry.content}"
        else:
            # Fallback
            part_content = ""
        print("compile here6", part_content)
        # 2. Wrap with prefix/postfix
        if self.content_prefix:
            part_content = f"{self.content_prefix.get()}{part_content}"
        if self.content_postfix:
            part_content = f"{part_content}{self.content_postfix.get()}"

        # 3. Token estimation
        tokens = math.ceil(len(part_content) / 3.8)
        if self.tokens != tokens:
            self.tokens = tokens
            self.save()

        # 4. Content Type Specific Formatting
        if content_type == "image":

            img = part_content
            if part_content.startswith("path:"):
                # Handle path:'...' format
                path = part_content.split(":", 1)[1].strip("'").strip('"')
                try:
                    with open(path, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode("ascii")
                        img = f"data:image/jpeg;base64,{encoded}"
                except Exception as e:
                    img = f"error: {e}"
            return {"type": "image_url", "image_url": {"url": img}}

        if content_type == "file":
             if part_content.startswith("path:"):
                path = part_content.split(":", 1)[1].strip("'").strip('"')
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception:
                    return f"[Error loading file: {path}]"
        print("compile here7", part_content)
        return part_content

