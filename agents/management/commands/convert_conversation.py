import json
from django.core.management.base import BaseCommand
from agents.models.conversation_message import ConversationMessage, ConversationMessagePart
from agents.models.llm_query import LLMQuery, QueryMessage, QueryMessagePart
from core.models.prompt_variant import PromptVariant
from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
from tools.calls.models.tool_call import ToolCall
from tools.calls.models.tool_response import ToolResponse

class Command(BaseCommand):
    help = 'convert foo'

    def handle(self, *args, **options):
        self.stdout.write("Starting conversion")
        for obj in [QueryMessage, QueryMessagePart, ConversationMessagePart]:
            c = obj.objects.all().count()
            while c > 0:
                ids = obj.objects.all()[:5000].values_list('id')
                obj.objects.filter(pk__in=ids).delete()
                c -= 5000
       
        toolCall_cache = {f.pk:f for f in ToolCall.objects.all()}

        conversationMessages = ConversationMessage.objects.all()
        total = conversationMessages.count()
        cnt=0
        for conversationMessage in conversationMessages:
            if cnt%100==0:
                print(f"{cnt} of {total} done")
            cnt+=1
            for index, conversationMessageDict in enumerate(conversationMessage.data.get("parts",[])):
                cmp = ConversationMessagePart()
                cmp.conversationMessage = conversationMessage
                cmp.index = index
                cmp.content = conversationMessageDict["content"]
                if "tcId" in conversationMessageDict:
                    cmp.toolCall = toolCall_cache[conversationMessageDict["tcId"]]  
                cmp.save(send_to_client=False)

        llmQueries = LLMQuery.objects.all()        
        total = llmQueries.count()
        cnt=0
        fsLogEntry_cache = {f.pk:f for f in FsLogEntry.objects.all()}
        toolResponse_cache = {f.pk:f for f in ToolResponse.objects.all()}
        PromptVariant_cache =  {f.pk:f for f in PromptVariant.objects.all()}
        conversationMessage_cache =  {f.pk:f for f in ConversationMessage.objects.all()}
        conversationMessagePart_cache =  {f"{f.conversationMessage_id}_{f.index}":f for f in ConversationMessagePart.objects.all()}
        print("fsLogEntry_cache", len(fsLogEntry_cache))
        print("toolCall_cache", len(toolCall_cache))
        print("toolResponse_cache", len(toolResponse_cache))
        print("PromptVariant_cache", len(PromptVariant_cache))
        print("conversationMessage_cache", len(conversationMessage_cache))
        print("conversationMessagePart_cache", len(conversationMessagePart_cache))
        
        for llmQuery in llmQueries:
            agentInstance = llmQuery.agentInstance
            agent = llmQuery.agent
            llmQuery.tags_token_usage = llmQuery.data.get("usage", {})
            llmQuery.save(send_to_client=False)
            if cnt % 100 == 0:
                print(f"{cnt} of {total} done")
            cnt+=1
            for index1, message in enumerate(llmQuery.data.get("messages", [])):
                queryMessage = QueryMessage()
                queryMessage.agent = agent
                queryMessage.agentInstance = agentInstance
                queryMessage.llmQuery = llmQuery
                queryMessage.role = message["role"]
                queryMessage.tokens = message.get("tokens",0)
                queryMessage.index = index1
                if message.get("warn_forget", False) is True:
                    queryMessage.content_prefix =  f"@@@TO_BE_FORGOTTEN@@@"
                queryMessage.save(send_to_client=False)
                for index2, queryMessagePartDict in enumerate(message.get("parts",[])):
                    cmp = QueryMessagePart()
                    cmp.index = index2
                    cmp.queryMessage = queryMessage
                    cmp.tokens =  queryMessagePartDict.get("tokens",0)
                    cmp.content = queryMessagePartDict.get("content", None)
                    cmp.tags =  queryMessagePartDict.get("tags",[])
                    cmp.template_data = queryMessagePartDict.get("data",{})
                    if queryMessagePartDict.get("warn_forget", False) is True:
                        cmp.content_prefix =  f"@@@TO_BE_FORGOTTEN@@@"
                    if "tcId" in queryMessagePartDict:
                        cmp.toolCall = toolCall_cache[queryMessagePartDict["tcId"]]
                    if "trId" in queryMessagePartDict:
                        cmp.toolResponse = toolResponse_cache[queryMessagePartDict["trId"]]
                    if "tpId" in queryMessagePartDict:
                        try:
                            cmp.promptVariant = PromptVariant_cache[queryMessagePartDict["tpId"]]
                        except:
                            pass
                    if "cmId" in queryMessagePartDict and "pnr" in queryMessagePartDict:
                        cmp.conversationMessage = conversationMessage_cache[queryMessagePartDict["cmId"]]
                        key = f'{queryMessagePartDict["cmId"]}_{queryMessagePartDict["pnr"]}'
                        try:
                            cmp.conversationMessagePart = conversationMessagePart_cache[key]
                        except:
                            pass
                    if "data" in queryMessagePartDict and "fs_content_type" in queryMessagePartDict["data"]:
                        cmp.fsLogEntry = fsLogEntry_cache[int(queryMessagePartDict["data"]["fs_content_id"])] 
                        #del cmp.template_data["fs_content_type"]
                        #del cmp.template_data["fs_content_id"]
                    #for key in ["tokens", "content", "tags", "data", "warn_forget", "tcId", "trId", "tpId", "cmId", "pnr"]:
                    #    if key in queryMessagePartDict:
                    #        del queryMessagePartDict[key]
                    #if queryMessagePartDict.keys():
                    #   print("queryMessagePartDict", queryMessagePartDict)
                    cmp.save(send_to_client=False)
                #for key in ["role", "tokens", "warn_forget", "parts"]:
                #    if key in message:
                #        del message[key]
                #if message.keys():
                #    print("queryMessagePartDict", message)
