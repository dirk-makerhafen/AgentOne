import json
import os
from django.contrib.auth.models import User
from agents.models.agent_instance import AgentInstance
from ui.router import register_handler
from agents.models.agent_instance_fork import AgentInstanceFork

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


def build_fork_tree(instances, forks):
    """
    Builds a tree structure from instances based on fork relationships.
    """
    instance_map = {inst['id']: {**inst, 'type': 'instance', 'name': inst['name'] or f"Instance {inst['id']}", 'children': []} for inst in instances}
    
    root_nodes = []
    
    # Create a set of all child instance IDs for quick lookup
    child_ids = {fork.child_instance.pk for fork in forks}

    for fork in forks:
        parent = instance_map.get(fork.parent_instance.pk)
        child = instance_map.get(fork.child_instance.pk)
        if parent and child:
            parent['children'].append(child)

    # Any instance that is not a child in any fork relationship is a root node
    for inst_id, instance_node in instance_map.items():
        if inst_id not in child_ids:
            root_nodes.append(instance_node)
            
    return root_nodes

@register_handler('instance_view_get_by_fork')
def handle_instance_view_get_by_fork(consumer, **kwargs):
    try:
        user = User.objects.get(pk=consumer.user_pk)
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {consumer.user_pk} not found.'}))
        return

    instances = AgentInstance.objects.filter(agent__owners=user)
    instance_list = [instance.as_client_dict() for instance in instances]
    
    forks = AgentInstanceFork.objects.filter(parent_instance__in=instances, child_instance__in=instances).select_related('parent_instance', 'child_instance')

    tree_data = build_fork_tree(instance_list, forks)

    consumer.send(text_data=json.dumps({'object': 'AgentInstanceView', 'view_type': 'fork', 'data': tree_data}))
