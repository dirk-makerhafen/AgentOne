from core.models.prompt_string import Prompt
from tools.primitives import run_python_code
from tools.base.base_tool import BaseTool
from tools.builtin_python.models.python_tool_var import PythonToolVar
from tools.builtin_subscriptions.models.tool_subscription import ToolSubscription
from .prompts import TOOLS, PROMPTS
from .apps import ToolsBuiltinPythonConfig

class PythonTool(BaseTool):
    DESCRIPTION = "Provides a Python execution environment. Allows the agent to run code for calculations, data manipulation, and complex logic, with access to a persistent 'VARS' dictionary for state management."
    TOOLS = TOOLS
    PROMPTS = PROMPTS

    def get_header_parts(self):
        instructionsTemplate = Prompt.get_template(self.agentInstance, source=ToolsBuiltinPythonConfig.name, key="instructions")
        functionsTemplate = Prompt.get_template(self.agentInstance, source=ToolsBuiltinPythonConfig.name, key="functions")
        #sharedVarsInjection = Prompt.get_template(self.agentInstance, source=ToolsBuiltinPythonConfig.name, key="list_of_shared_vars")
        existing_vars = PythonToolVar.objects.filter(agentInstance=self.agentInstance, next_version=None).order_by('-created_at')[:20]
        return [
            {"tpId": instructionsTemplate.pk, "tags": ["Prompts", "Python"], "data": {} },
            {"tpId": functionsTemplate.pk  , "tags": ["Prompts", "Python"], "data": {} },
            #{"tpId": sharedVarsInjection.pk, "tags": ['Tool', 'Python', 'Vars']       , "data": {"keys": [v.key for v in existing_vars]}}
        ]
        
    def python(self, source, mode="one-shot", subscription_id=None, toolCall=None):
        if mode == "subscribe":
            if not subscription_id:
                return (False, {"status": "error", "message": "A unique 'subscription_id' is required when mode is 'subscribe'."})

            ToolSubscription.objects.update_or_create(
                agentInstance=self.agentInstance,
                subscription_id=subscription_id,
                defaults={
                    'agent': self.agentInstance.agent,
                    'creating_tool_call': toolCall,
                    'tool_name': 'python',
                    'arguments': { "source": source },
                    'is_active': True
                }
            )

        existing_vars = PythonToolVar.objects.filter(agentInstance=self.agentInstance, next_version=None).order_by('-created_at')
        original_vars = {}
        for existing_var in existing_vars:
            if not existing_var.data.get('deleted', False):
                original_vars[existing_var.key] = existing_var.value

        result = run_python_code(agentInstance=self.agentInstance, python_code_string=source, locals_dict={'VARS': original_vars}, locals_to_return=["VARS"], workingdir=self.agentInstance.workingdir)
        
        returned_vars = result.get("vars",{})
        if "VARS" in returned_vars and len(returned_vars["VARS"]) == 0:
            del returned_vars["VARS"]
        if "vars" in result and len(result["vars"]) == 0:
            del result["vars"]
        
        updated_var_names = self.handle_results_vars(original_vars, result.get("vars",{}).get("VARS",{}), toolCall)
        if updated_var_names:
            result['updated_vars'] = list(updated_var_names)

        if mode == "subscribe":
            if "message" not in result:
                result["message"] = ""
            result["message"] += f"\nSuccessfully created/updated subscription with ID '{subscription_id}'."

        return ( result.get("status")=="success", result)

    def handle_results_vars(self, original_vars, current_vars, toolCall):
        updated_var_names = set()        
        so = set(original_vars.keys())
        sc =  set(current_vars.keys())
        new_vars = []
        removeds = so - sc
        addeds = sc - so
        for removed in removeds:
            new_vars.append(["delete", removed, None])
        for added in addeds:
            new_vars.append(["added", added,  current_vars[added]])
        for updated in sc - addeds - removeds:
            if not self._deep_equals(original_vars[updated], current_vars[updated]):
                new_vars.append(["updated", updated, current_vars[updated]])
        for new_var in new_vars:
            action, key, value = new_var
            updated_var_names.add(key)
            latest_var_entry = PythonToolVar.objects.filter(agentInstance=self.agentInstance, key=key, next_version=None).first()
            new_var_entry = PythonToolVar(
                agent=self.agentInstance.agent, 
                agentInstance=self.agentInstance, 
                key=key, action=action, toolCall=toolCall,
            )
            new_var_entry.value = value
            new_var_entry.save(send_to_client=False)
            if latest_var_entry:
                latest_var_entry.next_version = new_var_entry
                latest_var_entry.save(send_to_client=False)
            new_var_entry.save(send_to_client=True)
        return updated_var_names

    def _is_python_with_no_output_and_no_vars(self, toolcall):
        if toolcall.function_name != 'python':
            return False
        tool_response = toolcall.toolResponses.last()
        if not tool_response:
            return False
        return not tool_response.data.get('stdout', '').strip() and (not tool_response.data.get('stderr', '').strip()) and (not tool_response.data.get('updated_vars'))

    def _is_python_with_no_output_and_var(self, toolcall):
        if toolcall.function_name != 'python':
            return False
        tool_response = toolcall.toolResponses.last()
        if not tool_response:
            return False
        return not tool_response.data.get('stdout', '').strip() and (not tool_response.data.get('stderr', '').strip()) and tool_response.data.get('updated_vars')

    def get_history_limiting_rules(self):
        limit = self.agentInstance.effective_limit_max_conversation_messages
        return [
            {'group_name': "Python", 'name': 'any', 'description': 'General limit for all python tool calls.', 'match': lambda tc: tc.function_name == 'python', 'key': lambda tc: '', 'limits': {'pending': limit, 'success': limit, 'failed': 3, 'max': limit}},
            {'group_name': "Python", 'name': 'nooutput,novars', 'description': 'Limit for python calls that produced no output and did not change any VARS.', 'match': self._is_python_with_no_output_and_no_vars, 'key': lambda tc: '', 'limits': {'pending': limit, 'success': 5, 'failed': 3, 'max': 8}},
            {'group_name': "Python", 'name': 'nooutput', 'description': 'Limit for python calls that only changed VARS but produced no other output.', 'match': self._is_python_with_no_output_and_var, 'key': lambda tc: '', 'limits': {'pending': limit, 'success': 5, 'failed': 3, 'max': 8}}
        ]

    def _deep_equals(self, val1, val2):
        if type(val1) is not type(val2):
            return False
        if isinstance(val1, dict):
            if set(val1.keys()) != set(val2.keys()):
                return False
            for key in val1:
                if not self._deep_equals(val1[key], val2[key]):
                    return False
            return True
        if isinstance(val1, (list, tuple)):
            if len(val1) != len(val2):
                return False
            for item1, item2 in zip(val1, val2):
                if not self._deep_equals(item1, item2):
                    return False
            return True
        return val1 == val2
