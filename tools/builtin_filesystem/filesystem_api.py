import traceback
import ast
import textwrap

from .models.fs_log_entry import FsLogEntry
from .utils.fsutils import clean_path, get_abs_path
from .utils.permissions import check_permission
from .utils.fuzzymatch import find_fuzzy_match

class FilesystemApi():
    def __init__(self, agent_instance_version):
        self.agent_instance_version = agent_instance_version
        self.agent_instance = agent_instance_version.agent_instance
   
    def get_loaded_items(self, refresh_from_disk=False):
        r = []
        for item in FsLogEntry.objects.filter(agent_instance=self.agent_instance, is_newest_version=True, next_versions=None).exclude(load_mode=None):
            r.append(item.refresh_from_disk() if refresh_from_disk else item)
        return r

    def fs_load(self, path, filter = "", mode="full"):
        abs_path, rel_path = clean_path(self.agent_instance_version.workingdir, path)
        if not check_permission(self.agent_instance_version, abs_path, 'read'):
            return (False, {'status': 'failed', 'message': f"Read access denied for: {rel_path}"})
        success, item = FsLogEntry.objects.get_or_create_latest(agent_instance = self.agent_instance, action="load", load_mode = mode, path = abs_path, filter = filter, recursive = False, must_exist = True )
        if not success:
            return False, item
        return True, {}
       
    def fs_unload(self, path):
        abs_path, rel_path = clean_path(self.agent_instance_version.workingdir, path)
        item = FsLogEntry.objects.filter(agent_instance=self.agent_instance, path=abs_path, is_newest_version=True).exclude(load_mode=None).order_by("-pk").first()
        if not item:
            return True, {}
        if item.is_pinned:
            return False, {"status": "error", "message": f"Path has been pinned to your context by the user, you can not unload it"}
        item.create_next_version(action="unload", load_mode=None)
        return True, {}

    def fs_write(self, path, content):
        abs_path, rel_path = clean_path(self.agent_instance_version.workingdir, path)
        if not check_permission(self.agent_instance_version, abs_path, 'write'):
            return (False, {'status': 'failed', 'message': f"Write access denied for {rel_path}"})
        success, item = FsLogEntry.objects.get_or_create_latest(agent_instance=self.agent_instance, action="write", path = abs_path, must_be_file = True, must_exist = False)
        if not success:
            return False, item
        success, newitem = item.write(content=content)
        if not success:
            return False, newitem
        return True, {}

    def fs_append(self, path, content):
        abs_path, rel_path = clean_path(self.agent_instance_version.workingdir, path)
        if not check_permission(self.agent_instance_version, abs_path, 'write'):
            return (False, {'status': 'failed', 'message': f"Write access denied for {rel_path}"})
        success, item = FsLogEntry.objects.get_or_create_latest(agent_instance = self.agent_instance, action="append", path = abs_path, must_be_file = True, must_exist = False)
        if not success:
            return False, item
        success, newitem = item.append(content=content)
        if not success:
            return False, newitem
        return True, {}
    
    def fs_replace(self, path, search, replace):
        abs_path, rel_path = clean_path(self.agent_instance_version.workingdir, path)
        if not check_permission(self.agent_instance_version, abs_path, 'write'):
            return (False, {'status': 'failed', 'message': f"Write access denied for {rel_path}"})
        success, item = FsLogEntry.objects.get_or_create_latest(agent_instance=self.agent_instance, action="replace", path = abs_path, must_be_file = True, must_exist = True)
        if not success:
            return False, item
        ocontent = item.content
        if search not in ocontent:
            new_search = find_fuzzy_match(ocontent, search, threshold=0.97)
            if new_search is None:
                return False, {"status": "error", "message": f"Value of 'search' did not match anything in '{rel_path}'."}
            search = new_search
        success, newitem = item.write(content = ocontent.replace(search, replace))
        if not success:
            return False, newitem
        return True, {}

    def fs_python_edit(self, path, source, classname = None, functionname = None):
        abs_path, rel_path = clean_path(self.agent_instance_version.workingdir, path)
        if not check_permission(self.agent_instance_version, abs_path, 'write'):
            return (False, {'status': 'failed', 'message': f"Write access denied for {rel_path}"})      
        success, item = FsLogEntry.objects.get_or_create_latest(agent_instance = self.agent_instance, action="edit", path = abs_path, must_be_file = True, must_exist = True)
        if not success:
            return False, item
        try:
            lines = item.content.splitlines(keepends=True)
            tree = ast.parse(item.content)
            dedented_source = textwrap.dedent(source).rstrip() + "\n"
            new_node_tree = ast.parse(dedented_source)
            if not new_node_tree.body or len(new_node_tree.body) != 1:
                return False, {"status": "error", "message": "Source must be a single function or class."}
            new_node = new_node_tree.body[0]
            def get_node_indent(node):
                line = lines[node.lineno - 1]
                return line[:len(line) - len(line.lstrip())]
            target_scope = tree
            replaced = False
            indent = ""
            if functionname:
                if not isinstance(new_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return False, {"status": "error", "message": "Provided source is not a function."}
                new_node.name = functionname
                if classname:
                    for node in tree.body:
                        if isinstance(node, ast.ClassDef) and node.name == classname:
                            target_scope = node
                            indent = get_node_indent(node) + " " * 4
                            break
                    else:
                        return False, {"status": "error", "message": f"Class {classname} not found."}
                else:
                    indent = ""
                for i, node in enumerate(target_scope.body):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == functionname:
                        # Correctly determine the start line, accounting for decorators.
                        start_node = node.decorator_list[0] if node.decorator_list else node
                        start = start_node.lineno - 1
                        end = node.end_lineno

                        lines[start:end] = [textwrap.indent(dedented_source, indent)]
                        replaced = True
                        break
                if not replaced:
                    insert_at = target_scope.body[-1].end_lineno if target_scope.body else (target_scope.lineno if hasattr(target_scope, 'lineno') else len(lines))
                    lines.insert(insert_at, textwrap.indent(dedented_source, indent))
            elif classname:
                if not isinstance(new_node, ast.ClassDef):
                    return False, {"status": "error", "message": "Provided source is not a class."}
                new_node.name = classname
                indent = ""
                for i, node in enumerate(tree.body):
                    if isinstance(node, ast.ClassDef) and node.name == classname:
                        # Correctly determine start line for classes, accounting for decorators.
                        start_node = node.decorator_list[0] if node.decorator_list else node
                        start = start_node.lineno - 1
                        end = node.end_lineno
                        lines[start:end] = [dedented_source]
                        replaced = True
                        break
                if not replaced:
                    lines.append("\n" + dedented_source)
            else:
                return False, {"status": "error", "message": "Need functionname or classname."}

            success, uresult = item.write(content="".join(lines))
            if not success:
                return False, uresult

        except SyntaxError as e:
            return False, {"status": "error", "message": f"Error: Syntax error in file or provided source: {e} {traceback.format_exc()}"}

        return True, {}

    def get_history_limiting_rules(self):
        limit = self.agent_instance.effective_limit_max_conversation_messages
        return { 
            "Filesystem": [                {
                    #'group_name': "Filesystem",
                    'name': 'path,unloaded',
                    'description': 'Limits history for tool calls on paths that are no longer loaded in the context.',
                    #'match': lambda tc: tc.function_name.startswith('fs_') and tc.arguments.get('path') and get_abs_path(self.agent_instance_version.workingdir, tc.arguments.get('path')) not in loaded_paths,
                    #'key': lambda tc: get_abs_path(self.agent_instance_version.workingdir, tc.arguments.get('path')),
                    'limits': {'pending': limit, 'success': 2, 'failed': 1, 'max': 2}
                },
                {
                    #'group_name': "Filesystem",
                    'name': 'path,function',
                    'description': 'Limits history on a per-path, per-function basis (e.g., max 3 fs_write for "file.txt").',
                    #'match': lambda tc: tc.function_name.startswith('fs_'),
                    #'key': lambda tc: (get_abs_path(self.agent_instance_version.workingdir, tc.arguments.get('path', '')), tc.function_name),
                    'limits': {'pending': limit, 'success': 3, 'failed': 2, 'max': 3}
                },
                {
                    #'group_name': "Filesystem",
                    'name': 'path',
                    'description': 'Limits total history for any fs_* call on a specific path.',
                    #'match': lambda tc: tc.function_name.startswith('fs_'),
                    #'key': lambda tc: get_abs_path(self.agent_instance_version.workingdir, tc.arguments.get('path', '')),
                    'limits': {'pending': limit, 'success': 3, 'failed': 2, 'max': 3}
                },
                {
                    #'group_name': "Filesystem",
                    'name': 'any',
                    'description': 'A general fallback limit for all filesystem operations.',
                    #'match': lambda tc: tc.function_name.startswith('fs_'),
                    #'key': lambda tc: '',
                    'limits': {'pending': limit, 'success': limit, 'failed': 2, 'max': limit}
                }
            ]
        }
