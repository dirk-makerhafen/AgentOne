from __future__ import annotations


class Profile():
    def __init__(self, name = None, model: str|None = None,
                max_retries: int|None = None, max_task_steps: int|None = None, unattended_steps: int|None = None, max_history_messages: int|None = None,
                task_prompt: str|None = None, system_prompt: str|None = None,
                execution_mode: str = 'queue', tool_call_syntax: str = 'default',
                extra_settings: dict|None = None, variants: list[Profile]|None = None) -> None:
        self.name = name
        self.model = model
        self.max_retries = max_retries
        self.max_task_steps = max_task_steps
        self.unattended_steps = unattended_steps
        self.max_history_messages = max_history_messages
        self.task_prompt = task_prompt
        self.system_prompt = system_prompt
        self.execution_mode = execution_mode
        self.tool_call_syntax = tool_call_syntax
        self.extra_settings = extra_settings
        self.variants = variants

    def to_dict(self):
        d = {
            "name" : self.name,
            "model" : self.model,
        }
        if self.max_retries:
            d["max_retries"] = self.max_retries
        if self.max_task_steps:
            d["max_task_steps"] = self.max_task_steps
        if self.unattended_steps:
            d["unattended_steps"] = self.unattended_steps
        if self.max_history_messages:
            d["max_history_messages"] = self.max_history_messages
        if self.task_prompt:
            d["task_prompt"] = self.task_prompt
        if self.system_prompt:
            d["system_prompt"] = self.system_prompt
        if self.execution_mode:
            d["execution_mode"] = self.execution_mode
        if self.tool_call_syntax:
            d["tool_call_syntax"] = self.tool_call_syntax
        if self.extra_settings:
            d["extra_settings"] = self.extra_settings
        if self.variants:
            d["variants"] = [v.to_dict() for v in self.variants] if self.variants else []
        return d
