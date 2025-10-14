
from tools.base.buildin_tools_map import BUILTIN_TOOL_CLASS_MAP

class HistoryLimiter:
    def __init__(self, agentInstance, all_entries=None, all_loaded_paths=None):
        self.agentInstance = agentInstance
        self.all_entries = all_entries if all_entries is not None else []
        self.all_loaded_paths = all_loaded_paths if all_loaded_paths is not None else []
        self.limit_counts = {}
        
        # Populate tool instances based on the agent's available tools
        self.tool_instances = {}
        available_tool_definitions = self.agentInstance.agent.available_tools.filter(is_builtin=True)
        for toolDefinition in available_tool_definitions:
            self.tool_instances[toolDefinition.name] = BUILTIN_TOOL_CLASS_MAP.get(toolDefinition.name)(agentInstance)

        self._define_general_rules()

    def _define_general_rules(self):
        """Defines non-tool-specific limiting rules."""
        limit = self.agentInstance.limit_max_conversation_messages
        self.general_rules = {
            'messages_dont_warn_forget': max(4, limit * 0.80) # Warn for the last 20% or 4 messages
        }

    def get_merged_history_limiting_rules(self):
        """
        Collects all rule templates from active tool instances and merges them
        with database overrides for the current agent instance.
        """
        all_rule_templates = []
        # Use set() to get unique tool instances, preventing duplicates for tools with multiple functions.
        unique_tool_instances = set(self.tool_instances.values())
        for tool_instance in unique_tool_instances:
            if hasattr(tool_instance, 'get_history_limiting_rules'):
                all_rule_templates.extend(tool_instance.get_history_limiting_rules())

        db_rules = self.agentInstance.history_limiting_rules.filter(is_active=True)
        db_rules_map = {f'{rule.group_name}:{rule.rule_name}': rule for rule in db_rules}
        
        merged_rules = []
        for template in all_rule_templates:
            group_name = template.get('group_name', 'default')
            rule_name = template['name']
            rule_key = f'{group_name}:{rule_name}'
            
            rule_data = {
                'group_name': group_name,
                'full_rule_name': rule_key,
                'display_name': rule_name,
                'description': template.get('description', ''),
                'success': template['limits'].get('success'),
                'failed': template['limits'].get('failed'),
                'pending': template['limits'].get('pending'),
                'max': template['limits'].get('max'),
                'db_id': None
            }
            
            if rule_key in db_rules_map:
                db_rule = db_rules_map[rule_key]
                rule_data['db_id'] = db_rule.pk
                if db_rule.limit_success is not None:
                    rule_data['success'] = db_rule.limit_success
                if db_rule.limit_failed is not None:
                    rule_data['failed'] = db_rule.limit_failed
                if db_rule.limit_pending is not None:
                    rule_data['pending'] = db_rule.limit_pending
                if db_rule.limit_max is not None:
                    rule_data['max'] = db_rule.limit_max
            
            merged_rules.append(rule_data)
        
        grouped_rules = {}
        for rule_item in merged_rules:
            group_name = rule_item.pop('group_name', 'default')
            if group_name not in grouped_rules:
                grouped_rules[group_name] = []
            grouped_rules[group_name].append(rule_item)

        for group_name in grouped_rules:
            grouped_rules[group_name].sort(key=lambda x: x['display_name'])
        
        return grouped_rules

    def is_tool_call_limited(self, toolcall, message):
        """Checks if a specific tool call should be excluded based on the defined rules."""

        all_rule_templates = []
        unique_tool_instances = set(self.tool_instances.values())
        for tool_instance in unique_tool_instances:
            if hasattr(tool_instance, 'get_history_limiting_rules'):
                all_rule_templates.extend(tool_instance.get_history_limiting_rules())

        db_rules = self.agentInstance.history_limiting_rules.filter(is_active=True)
        db_rules_map = {rule.rule_name: rule for rule in db_rules}

        internal_merged_rules = []
        for template in all_rule_templates:
            rule_name = template['name']
            if rule_name in db_rules_map:
                db_rule = db_rules_map[rule_name]
                if db_rule.limit_success is not None: template['limits']['success'] = db_rule.limit_success
                if db_rule.limit_failed is not None: template['limits']['failed'] = db_rule.limit_failed
                if db_rule.limit_pending is not None: template['limits']['pending'] = db_rule.limit_pending
                if db_rule.limit_max is not None: template['limits']['max'] = db_rule.limit_max
            internal_merged_rules.append(template)

        self.tool_call_rules = internal_merged_rules # Store for subsequent internal checks

        for rule in self.tool_call_rules:
            if rule['match'](toolcall):
                rule_name = rule['name']
                item_key = rule['key'](toolcall)
                limits = rule['limits']

                self.limit_counts.setdefault(rule_name, {}).setdefault(item_key, {
                    'max': set(), 'success': set(), 'failed': set(), 'pending': set()
                })

                counters = self.limit_counts[rule_name][item_key]
                counters.setdefault(toolcall.status, set()).add(message)
                counters['max'].add(message)

                if len(counters[toolcall.status]) > limits.get(toolcall.status, float('inf')):
                    return True
                if len(counters['max']) > limits.get('max', float('inf')):
                    return True
        return False

    def is_general_message_limited(self, key, message):
        """Checks general message limits, like the one for `warn_forget`."""
        limit = self.general_rules.get(key)
        if limit is None:
            return False
            
        self.limit_counts.setdefault(key, set()).add(message)
        
        return len(self.limit_counts[key]) > limit
