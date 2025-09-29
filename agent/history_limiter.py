
class HistoryLimiter:
    def __init__(self, agentInstance, all_entries, all_loaded_paths, tool_call_rule_templates):
        self.agentInstance = agentInstance
        self.all_entries = all_entries
        self.all_loaded_paths = all_loaded_paths
        self.limit_counts = {}
        
        # Fetch database overrides for the current agent instance
        db_rules = self.agentInstance.history_limiting_rules.filter(is_active=True)
        db_rules_map = {rule.rule_name: rule for rule in db_rules}

        merged_rules = []
        for template in tool_call_rule_templates:
            rule_name = template['name']
            if rule_name in db_rules_map:
                db_rule = db_rules_map[rule_name]
                
                # Override default limits with non-null values from the database
                if db_rule.limit_success is not None:
                    template['limits']['success'] = db_rule.limit_success
                if db_rule.limit_failed is not None:
                    template['limits']['failed'] = db_rule.limit_failed
                if db_rule.limit_pending is not None:
                    template['limits']['pending'] = db_rule.limit_pending
                if db_rule.limit_max is not None:
                    template['limits']['max'] = db_rule.limit_max
            
            merged_rules.append(template)

        self.tool_call_rules = merged_rules
        
        self._define_general_rules()

    def _define_general_rules(self):
        """Defines non-tool-specific limiting rules."""
        limit = self.agentInstance.limit_max_conversation_messages
        
        self.general_rules = {
            'messages_dont_warn_forget': max(4, limit * 0.80) # Warn for the last 20% or 4 messages
        }

    def is_tool_call_limited(self, toolcall, message):
        """Checks if a specific tool call should be excluded based on the defined rules."""
        for rule in self.tool_call_rules:
            if rule['match'](toolcall):
                rule_name = rule['name']
                item_key = rule['key'](toolcall)
                limits = rule['limits']

                # Initialize counters if they don't exist
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
