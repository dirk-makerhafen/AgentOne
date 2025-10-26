import re, ast 

def parse_responsestring(response_string):
    response_string = response_string.replace('_@_@_', '@@@')

    parsed_output = []
     

    # fix common errors llm make when outputing tool calls. 
    for tname in ["memory_add", "memory_correct", "fs_load", "fs_unload", "fs_write", "fs_append", "fs_replace", "fs_python_edit", "python", "agent_send_message", "await_input","kv_storage.set", "kv_storage.get", "kv_storage.list", "kv_storage.delete"]:
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
        if f'\n    @@@{tname}(' in  response_string:
            parts = response_string.split("\n")
            for index, part in enumerate(parts):
                if part.startswith(f'    @@@{tname}') and part.endswith('@@@'):
                    parts[index] = part[4:]
            response_string = "\n".join(parts) 
        if f'\n  @@@{tname}(' in  response_string:
            parts = response_string.split("\n")
            for index, part in enumerate(parts):
                if part.startswith(f'  @@@{tname}') and part.endswith('@@@'):
                    parts[index] = part[2:]
            response_string = "\n".join(parts) 
    # capture some common output mistakes llms make in addition to the correct tool call syntax
    tool_call_line_pattern = re.compile(r'(^|\n|```|```python|```python\n|```tool_code|```tool_code\n)@@@([\w.]+)\s*\((.*?)\)@@@(?=$|\n|```)', re.DOTALL)

    last_end_index = 0

    for match in tool_call_line_pattern.finditer(response_string):
        full_match_start = match.start(0)
        full_match_end = match.end(0)
        full_match_content = response_string[full_match_start:full_match_end]
        # fix incorrect pre/post tool call wrappers that llms produce
        while len(full_match_content) > 0 and full_match_content[-1] != "@": full_match_content = full_match_content[:-1]
        while len(full_match_content) > 0 and full_match_content[ 0] != "@": full_match_content = full_match_content[1:]
        while full_match_content[:3] != "@@@":
            full_match_content = f"@{full_match_content}"
        while full_match_content[-3:] != "@@@":
            full_match_content = f"{full_match_content}@"

        func_name = match.group(2).strip() # Changed from group(2) to group(1)
        args_str = match.group(3).strip() # Changed from group(3) to group(2)
        
        chat_message_segment = _clean_msg_ending(response_string[last_end_index:full_match_start])
        if chat_message_segment != "":
            if len(parsed_output) == 0:  # first message
                chat_message_segment = _clean_first_msg_start(chat_message_segment)
            else:
                chat_message_segment = _clean_msg_start(chat_message_segment)
            parsed_output.append({"content": f"{chat_message_segment}\n"})

        arguments = {}
        if args_str.strip(): # Only process if arguments string is not empty
            try:
                temp_args = {}
                # Regex for key-value pairs, handling various string formats including triple quotes
                arg_kv_pattern = re.compile(
                    r"(\w+)\s*=\s*("
                    r"'''(?:[^\\]|\\.|\\n)*?'''|"   # triple single quotes
                    r'"""(?:[^\\]|\\.|\\n)*?"""|'   # triple double quotes
                    r"'(?:[^'\\]|\\.)*'|"           # single quotes
                    r'"(?:[^"\\]|\\.)*"|'           # double quotes
                    r"\[(?:[^\]]|\\.)*?\]|"         # ADDED: Matches lists like ['a', 'b']
                    r"\{(?:[^\}]|\\.)*?\}|"         # ADDED: Matches dicts like {'key': 'value'}
                    r"[^,]+?"                       # fallback for bare values (must be last to ensure others are tried first)
                    r")(?:\s*,|\s*$)",              # separator or end of string
                    re.DOTALL
                )

                if "_@_@_" in args_str:
                    args_str = args_str.replace( "_@_@_", '@@@')
                for arg_match in arg_kv_pattern.finditer(args_str):
                    key = arg_match.group(1)
                    value_str = arg_match.group(2)
                    try:
                        value = ast.literal_eval(value_str)
                    except (ValueError, SyntaxError):
                        # If literal_eval fails, check if it's a triple-quoted string that needs stripping
                        if (value_str.startswith('"""') and value_str.endswith('"""')) or \
                           (value_str.startswith("'''") and value_str.endswith("'''")):
                            value = value_str[3:-3] # Strip outer triple quotes
                            try:
                                value = ast.literal_eval(value_str)
                            except:
                                pass
                        else:
                            value = value_str # Keep as raw string if evaluation failed and not triple-quoted
                    if func_name in [ "agent_send_message", "update_working_dir"]:
                        if key in ["recipient_agent_id", "target_agent_id"]: 
                            key = "agent_id"
                  
                    temp_args[key] = value
                arguments = temp_args
            except Exception:
                # If argument parsing fails for any reason (e.g., malformed syntax),
                # treat this entire tool call as malformed and skip it.
                last_end = match.end()
                continue # Skip adding this malformed tool call to parsed_output

        
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

