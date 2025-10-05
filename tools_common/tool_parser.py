import re, ast 

def extract_tool_call_parts(response_string):
    parsed_output = []
    
    for tname in ["memory_add", "memory_correct", "memory_reposition", "fs_load", "fs_unload", "fs_write", "fs_append", "fs_replace", "fs_python_edit", "python", "agent_send_message", "await_user_input"]:
        response_string = response_string.replace(')@@@\n@%s(' % tname, ')@@@\n@@@%s(' % tname)
        response_string = response_string.replace('.@@@%s(' % tname, '.\n@@@%s(' % tname)
        if f'- `{tname}' in response_string:
            parts = response_string.split("\n")
            for index, part in enumerate(parts):
                if part.startswith(f'- `{tname}') and part.endswith('`'):
                    parts[index] = "@@@" + part[3:-1] + "@@@"
            response_string = "\n".join(parts)
        if f'- `@@@{tname}' in response_string:
            parts = response_string.split("\n")
            for index, part in enumerate(parts):
                if part.startswith(f'- `@@@{tname}') and part.endswith('@@@`'):
                    parts[index] = part[3:-1]
            response_string = "\n".join(parts)
            
    tool_call_line_pattern = re.compile(r'(^|\n|```|```python|```python\n|```tool_code|```tool_code\n)@@@(\w+)\s*\((.*?)\)@@@(?=$|\n|```)', re.DOTALL)

    last_end_index = 0

    for match in tool_call_line_pattern.finditer(response_string):
        full_match_start = match.start(0)
        full_match_end = match.end(0)
        full_match_content = response_string[full_match_start:full_match_end]
        while len(full_match_content) > 0 and full_match_content[-1] != "@": full_match_content = full_match_content[:-1]
        while len(full_match_content) > 0 and full_match_content[ 0] != "@": full_match_content = full_match_content[1:]
        while full_match_content[:3] != "@@@":
            full_match_content = f"@{full_match_content}"
        while full_match_content[-3:] != "@@@":
            full_match_content = f"{full_match_content}@"

        # CORRECTED GROUP INDICES HERE:
        func_name = match.group(2) # Changed from group(2) to group(1)
        args_str = match.group(3).strip() # Changed from group(3) to group(2)
        
        chat_message_segment = _clean_msg_ending(response_string[last_end_index:full_match_start])
        if chat_message_segment != "":
            if len(parsed_output) == 0:  # first message
                chat_message_segment = _clean_first_msg_start(chat_message_segment)
            else:
                chat_message_segment = _clean_msg_start(chat_message_segment)
            parsed_output.append({"content": f"{chat_message_segment}\n"})

        arguments = {}
        if args_str:
            #print("args_str", args_str)
            key_value_pattern = re.compile(
                r"(\w+)\s*=\s*("
                r"'''(?:[^\\]|\\.|\\n)*?'''|"   # triple single quotes
                r'"""(?:[^\\]|\\.|\\n)*?"""|'   # triple double quotes
                r"'(?:[^'\\]|\\.)*'|"           # single quotes
                r'"(?:[^"\\]|\\.)*"|'           # double quotes
                r"[^,]+?"                       # fallback for bare values
                r")(?:\s*,|\s*$)",
                re.DOTALL
            )
            
            for arg_match in key_value_pattern.finditer(args_str):
                #print(arg_match)
                key = arg_match.group(1)
                value_str = arg_match.group(2)
                #print(key, f"str_value: '{value_str}'")
               
                try:
                    value = ast.literal_eval(value_str)
                except (ValueError, SyntaxError):
                    if (value_str.startswith('"""') and value_str.endswith('"""')) or (value_str.startswith("'''") and value_str.endswith("'''")):
                        value = value_str[3:-3]
                        try:
                            value = ast.literal_eval(value_str)
                        except (ValueError, SyntaxError):
                            pass
                    else:
                        value = value_str 
                #print("KV;", key, value)
                arguments[key] = value
        
        parsed_output.append({
            'tool': func_name,
            'arguments': arguments,
            'content': f"{full_match_content}\n",
        })
        
        last_end_index = full_match_end

    remaining_chat_message = response_string[last_end_index:].strip()
    #if len(parsed_output) > 0:  # first message
    remaining_chat_message = _clean_msg_ending(_clean_msg_start(remaining_chat_message))
    if remaining_chat_message != "":
        parsed_output.append({"content": remaining_chat_message})

    return parsed_output

def generate_function_stub(func_name: str, func_def: dict) -> str:
    """
    Generate a Python function stub from a dictionary definition.

    Args:
        func_name (str): Name of the function to generate.
        func_def (dict): Dictionary containing description and parameters.

    Returns:
        str: The generated Python function code as a string.
    """
    # Extract description
    description = func_def.get("description", "").strip()

    # Extract parameters
    params = func_def.get("parameters", {})
    param_str_list = []
    docstring_params = []

    for param_name, param_info in params.items():
        required = param_info.get("required", False)
        
        default_value = "" if required else " = %s" % param_info.get("default", "None")
        param_str_list.append(f"{param_name}{default_value}")

        type_str = param_info.get("type", "Any")
        param_desc = param_info.get("description", "")
        docstring_params.append(f"    {param_name} ({type_str}): {param_desc}")

    # Join parameters for function definition
    params_str = ", ".join(param_str_list)

    # Create the docstring
    docstring = f'"""{description}\n\nArgs:\n' + "\n".join(docstring_params) + '\n"""'

    # Build the full function stub
    function_code = f"def {func_name}({params_str}):\n    {docstring}\n    pass\n"
    return function_code

def _clean_msg_ending(message):
    while len(message) > 0 and message[-1] in ["'", '"', '`', '\n', '"\r', " "]:
        message = message[:-1]
    return message

def _clean_msg_start(message):
    while len(message) > 0 and message[0] in ["'", '"', '`', '\n', '"\r', " "]:
        message = message[1:]
    return message

def _clean_first_msg_start(message):
    while len(message) > 0 and message[0] in ['\n', '"\r', " "]:
        message = message[1:]
    return message

