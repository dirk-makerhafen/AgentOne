from pathlib import Path

def _parse_rules(rules_text):
    """
    Parses the access_rules text into a list of tuples.
    Each tuple contains (is_negated, permission_type, pattern).
    """
    parsed_rules = []
    for line in rules_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line[0] not in ["!", "<", ">"]:
            continue
        parsed_rules.append({'permission': line[0], 'pattern': line[1:].strip()})
    return parsed_rules

def _matches(path, pattern):
    """
    Checks if a given path matches a glob-style pattern.
    Handles directory matching (pattern ending in '/').
    """
    path = Path(path)
    if pattern.endswith('/'):
        # It's a directory pattern, check if the path is within that directory or is the directory itself
        return Path(pattern[:-1]) in path.parents or path == Path(pattern[:-1])
    else:
        # It's a file pattern
        return path.match(pattern)

def check_permission(session_version, absolute_path, action):
    """
    Checks if an agent instance has permission to perform an action on a given path.

    Args:
        agent_instance (AgentVersion): The agent instance.
        absolute_path (str): The absolute path to the file or directory.
        action (str): The action to perform ('read' or 'write').

    Returns:
        bool: True if the action is permitted, False otherwise.
    """
    # Normalize paths to handle OS differences
    working_dir = Path(session_version.workingdir).resolve()
    target_path = Path(absolute_path).resolve()

    '''
    # ---  Check Fine-Grained Rules First ---
    rules = _parse_rules(agent_instance.access_rules)
    # Rules are checked in order like iptables rules
    for rule in rules:
        print("RULE", rule)
        # We need to check against the relative path if the rule is relative,
        # or absolute if the rule is absolute. For simplicity, we'll assume
        # rules are relative to the working directory.
        try:
            relative_target_path = target_path.relative_to(working_dir)
            path_to_check = str(relative_target_path)
        except ValueError:
            path_to_check = absolute_path
        if path_to_check and _matches(path_to_check, rule['pattern']):
            if rule['permission'] == '!': # deny
                return False   
            if action == "read":
                return True
            if action == "write" and rule['permission'] == '>':
                return True
            return False
    '''
    # ---  Apply Default Permissions (if no rule matched) ---
    is_inside_workingdir = working_dir in target_path.parents or target_path == working_dir

    if is_inside_workingdir:
        if action == 'read':
            return True  # Read access is implicitly granted inside working directory
        if action == 'write':
            return True # TODO
            return session_version.workingdir_write_allowed # Write access depends on the flag
    
    # Path is outside working directory, but not handeld in rules, so deny
    return False
    