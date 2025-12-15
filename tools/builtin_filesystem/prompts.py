
MARKER = 'FS_TOOL_CONTENT'

PROMPT_INSTRUCTIONS = """
# Filesystem Tools: File and Directory Management

You have access to a set of external `fs_*` tools to manage file and directory context. Use them to load, unload, write, append, or update files and directories during your tasks.
Remember to fs_load files that are not already loaded before trying to edit them so you know their content.  

## Core Principles & Best Practices

*   **Internal Use Only:** `<%(marker)s>` messages and instructions are for your internal use only. **Never** respond to them or reference them directly to the user, unless explicitly asked about your tools. 
*   **Absolute Trust in `<%(marker)s>` Messages:** The content in `<%(marker)s>` messages (file content or directory listings) **always** represents the most recent, up-to-date version, regardless of where it appears in the conversation history. If no new `%(marker)s` message is present for a file/directory, its last provided content is still current.
*   **Batch Operations:** Combine related `fs_` tool calls into a single response to improve efficiency and reduce cost (e.g., load/unload multiple files at once).
*   **Timely Unloading:** Remove files or directories from your context memory using `fs_unload` when they are no longer relevant to your current task.
*   **Path Interpretation:** The 'path' attribute can be an absolute path or relative to your current working directory (`{{workingdir}}`).
*   **File vs. Directory:** If unsure whether a path is a file or a directory, attempt to `fs_load` it; errors will be reported if invalid.
*   **No Implicit Loading:** `fs_write`, `fs_append`, and `fs_replace` **do not** automatically load file content into your context. You **must** explicitly call `fs_load` to view a file's content.
*   **Single Path Per Call:** Each `fs_` tool call supports only one `path` attribute. To modify multiple files, use multiple distinct `fs_` tool calls.
*   **Token Efficiency for Changes:** For changes to larger files, prefer `fs_replace` over `fs_write` to save on tokens, as `fs_replace` only sends the changed parts.
*   **Avoid Duplication:** Do not duplicate tool calls unnecessarily.
*   **Token Efficiency for loaded files**: The 'summary' mode of `fs_load` retrieve a token-efficient structural outline of a file, highlighting its architecture without full implementation details for Python, JavaScript/JSX, CSS, C/C++/Arduino, Java, Go, C#, TypeScript/TSX, Ruby, JSON, and YAML files.

## Available Context Tools

*   **`fs_load`**: Load file content or list directory contents.
*   **`fs_unload`**: Remove a file or directory from your context memory.
*   **`fs_write`**: Overwrite an entire file with new content.
*   **`fs_append`**: Append content to the end of a file (no automatic newline).
*   **`fs_replace`**: Search for and replace content within a file.
*   **`fs_python_edit`**: Efficient editing of Python source code

## Understanding `<%(marker)s>` Messages (System Output)

Messages starting with `<%(marker)s` are system-injected outputs from `fs_*` tools. They provide file content or directory listings directly into your memory.
They end with `</%(marker)s>`.

*   **Purpose:** This information is solely for your internal use to assist the user. The user will **not** see these messages, and you should **not** respond to or acknowledge them unless explicitly asked.
*   Format Example:
<%(marker)s path='some.file' is_directory=False status=up-to-date>THE Actual CONTENT<%(marker)s>
""" % {
    "marker": MARKER
}

PROMPT_CONTENT_INJECTION = '''<%s path='{{path}}' {%% if is_directory %%}is_directory=True{%% endif %%} mode='{{load_mode}}' status='{%% if exist_on_fs %%}{%% if refreshed_from_fs %%}(Updated by user){%% else %%}up-to-data{%% endif %%}{%% else %%}Deleted, path does not exist{%% endif %%}'>{{content | safe}}</%s>''' % (MARKER, MARKER)

PROMPTS = [
    {
        "name": "instructions",
        "title": "Filesystem tool instructions",
        "description": "Contains general usage instructions for the agent2agent tool",
        "arguments": [],
        'template': PROMPT_INSTRUCTIONS,
    },
    {
        "name": "content_injection",
        "title": "Ls",
        "description": "TODO",
        "arguments": [
            {
                "name": "agents",
                "description": "list of agent dicts with name, description and id",
                "required": True,
            }
        ],
        'template': PROMPT_CONTENT_INJECTION,
    },
]

TOOLS = {
    "fs_load": {
        "name": "",
        "title": "",
        "description": "Load the content of a file or list the contents of a directory into your context memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file or directory (POSIX-style).", 
                },
                "recursive": {
                    "type": "boolean", 
                    "description": "List directories recursively. Ignored for files.", 
                    'default': False,
                },
                "mode": {
                    "type": "string", 
                    "description": "'full' to load the entire file content, 'summary' to load a outline (for supported files like Python, JavaScript/JSX, CSS, C/C++/Arduino, Java, Go, C#, TypeScript/TSX, Ruby, JSON, and YAML). Defaults to 'full'.", 
                    'default': 'full',
                }
            },
            "required" : ["path"],
        }
    },
    "fs_unload": {
        "name": "",
        "title": "",
        "description": "Remove a file or directory from your context memory to free resources.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": { 
                    "type": "string", 
                    "description": "Path to unload.", 
                },
            },
            "required" : ["path"],
        }
    },
    "fs_write": {
        "name": "",
        "title": "",
        "description": "Overwrite an entire file with new content, replacing any existing data.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": { 
                    "type": "string", 
                    "description": "Path to the file.", 
                },
                "content": { 
                    "type": "string", 
                    "description": "New file content.", 
                }
            },
            "required" : ["path", "content"],
        }
    },
    "fs_append": {
        "name": "",
        "title": "",
        "description": "Append content to the end of a file. No newline is added automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": { 
                    "type": "string", "description": "Path to the file.", 
                },
                "content": { 
                    "type": "string", "description": "Content to append.", 
                }
            },
            "required" : ["path", "content"],
        }
        
    },
    "fs_replace": {
        "name": "",
        "title": "",
        "description": "Search for and replace content within a file and replace them with a new string.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": { 
                    "type": "string", 
                    "description": "Path to the file.", 
                },
                "search": { 
                    "type": "string", 
                    "description": "Text to search for.", 
                },
                "replace": { 
                    "type": "string", 
                    "description": "Replacement text.", 
                }
            },
            "required" : ["path", "search", "replace"],
        }
    },
    "fs_python_edit": {
        "name": "",
        "title": "",
        "description":  "Inserts or replaces a Python function or method within a specified file and (optionally) class. If the function/method does not exist, it will be added. If it exists, its entire definition will be replaced. Automatic indentation correction is applied to the provided source code. For python code this is more efficient than fs_write or fs_replace. ",
        "parameters": {
            "type": "object",
            "properties": {
                "path": { 
                    "type": "string", 
                    "description": "The path to the Python file to be modified.", 
                },
                "classname": { 
                    "type": "string", 
                    "description": "The name of the class where the function/method is located. Omit or provide an empty string for top-level (module-level) functions. The tool will fail if the specified class does not exist.", 
                },
                "functionname": {
                    "type": "string", 
                    "description": "The name of the function or method to be inserted or replaced. Must be unique within its scope (class or module level). if Omited or empty and classname is provided, attempts to replace the entire class", 
                },
                "source": {
                    "type": "string", 
                    "description": "The complete source code for the function or method. The tool will automatically adjust its indentation to fit the target location. Example: 'def my_func(self, arg):\\n    pass'", 
                },
            },
            "required" : ["path", "source"],
        }
    }
}

