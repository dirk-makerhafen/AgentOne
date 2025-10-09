from datetime import datetime
import math

from core.models.prompt_string import PromptString
from tools.base.base_tool import BaseTool
from .models.memory_item import MemoryItem
from .prompts import FUNCTIONS, TRACKS
from .apps import ToolsBuiltinMemoryConfig

class MemoryTool(BaseTool):
    DESCRIPTION = "Accesses a persistent, structured memory system with multiple tracks (e.g., plans, insights) and time horizons. Crucial for retaining context, learning from past actions, and managing long-term goals."
    functions = FUNCTIONS
    
    @property
    def tracks(self):
        return [f'{k}' for k in TRACKS.keys()]

    def get_header_parts(self):
        instructionsTemplate = PromptString.get_template(self.agentInstance, source=ToolsBuiltinMemoryConfig.name, key="Instructions")
        functionsTemplate = PromptString.get_template(self.agentInstance, source=ToolsBuiltinMemoryConfig.name, key="Functions")
        return [
            {"tpId": instructionsTemplate.pk, "data": {}, 'tags': ['Prompts', 'Memory'] },
            {"tpId": functionsTemplate.pk, "data": {}, 'tags': ['Prompts', 'Memory'] },
        ]
    
    def get_content_parts(self):
        memoryContentHeaderPrompt = PromptString.get_template(self.agentInstance, source=ToolsBuiltinMemoryConfig.name, key="ContentHeader")       
        parts = [
            {"tpId": memoryContentHeaderPrompt.pk, "data": { "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, 'tags': ['Prompts', 'Memory'] }, 
        ] 
     
        memory = {}
        limit = self.agentInstance.limit_max_memory_items
        for trackname, trackitem in TRACKS.items():
            memory[trackname] = {}
            for layername, layerdesription in trackitem['layers'].items():      
                memory[trackname][layername] = {
                    "memories":sorted([{ "tackname": trackname, "layername": layername, "created_at":x.created_at.timestamp(), "pk":x.pk, "index": x.index} for x in MemoryItem.objects.filter(track=trackname, layer=layername, next_version=None, agentInstance=self.agentInstance).order_by('-index')[:limit]],key=lambda v:v["index"]),
                }
        _l = []
        for trackname, trackitem in TRACKS.items():
            _l.extend([x["created_at"] for x in memory[trackname]["ST"]["memories"]])
        avg_st_update_ts = sum(_l) / len(_l) if len(_l) > 0 else 0
        
        stalled = []
        for trackname, trackitem in TRACKS.items():
            
            try: # warn outdated ST layer
                newest_st_entry = sorted(memory[trackname]["ST"]["memories"], key=lambda x:x.created_at,reverse=True)[0]
                if newest_st_entry.created_at.timestamp() < avg_st_update_ts:
                    memory[trackname]["ST"]["warn_stall"] = True
            except:
                pass
            try: # warn outdated MT layer
                oldest_st_entry = sorted(memory[trackname]["ST"]["memories"], key=lambda x:x.created_at)[0]
                newest_mt_entry = sorted(memory[trackname]["MT"]["memories"], key=lambda x:x.created_at, reverse=True)[0]
                if newest_mt_entry.created_at < oldest_st_entry.created_at:
                    memory[trackname]["MT"]["warn_stall"] = True
            except:
                pass
            try: # warn outdated LT layer
                oldest_mt_entry = sorted(memory[trackname]["MT"]["memories"], key=lambda x:x.created_at)[0]
                newest_lt_entry = sorted(memory[trackname]["LT"]["memories"], key=lambda x:x.created_at, reverse=True)[0]
                if newest_lt_entry.created_at < oldest_mt_entry.created_at:
                    memory[trackname]["LT"]["warn_stall"] = True
            except:
                pass
            if len(memory[trackname]["ST"]["memories"]) == 0:
                memory[trackname]["ST"]["warn_stall"] = True
            if len(memory[trackname]["ST"]["memories"]) >= limit * 0.9 and len(memory[trackname]["MT"]["memories"]) == 0:
                memory[trackname]["MT"]["warn_stall"] = True
            if len(memory[trackname]["MT"]["memories"]) >= limit * 0.9 and len(memory[trackname]["LT"]["memories"]) == 0:
                memory[trackname]["LT"]["warn_stall"] = True
            for layername, layerdesription in trackitem['layers'].items():
                if len(memory[trackname][layername]["memories"]) >= limit * 0.9:
                    for i in range(max(math.ceil(limit * 0.15), 3)):
                        memory[trackname][layername]["memories"][i]["warn_forget"] = True
                for m in memory[trackname][layername]["memories"]: # clean to save storage later, create_at is not needed anymore
                    del m["created_at"]
            if memory[trackname].get("ST",{}).get("warn_stall", False) is True:
                stalled.append([trackname, "ST"])  
            if memory[trackname].get("MT",{}).get("warn_stall", False) is True:
                stalled.append([trackname, "MT"])  
            if memory[trackname].get("LT",{}).get("warn_stall", False) is True:
                stalled.append([trackname, "LT"])  

        memoryContentPrompt = PromptString.get_template(self.agentInstance, source=ToolsBuiltinMemoryConfig.name, key="Content")

        for trackname, trackitem in TRACKS.items():
            trackHeaderPrompt = PromptString.get_template(self.agentInstance, source=ToolsBuiltinMemoryConfig.name, key= f"ContentHeader.{trackname}")
            parts.append({
                "tpId": trackHeaderPrompt.pk, 
                'tags': ['Prompts', 'Memory', trackname] 
            }) 
            for layername, layerdesription in trackitem['layers'].items():
                layerHeaderPrompt = PromptString.get_template(self.agentInstance, source=ToolsBuiltinMemoryConfig.name, key= f"ContentHeader.{trackname}.{layername}")
                parts.append({
                    "tpId": layerHeaderPrompt.pk, 
                    'tags': ['Prompts', 'Memory', trackname, layername] 
                }) 
                parts.append({
                    'tags': ['Tool', 'MemoryTool', 'Content', f'{trackname}', f'{layername}'],
                    "tpId": memoryContentPrompt.pk, 
                    "data":  memory[trackname][layername],
                })

        if len(stalled) > 0:
            stalledWarningHeader = PromptString.get_template(self.agentInstance, source=ToolsBuiltinMemoryConfig.name, key="StalledWarning")
            parts.append({
                'tags': ['Prompts', 'Memory'],
                "tpId": stalledWarningHeader.id, 
                "data": {"stalled": stalled},
            })
            
        return parts

    def get(self, track, layer, limit=20):
        existing_entries = MemoryItem.objects.filter(track=track, layer=layer, next_version=None, agentInstance=self.agentInstance).order_by('-index')[:limit * 3]
        r = []
        for existing_entry in existing_entries:
            if existing_entry.value != '':
                r.append({'index': existing_entry.index, 'content': existing_entry.value, 'toolCall': existing_entry.toolCall, 'MemoryItem__id': existing_entry.pk})
            if len(r) >= limit:
                break
        return reversed(r)

    def memory_add(self, toolCall, track, layer, content):
        new_item = self._memory_add(toolCall=toolCall, track=track, layer=layer, content=content)
        return (True, {})

    def memory_correct(self, toolCall, track, layer, index, content):
        existing_entry = MemoryItem.objects.filter(track=track, layer=layer, next_version=None, index=int(index), agentInstance=self.agentInstance).first()
        if not existing_entry:
            return (False, {'status': 'error', 'message': 'Memory item not found'})
        if existing_entry.value == content:
            return False, {"status":"warning", "message": "Memory content not changed. Be carefull when using memory_correct, dont call memory_correct when the memory content does not need correction."}
        content_stripped = content.strip()
        if content_stripped.startswith('[') and content_stripped.endswith(']'):
            return False, {"status":"warning", "message": "Don't overwrite old memory items. Add tags if you need, but don't overwrite memories."}

        newmi = MemoryItem()
        newmi.agent = self.agentInstance.agent
        newmi.agentInstance = self.agentInstance
        newmi.toolCall = toolCall
        newmi.track = track
        newmi.layer = layer
        newmi.value = content
        newmi.index = existing_entry.index
        newmi.save(send_to_client=False)
        existing_entry.next_version = newmi
        existing_entry.save(send_to_client=False)
        return (True, {})

    def memory_reposition(self, toolCall, track, layer, index, steps):
        if steps == 0:
            return (True, {})
        min_index = int(index) if steps > 0 else int(index) + steps
        existing_entries = MemoryItem.objects.filter(track=track, layer=layer, next_version=None, index__gte=min_index, agentInstance=self.agentInstance).order_by('index')
        existing_entries = [x for x in existing_entries]
        if len(existing_entries) == 0:
            return (False, {'status': 'error', 'message': 'Memory item not found'})
        if len([x for x in existing_entries if x.index == index]) == 0:
            return (False, {'status': 'error', 'message': 'Memory item with this index does not exist'})
        if len(existing_entries) == 1:
            return (True, {})
        if steps > 0:
            to_update = [x for x in existing_entries[1:]]
            to_update.insert(steps, existing_entries[0])
        elif steps < 0:
            to_update = [x for x in existing_entries]
            item = to_update.pop(abs(steps))
            to_update.insert(0, item)
        for offset, item in enumerate(to_update):
            newmi = MemoryItem()
            newmi.agent = self.agentInstance.agent
            newmi.agentInstance = self.agentInstance
            newmi.toolCall = toolCall
            newmi.track = track
            newmi.layer = layer
            newmi.value = item.value
            newmi.index = min_index + offset
            newmi.save(send_to_client=False)
            original_item = next((x for x in existing_entries if x.id == item.id), None)
            if original_item:
                original_item.next_version = newmi
                original_item.save(send_to_client=False)
            
        return (True, {})

    def _memory_add(self, toolCall, track, layer, content):
        latest_entry = MemoryItem.objects.filter(track=track, layer=layer, next_version=None, agentInstance=toolCall.agentInstance).order_by('-index').first()
        mi = MemoryItem()
        mi.agent = toolCall.agent
        mi.agentInstance = toolCall.agentInstance
        mi.conversationMessage = toolCall.conversationMessage
        mi.toolCall = toolCall
        mi.track = track
        mi.layer = layer
        mi.value = content
        mi.index = latest_entry.index + 1 if latest_entry else 0
        mi.save(send_to_client=False)
        return mi

    def get_history_limiting_rules(self):
        limit = self.agentInstance.limit_max_conversation_messages
        return [
            {
                'group_name': "Memory",
                'name': 'function,track,layer',
                'description': 'Limits history on a per-function, per-track, and per-layer basis (most specific).',
                'match': lambda tc: tc.function_name.startswith('memory_'),
                'key': lambda tc: (tc.function_name, tc.arguments.get('track'), tc.arguments.get('layer')),
                'limits': {'pending': limit, 'success': 1, 'failed': 2, 'max': 3}
            },{
                'group_name': "Memory",
                'name': 'function,track',
                'description': 'Limits history on a per-function and per-track basis.',
                'match': lambda tc: tc.function_name.startswith('memory_'),
                'key': lambda tc: (tc.function_name, tc.arguments.get('track')),
                'limits': {'pending': limit, 'success': 2, 'failed': 2, 'max': 3}
            },{
                'group_name': "Memory",
                'name': 'function',
                'description': 'Limits history on a per-function basis (e.g., memory_add).',
                'match': lambda tc: tc.function_name.startswith('memory_'),
                'key': lambda tc: (tc.function_name,),
                'limits': {'pending': limit, 'success': 5, 'failed': 2, 'max': 5}
            },{
                'group_name': "Memory",
                'name': 'any',
                'description': 'A general fallback limit for all memory operations.',
                'match': lambda tc: tc.function_name.startswith('memory_'),
                'key': lambda tc: '',
                'limits': {'pending': limit, 'success': 10, 'failed': 2, 'max': 10}
            }
        ]
