import json
import math
from django.db import models
from django_enum import EnumField
import base64
from jinja2 import Environment, BaseLoader
from server.models.enums.message_enums import MessageContentType
from server.models.base_model import BaseModel
from server.models.content import  GenericContent


_JINJA_ENV = Environment(loader=BaseLoader())

class QueryMessagePart(BaseModel):
    # refernces
    query_message = models.ForeignKey("server.QueryMessage"           , on_delete=models.CASCADE, related_name='query_message_parts')
    #message       = models.ForeignKey("server.Message"    , default=None, null=True, on_delete=models.SET_DEFAULT, related_name='query_message_parts')
    source_message_part  = models.ForeignKey("server.MessagePart", default=None, null=True, on_delete=models.SET_DEFAULT, related_name='query_message_parts')

    tokens = models.IntegerField(default=None, blank=True, null=True)

    content          = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_message_parts_content")
    content_prefix   = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_message_parts_prefix")
    content_postfix  = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_message_parts_postfix")
    template_data    = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="query_message_parts_template_data")
    content_type     = EnumField(MessageContentType, default=MessageContentType.TEXT)

    tags = models.JSONField(default=list, null=True, blank=True, help_text="List of tags used")

    def to_openai_message(self, fail_on_error=True) -> list[dict]:

        if self.source_message_part:
            content_type =  self.source_message_part.content_type
            content =   self.source_message_part.content
            template_data = self.source_message_part.template_data

            print("to_openai_message here1")
        else:
            content_type =  self.content_type
            content = self.content
            template_data = self.template_data
            print("to_openai_message here2")

        if not content:
            raise Exception("No content set")
    
        message_contents = None

        if content_type == MessageContentType.TEXT:
            message_contents = [{"type": "text", "text": content.get()}, ]

        elif content_type == MessageContentType.TEMPLATE:
            try:
                rtemplate = _JINJA_ENV.from_string(content.get())
                data = {}
                context = {**template_data.get(), **data}
                message_contents = [{"type": "text", "text": rtemplate.render(**context)}, ]
            except  Exception as e: 
                if fail_on_error:
                    raise e
                message_contents =  [{"type": "text", "text": f"Error in Template String:{e}\n{content.get()}"}, ]

        elif content_type == MessageContentType.IMAGE:
            message_contents = [{"type": "image_url", "image_url": {"url": content.get()}}, ]

        elif content_type == MessageContentType.JSON:
            message_contents =  [{"type": "text", "text": json.dumps(content.get())}, ]

        if message_contents is None:
            raise Exception(f"No message_content for content {content}")

        # 2. Wrap with prefix/postfix
        if prefix := (self.content_prefix.get() if self.content_prefix else None):
            message_contents.insert(0, {"type": "text", "text": prefix})
        if postfix := (self.content_postfix.get() if self.content_postfix else None):
            message_contents.append({"type": "text", "text": postfix})

        # 3. Token estimation
        tokens = 0
        for message_content in message_contents:
            if msg :=message_content.get("text", None):
                tokens += math.ceil(len(msg) / 3.8)
        if self.tokens != tokens:
            self.tokens = tokens
            self.save()
                
        return message_contents

'''
        if template_data:
            print("to_openai_message here3", template_data.content)
            # Use template_data as a Jinja2 template
            try:
                rtemplate = _JINJA_ENV.from_string(template_data.content)
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
                    print("to_openai_message here4")
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
                    print("to_openai_message here5", part_content)

            except  Exception as e: 
                if fail_on_error:
                    raise e
                part_content = f"Error in Template String:{e}\n{template_data.content}"

        elif content:
            part_content = content.content

        print("to_openai_message here6", part_content)
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
        print("to_openai_message here7", part_content)
        return part_content

'''
