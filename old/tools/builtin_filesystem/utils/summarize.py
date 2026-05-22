import ast
import re
import json
import traceback
try:
    import yaml
except ImportError:
    yaml = None

def summarize(file_path, content):
    """
    Dispatches to the correct summarizer based on file extension.
    """
    if file_path.endswith('.py'):
        return summarize_python(content)
    elif file_path.endswith(('.js', '.jsx')):
        return summarize_javascript(content)
    elif file_path.endswith('.css'):
        return summarize_css(content)
    elif file_path.endswith(('.c', '.h', '.ino')):
        return summarize_c_cpp(content)
    elif file_path.endswith('.java'):
        return summarize_java(content)
    elif file_path.endswith('.go'):
        return summarize_golang(content)
    elif file_path.endswith('.cs'):
        return summarize_csharp(content)
    elif file_path.endswith(('.ts', '.tsx')):
        return summarize_typescript(content)
    elif file_path.endswith('.rb'):
        return summarize_ruby(content)
    elif file_path.endswith('.json'):
        return summarize_yaml_json(content, is_json=True)
    elif file_path.endswith(('.yml', '.yaml')):
        return summarize_yaml_json(content, is_json=False)
    else:
        return content

# --- Summarizer Functions (Alphabetical Order) ---

def summarize_c_cpp(source_code):
    """
    Summarizes C/C++ (including Arduino .ino) files by removing function bodies
    while preserving preprocessor directives, declarations, and comments.
    This is a best-effort approach using regex and brace counting.
    """
    output_lines = []
    in_block_to_summarize = False
    brace_level = 0
    
    function_block_pattern = re.compile(r'^\s*(?:(?:static|const|inline|virtual)\s+)*\w+\s+\w+\s*\([^)]*\)\s*\{.*$|(?i)^\s*(?:class|struct|union|enum)\s+\w+\s*\{.*$')

    for line in source_code.splitlines():
        stripped_line = line.strip()

        if in_block_to_summarize:
            brace_level += stripped_line.count('{')
            brace_level -= stripped_line.count('}')
            if brace_level <= 0:
                in_block_to_summarize = False
                output_lines.append(line)
            continue
        else:
            if stripped_line.startswith('#') or stripped_line.startswith('//') or stripped_line.startswith('/*') or stripped_line.endswith('*/'):
                output_lines.append(line)
                continue

            if stripped_line.endswith('{') and not re.match(r'^\s*(if|for|while|switch|catch)\b', stripped_line):
                if function_block_pattern.search(line):
                    open_braces = stripped_line.count('{')
                    close_braces = stripped_line.count('}')
                    if open_braces > close_braces:
                        brace_level = open_braces - close_braces
                        in_block_to_summarize = True
                        output_lines.append(line)
                        continue
            
            output_lines.append(line)

    return '\n'.join(output_lines)

def summarize_csharp(source_code):
    """
    Summarizes a C# file by emptying method, constructor, and property bodies.
    This is a best-effort approach using regex and brace counting.
    """
    output_lines = []
    in_block_to_summarize = False
    brace_level = 0
    pattern = re.compile(r'^\s*(?!if|for|while|switch|try|catch|finally|lock|else\b)\s*.*(?:\)|])?\s*\{$|class\s+.*\{$|interface\s+.*\{$|enum\s+.*\{$|struct\s+.*\{$|delegate\s+.*\{$|(?:get|set|add|remove)\s*\{.*$')

    for line in source_code.splitlines():
        stripped_line = line.strip()

        if in_block_to_summarize:
            brace_level += stripped_line.count('{')
            brace_level -= stripped_line.count('}')
            if brace_level <= 0:
                in_block_to_summarize = False
                output_lines.append(line)
            continue
        else:
            output_lines.append(line)
            if pattern.search(line):
                open_braces = line.count('{')
                close_braces = line.count('}')
                if open_braces > close_braces:
                    brace_level = open_braces - close_braces
                    in_block_to_summarize = True

    return '\n'.join(output_lines)

def summarize_css(source_code):
    """
    Summarizes a CSS file by removing all rules within selectors.
    """
    return re.sub(r'(\s*\{)[\s\S]*?(\})', r'\1\n\2', source_code)

def summarize_golang(source_code):
    """
    Summarizes a Golang file by emptying function and method bodies.
    This is a best-effort approach using regex and brace counting.
    """
    output_lines = []
    in_block_to_summarize = False
    brace_level = 0
    function_pattern = re.compile(r'^\s*func(?:\s+\([^)]+\))?\s+\w+\s*\([^)]*\)\s*\{')

    for line in source_code.splitlines():
        stripped_line = line.strip()

        if in_block_to_summarize:
            brace_level += stripped_line.count('{')
            brace_level -= stripped_line.count('}')
            if brace_level <= 0:
                in_block_to_summarize = False
                output_lines.append(line)
            continue
        else:
            output_lines.append(line)
            if function_pattern.match(line):
                open_braces = stripped_line.count('{')
                close_braces = stripped_line.count('}')
                if open_braces > close_braces:
                    brace_level = open_braces - close_braces
                    in_block_to_summarize = True

    return '\n'.join(output_lines)

def summarize_java(source_code):
    """
    Summarizes a Java file by emptying method and constructor bodies.
    This is a best-effort summary using a state machine and heuristics.
    """
    output_lines = []
    in_block_to_summarize = False
    brace_level = 0
    pattern = re.compile(r'^\s*(?!if|for|while|switch|try|catch|finally|synchronized|else\b)\s*.*(?:\)|])?\s*\{$|class\s+.*\{$|interface\s+.*\{$|enum\s+.*\{$|@interface\s+.*\{$')

    for line in source_code.splitlines():
        stripped_line = line.strip()

        if in_block_to_summarize:
            brace_level += stripped_line.count('{')
            brace_level -= stripped_line.count('}')
            if brace_level <= 0:
                in_block_to_summarize = False
                output_lines.append(line)
            continue
        else:
            output_lines.append(line)
            if pattern.search(line):
                open_braces = line.count('{')
                close_braces = line.count('}')
                if open_braces > close_braces:
                    brace_level = open_braces - close_braces
                    in_block_to_summarize = True

    return '\n'.join(output_lines)

def summarize_javascript(source_code):
    """
    Summarizes a JavaScript/JSX file by emptying function and method bodies.
    This is a best-effort summary using a state machine and heuristics.
    """
    output_lines = []
    in_block_to_summarize = False
    brace_level = 0
    pattern = re.compile(r'^\s*(?!if|for|while|switch|catch\b)\s*.*\)\s*\{$|=>\s*\{$|class\s+.*\s*\{$')

    for line in source_code.splitlines():
        stripped_line = line.strip()

        if in_block_to_summarize:
            brace_level += stripped_line.count('{')
            brace_level -= stripped_line.count('}')
            if brace_level <= 0:
                in_block_to_summarize = False
                output_lines.append(line)
            continue
        else:
            output_lines.append(line)
            if pattern.search(line):
                open_braces = line.count('{')
                close_braces = line.count('}')
                if open_braces > close_braces:
                    brace_level = open_braces - close_braces
                    in_block_to_summarize = True

    return '\n'.join(output_lines)

def summarize_python(source_code):
    """
    Summarizes a Python source file by replacing function and method bodies
    with 'pass'. Preserves imports, class/function definitions, and docstrings.
    """
    try:
        tree = ast.parse(source_code)
        summarizer = PythonSummarizer()
        transformed_tree = summarizer.visit(tree)
        return ast.unparse(transformed_tree)
    except (SyntaxError, ValueError) as e:
        return f"# Could not parse Python code: {e}\n{source_code}"

def summarize_ruby(source_code):
    """
    Summarizes a Ruby file by emptying method, class, and module bodies.
    This is a best-effort approach using a state machine that tracks block keywords and 'end'.
    """
    output_lines = []
    block_level = 0
    in_skippable_block = False
    added_placeholder = False
    block_starters = ['module', 'class', 'def']

    for line in source_code.splitlines():
        stripped = line.strip()
        
        # Detect block start
        if any(re.match(r'^{}\b'.format(re.escape(k)), stripped) for k in block_starters):
            output_lines.append(line)
            block_level += 1
            if block_level == 1:
                in_skippable_block = True
                added_placeholder = False
            continue

        # Detect block end
        if stripped == 'end':
            if block_level == 1 and in_skippable_block and not added_placeholder:
                indent = len(line) - len(stripped)
                output_lines.append('{}# ...'.format(' ' * (indent + 2)))
            
            if block_level == 1:
                in_skippable_block = False
            
            output_lines.append(line)
            block_level = max(0, block_level - 1)
            continue

        # Inside a skippable block, skip content
        if in_skippable_block:
            if not stripped:
                output_lines.append(line)
            else:
                added_placeholder = True
            continue

        # Default: not in a skippable block
        output_lines.append(line)
    
    return '\n'.join(output_lines)

def summarize_typescript(source_code):
    """
    Summarizes a TypeScript file by emptying function, method, and constructor bodies.
    This is a best-effort summary using a state machine and heuristics.
    """
    output_lines = []
    in_block_to_summarize = False
    brace_level = 0
    pattern = re.compile(r'^\s*(?!if|for|while|switch|catch\b)\s*.*(?:\)|])?\s*\{$|class\s+.*\{$|interface\s+.*\{$|enum\s+.*\{$|namespace\s+.*\{$|type\s+.*=\s*\{$|@\w+\s*\(.*\)\s*class\s+.*\{$|@\w+\s*class\s+.*\{$')

    for line in source_code.splitlines():
        stripped_line = line.strip()

        if in_block_to_summarize:
            brace_level += stripped_line.count('{')
            brace_level -= stripped_line.count('}')
            if brace_level <= 0:
                in_block_to_summarize = False
                output_lines.append(line)
            continue
        else:
            output_lines.append(line)
            if pattern.search(line):
                open_braces = line.count('{')
                close_braces = line.count('}')
                if open_braces > close_braces:
                    brace_level = open_braces - close_braces
                    in_block_to_summarize = True

    return '\n'.join(output_lines)

def summarize_yaml_json(source_code, is_json=False):
    """
    Summarizes YAML or JSON content by replacing scalar values with '...'
    and array elements with a placeholder, preserving structure.
    """
    try:
        if is_json:
            data = json.loads(source_code)
            summarized_data = _summarize_data_structure(data)
            return json.dumps(summarized_data, indent=2)
        else: # YAML
            if yaml is None:
                return "# PyYAML not installed. Cannot summarize YAML."
            data = yaml.safe_load(source_code)
            summarized_data = _summarize_data_structure(data)
            return yaml.dump(summarized_data, indent=2, default_flow_style=False)
    except (json.JSONDecodeError, yaml.YAMLError, TypeError) as e:
        return f"# Could not parse {'JSON' if is_json else 'YAML'} content: {e} {traceback.format_exc()}"


# Common Helpers
def _summarize_data_structure(value):
    """Recursively summarizes JSON/YAML values."""
    if isinstance(value, dict):
        return {k: _summarize_data_structure(v) for k, v in value.items()}
    elif isinstance(value, list):
        if not value:
            return []
        # If list contains complex objects, summarize the first one as a template
        if isinstance(value[0], (dict, list)):
             return [_summarize_data_structure(value[0]), "..."]
        # If list contains simple values
        return ["..."]
    else:
        return "..."
    

# Helper Class for Python Summarizer (moved to module level)
class PythonSummarizer(ast.NodeTransformer):
    """
    An AST transformer that replaces the body of functions and methods
    with a single 'pass' statement, preserving docstrings.
    """
    def _summarize_body(self, node):
        if not hasattr(node, 'body') or not node.body:
            return node

        docstring = ast.get_docstring(node)
        new_body = []
        if docstring:
            new_body.append(ast.Expr(value=ast.Constant(value=docstring)))
        
        new_body.append(ast.Pass())
        node.body = new_body
        return node

    def visit_FunctionDef(self, node):
        return self._summarize_body(node)

    def visit_AsyncFunctionDef(self, node):
        return self._summarize_body(node)

