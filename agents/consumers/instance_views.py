import json
import os
from django.contrib.auth.models import User
from agents.models.agent_instance import AgentInstance
from ui.router import register_handler
from agents.models.agent_instance_fork import AgentInstanceFork
from agents.models.sub_agent_link import SubAgentLink # Import the new model

def build_directory_tree(instances):
    """
    Builds a tree structure from a flat list of agent instances based on their workingdir.
    """
    tree = []
    # Create a map for quick access to nodes
    node_map = {'': {'name': '/', 'type': 'folder', 'children': []}}
    tree.append(node_map[''])

    for instance in instances:
        path = instance.get('workingdir', '').strip('/')
        parts = path.split('/') if path else []
        
        current_path_key = ''
        for part in parts:
            parent_node = node_map[current_path_key]
            current_path_key = f"{current_path_key}/{part}" if current_path_key else part
            
            child_node = node_map.get(current_path_key)
            if not child_node:
                child_node = {'name': part, 'type': 'folder', 'children': []}
                node_map[current_path_key] = child_node
                parent_node['children'].append(child_node)
        
        # Add the instance leaf node
        instance_node = {**instance, 'type': 'instance', 'name': instance['name'] or f"Instance {instance['id']}"}
        node_map[current_path_key]['children'].append(instance_node)
        
    return tree[0]['children'] # Return children of the root

@register_handler('instance_view_get_by_dir')
def handle_instance_view_get_by_dir(consumer, **kwargs):
    try:
        user = User.objects.get(pk=consumer.user_pk)
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
        return

    instances = AgentInstance.objects.filter(agent__owners=user).order_by('workingdir', 'name')
    instance_list = [instance.as_client_dict() for instance in instances]

    # Find and trim the common base path
    working_dirs = [inst.get('workingdir', '') for inst in instance_list if inst.get('workingdir', '')]
    common_base_path = os.path.commonprefix(working_dirs)

    trimmed_instance_list = []
    for inst in instance_list:
        trimmed_inst = inst.copy()
        if trimmed_inst.get('workingdir', ''):
            trimmed_inst['workingdir'] = os.path.relpath(trimmed_inst['workingdir'], common_base_path)
            if trimmed_inst['workingdir'] == '.':
                trimmed_inst['workingdir'] = ''
        trimmed_instance_list.append(trimmed_inst)

    tree_data = build_directory_tree(trimmed_instance_list)

    consumer.send(text_data=json.dumps({
        'object': 'AgentInstanceView', 
        'view_type': 'directory', 
        'data': tree_data,
        'common_base_path': common_base_path
    }))


def _build_unified_instance_hierarchy_tree(all_instances_data, forks, sub_agent_links):
    """
    Builds a hierarchical tree structure of agent instances, including
    both fork relationships and sub-agent relationships, suitable for recursive rendering.
    Each child node explicitly states its relationship type to its parent.
    """
    # Step 1: Initialize nodes with basic instance data
    # We create a deep copy for each instance to allow modification without affecting original
    # client dicts and to add new properties for tree building.
    instance_nodes = {
        inst['id']: {
            **inst,
            'children': [],       # Unified list of children for the template
            '_parent_links': [],  # Internal: tracks how this instance is a child of others
        } for inst in all_instances_data
    }

    # Step 2: Populate relationships (forks and sub-agents)
    # The 'children' list will store direct references to child node dictionaries,
    # and each child will be augmented with its relationship type to this specific parent.

    # Process Forks
    for fork in forks:
        parent_id = fork.parent_instance.pk
        child_id = fork.child_instance.pk

        if parent_id in instance_nodes and child_id in instance_nodes:
            # Add to parent's children, marking it as a fork relationship
            child_node_for_parent = {**instance_nodes[child_id], 'relationship_type': 'fork'}
            instance_nodes[parent_id]['children'].append(child_node_for_parent)
            
            # Record that this child has a parent (for root node detection)
            instance_nodes[child_id]['_parent_links'].append({'type': 'fork', 'parent_id': parent_id})

    # Process Sub-agent Links
    for link in sub_agent_links:
        supervisor_id = link.supervisor_instance.pk
        subordinate_id = link.subordinate_instance.pk

        if supervisor_id in instance_nodes and subordinate_id in instance_nodes:
            # Add to parent's children, marking it as a subagent relationship
            child_node_for_parent = {**instance_nodes[subordinate_id], 'relationship_type': 'subagent'}
            instance_nodes[supervisor_id]['children'].append(child_node_for_parent)

            # Record that this child has a parent
            instance_nodes[subordinate_id]['_parent_links'].append({'type': 'subagent', 'parent_id': supervisor_id})

    # Step 3: Identify Root Nodes
    # A node is a root if it has no parent links within the current set of instances being processed.
    root_nodes = []
    for inst_id, node in instance_nodes.items():
        is_actual_root = True
        for parent_link in node['_parent_links']:
            if parent_link['parent_id'] in instance_nodes: # If its parent is also in our current map, it's not a root
                is_actual_root = False
                break
        if is_actual_root:
            root_nodes.append(node)

    # Step 4: Recursively sort children within each node for consistent display
    # This will construct the final tree structure, ensuring that children lists
    # contain fully formed and sorted child dictionaries.

    final_tree = []
    processed_ids = set() # To prevent infinite recursion/reprocessing if a cycle somehow exists

    def build_subtree(node_dict):
        # Prevent re-adding the same node multiple times if it's referenced by different parents
        # This function should only be called once per unique node being added to the final_tree.
        # This is for the *output structure*, not the internal `instance_nodes` map.
        
        # Create a clean dictionary for the output, excluding internal metadata
        output_node = {
            'id': node_dict['id'],
            'name': node_dict['name'],
            'status': node_dict['status'],
            'status_display': node_dict['status_display'],
            'agent_id': node_dict['agent_id'],
            'agent_name': node_dict['agent_name'],
            'description_text': node_dict['description_text'],
            'workingdir': node_dict['workingdir'],
            'isSelected': node_dict.get('isSelected', False) # Preserve selection state
        }
        
        # If this node itself is a child in the hierarchy, include its relationship_type
        if 'relationship_type' in node_dict:
            output_node['relationship_type'] = node_dict['relationship_type']

        # Recursively build children
        output_node['children'] = []
        # Sort children of this node before processing them
        node_dict['children'].sort(key=lambda child: (child.get('relationship_type', 'instance'), child['name']))
        
        for child_source_node in node_dict['children']:
            child_output = build_subtree(child_source_node)
            if child_output:
                output_node['children'].append(child_output)
        
        return output_node

    # Build the tree starting from identified root nodes
    for root_node in root_nodes:
        tree_branch = build_subtree(root_node)
        if tree_branch:
            final_tree.append(tree_branch)
    
    # Final sort of top-level root nodes
    final_tree.sort(key=lambda node: node['name'])

    return final_tree


@register_handler('instance_view_get_by_fork')
def handle_instance_view_get_by_fork(consumer, **kwargs):
    try:
        user = User.objects.get(pk=consumer.user_pk)
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
        return

    instances = AgentInstance.objects.filter(agent__owners=user).prefetch_related('agent')
    instance_list_data = [instance.as_client_dict() for instance in instances]
    
    forks = AgentInstanceFork.objects.filter(
        parent_instance__agent__owners=user # Ensure we only consider forks where parent is owned by user
    ).select_related('parent_instance', 'child_instance')

    sub_agent_links = SubAgentLink.objects.filter(
        supervisor_instance__agent__owners=user # Ensure we only consider links where supervisor is owned by user
    ).select_related('supervisor_instance', 'subordinate_instance__agent')

    tree_data = _build_unified_instance_hierarchy_tree(instance_list_data, forks, sub_agent_links)

    consumer.send(text_data=json.dumps({'object': 'AgentInstanceView', 'view_type': 'fork', 'data': tree_data}))
