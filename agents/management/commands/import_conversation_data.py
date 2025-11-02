import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from agents.models.conversation_message import ConversationMessage, ConversationMessagePart
from tools.calls.models.tool_call import ToolCall
from tools.calls.models.tool_response import ToolResponse
from core.models.prompt import PromptVariant

class Command(BaseCommand):
    help = 'Imports conversation data from a JSON backup into the ConversationMessagePart model.'

    def add_arguments(self, parser):
        parser.add_argument('backup_file', type=str, help='The path to the JSON backup file.')

    @transaction.atomic
    def handle(self, *args, **options):
        backup_file = options['backup_file']
        self.stdout.write(f"Starting import from {backup_file}...")

        try:
            with open(backup_file, 'r') as f:
                data_backup = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"Backup file not found at {backup_file}")
        except json.JSONDecodeError:
            raise CommandError(f"Could not decode JSON from {backup_file}")

        self.stdout.write("Deleting existing ConversationMessagePart objects to prevent duplicates...")
        ConversationMessagePart.objects.all().delete()
        self.stdout.write("Deletion complete.")

        parts_to_create = []
        total_messages = len(data_backup)
        processed_count = 0

        for msg_pk, raw_data_str in data_backup.items():
            processed_count += 1
            if (processed_count % 100 == 0):
                self.stdout.write(f"Processing message {processed_count}/{total_messages}...")

            try:
                # The raw_data field is a JSON string itself, so it must be parsed.
                inner_data_obj = json.loads(raw_data_str)
                parts_list = inner_data_obj.get('data', {}).get('parts', [])
                
                if not parts_list or not isinstance(parts_list, list):
                    continue

                msg_instance = ConversationMessage.objects.get(pk=int(msg_pk))

                for index, part_dict in enumerate(parts_list):
                    if not isinstance(part_dict, dict):
                        continue

                    # Extract IDs for foreign key relationships
                    tc_id = part_dict.get('tcId')
                    tr_id = part_dict.get('trId')
                    tp_id = part_dict.get('tpId')
                    cm_id = part_dict.get('cmId')

                    tool_call_instance = None
                    tool_response_instance = None
                    prompt_variant_instance = None
                    conversation_message_instance = None
                    if tc_id:
                        try:
                            tool_call_instance = ToolCall.objects.get(pk=int(tc_id))
                        except (ToolCall.DoesNotExist, ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f"ToolCall with pk={tc_id} not found for msg {msg_pk}. Skipping link."))
                    
                    if tr_id:
                        try:
                            tool_response_instance = ToolResponse.objects.get(pk=int(tr_id))
                        except (ToolResponse.DoesNotExist, ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f"ToolResponse with pk={tr_id} not found for msg {msg_pk}. Skipping link."))

                    if tp_id:
                        try:
                            prompt_variant_instance = PromptVariant.objects.get(pk=int(tp_id))
                        except (PromptVariant.DoesNotExist, ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f"PromptVariant with pk={tp_id} not found for msg {msg_pk}. Skipping link."))
                    if cm_id:
                        try:
                            conversation_message_instance = ConversationMessage.objects.get(pk=int(cm_id))
                        except (PromptVariant.DoesNotExist, ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f"ConversationMessage with pk={cm_id} not found for msg {msg_pk}. Skipping link."))
                    
                    # The rendering logic is complex; for the migration, we store the raw part
                    # and a simple placeholder for the content. The real rendering will be
                    # handled by the application logic later.
                    placeholder_content = part_dict.get('content', '')

                    part_obj = ConversationMessagePart(
                        conversationMessage=msg_instance,
                        conversationMessage_reference=conversation_message_instance,
                        index=index,
                        content=placeholder_content, 
                        raw_part_data=part_dict,     # Store the complete original part dictionary
                        toolCall=tool_call_instance,
                        toolResponse=tool_response_instance,
                        promptVariant=prompt_variant_instance,
                        created_at=msg_instance.created_at,
                        updated_at=msg_instance.updated_at,
                    )
                    parts_to_create.append(part_obj)

            except ConversationMessage.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"ConversationMessage with pk={msg_pk} not found. Skipping."))
            except json.JSONDecodeError:
                 self.stdout.write(self.style.WARNING(f"Could not parse raw_data JSON string for message pk={msg_pk}. Skipping."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"An unexpected error occurred for message pk={msg_pk}: {e}"))
        
        if parts_to_create:
            self.stdout.write(f"Bulk creating {len(parts_to_create)} new ConversationMessagePart objects...")
            ConversationMessagePart.objects.bulk_create(parts_to_create, batch_size=500)

        self.stdout.write(self.style.SUCCESS("Import complete."))
