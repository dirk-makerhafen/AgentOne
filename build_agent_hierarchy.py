
import os
import django
import sys
import argparse


# --- Django Setup ---
# Add the project root to the Python path to allow script to be run from anywhere.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

# Set the DJANGO_SETTINGS_MODULE environment variable.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error setting up Django: {e}")
    print("Please ensure you run this script from the root of your Django project,")
    print("and that the project structure is correct.")
    sys.exit(1)
# --- End Django Setup ---

from django.db import transaction
from agents.models.agent import Agent
from agents.models.agent_instance import AgentInstance
from agents.models.sub_agent_link import SubAgentLink

from tools.calls.models.tool_call import ToolCall

# --- Configuration ---
# Use the PK of the "Default SubAgent Template"
DEFAULT_AGENT_TEMPLATE_PK = 4 

def send_initial_message(agent_instance, tool_name, arguments):
    """Creates and queues an initial tool call for a new agent."""
    print(f"    - Queuing initial message for agent {agent_instance.instance_pk}: {tool_name}({arguments})")
    ToolCall.objects.create(
        agentInstance=agent_instance,
        agent=agent_instance.agent,
        tool_name=tool_name,
        arguments=arguments,
        status='pending' # The agent will pick this up on its next cycle
    )

@transaction.atomic
def sync_agent_hierarchy(parent_agent):
    """
    Recursively synchronizes the agent hierarchy with the filesystem.
    Ensures one agent exists for each file and subdirectory.
    """
    print(f"\n--- Syncing children for Agent {parent_agent.instance_pk} ('{parent_agent.name}') in '{parent_agent.workingdir}' ---")

    # 1. Validate parent agent's working directory
    if not parent_agent.workingdir or not os.path.isdir(parent_agent.workingdir):
        print(f"  [ERROR] Agent {parent_agent.instance_pk} has an invalid or non-existent working directory: '{parent_agent.workingdir}'. Skipping.")
        return

    # 2. Get current state from filesystem and database
    try:
        fs_items = {item for item in os.listdir(parent_agent.workingdir)}
    except OSError as e:
        print(f"  [ERROR] Could not read directory '{parent_agent.workingdir}': {e}. Skipping.")
        return
        
    child_agents = [x.subordinate_instance for x in parent_agent.subordinates.all()]
    agents_by_name = {agent.name: agent for agent in child_agents}

    # 3. Create sets for efficient lookup
    # Filesystem sets
    fs_dirs = {item for item in fs_items if os.path.isdir(os.path.join(parent_agent.workingdir, item))}

    fs_files = fs_items - fs_dirs

    # Agent sets (based on naming convention)
    agent_managed_dirs = {name.replace('Supervisor: ', ''): agent for name, agent in agents_by_name.items() if name.startswith('Supervisor: ')}
    agent_managed_files = {name.replace('File Agent: ', ''): agent for name, agent in agents_by_name.items() if name.startswith('File Agent: ')}

    # 4. Create missing agents and correct existing ones
    agent_template = Agent.objects.get(pk=DEFAULT_AGENT_TEMPLATE_PK)

    # Sync Directories
    for dir_name in fs_dirs:
        if dir_name.startswith("."):
            continue
        if ".git" in dir_name:
            continue
        if "__pycache__" in dir_name:
            continue
        if "3party" in dir_name:
            continue
        dir_path = os.path.join(parent_agent.workingdir, dir_name)
        if dir_name not in agent_managed_dirs:
            print(f"  [CREATE] Creating agent for directory: {dir_name}")
            new_agent = AgentInstance.objects.create(
                agent=agent_template,
                name=f"Supervisor: {dir_name}",
                description_text=f"Manages the {dir_path} directory.",
                workingdir=dir_path
            )
            SubAgentLink.objects.create(supervisor_instance=parent_agent, subordinate_instance=new_agent)
            send_initial_message(new_agent, 'fs_load', {'path': '.'})
            sync_agent_hierarchy(new_agent) # Recurse immediately
        else:
            # Agent exists, ensure workingdir is correct and recurse
            existing_agent = agent_managed_dirs[dir_name]
            if existing_agent.workingdir != dir_path:
                print(f"  [CORRECT] Updating workingdir for agent {existing_agent.instance_pk} to '{dir_path}'")
                existing_agent.workingdir = dir_path
                existing_agent.save()
            sync_agent_hierarchy(existing_agent) # Recurse

    # Sync Files
    for file_name in fs_files:
        
        if file_name not in agent_managed_files:
            print(f"  [CREATE] Creating agent for file: {file_name}")
            new_agent = AgentInstance.objects.create(
                agent=agent_template,
                name=f"File Agent: {file_name}",
                description_text=f"Manages the file {file_name} in {parent_agent.workingdir}.",
                workingdir=parent_agent.workingdir # File agents inherit parent's workingdir
            )
            SubAgentLink.objects.create(supervisor_instance=parent_agent, subordinate_instance=new_agent)

            send_initial_message(new_agent, 'fs_load', {'path': file_name})
            
    # 5. Delete orphaned agents
    orphaned_dir_agents = set(agent_managed_dirs.keys()) - fs_dirs
    for dir_name in orphaned_dir_agents:
        agent_to_delete = agent_managed_dirs[dir_name]
        print(f"  [DELETE] Deleting orphaned agent {agent_to_delete.instance_pk} for non-existent directory: {dir_name}")
        agent_to_delete.delete() # Cascading delete will handle children

    orphaned_file_agents = set(agent_managed_files.keys()) - fs_files
    for file_name in orphaned_file_agents:
        agent_to_delete = agent_managed_files[file_name]
        print(f"  [DELETE] Deleting orphaned agent {agent_to_delete.instance_pk} for non-existent file: {file_name}")
        agent_to_delete.delete()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recursively build and synchronize the agent hierarchy based on the filesystem.")
    parser.add_argument('--root-agent', type=int, required=True, help="The primary key of the root agent instance to start from.")
    args = parser.parse_args()

    try:
        root_agent = AgentInstance.objects.get(pk=args.root_agent)
    except AgentInstance.DoesNotExist:
        print(f"Error: AgentInstance with pk={args.root_agent} not found.")
        sys.exit(1)
        
    print(f"Starting agent hierarchy synchronization from root agent {root_agent.instance_pk}...")
    sync_agent_hierarchy(root_agent)
    print("\nSynchronization complete.")
