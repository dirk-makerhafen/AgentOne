TOOL_RESPONSE_MARKER = 'TOOL_RESPONSE'

INSTRUCTIONS = '''
# You do have access to a set of external tools that help you accomplish you tasks, namely:
- Filesystem Tools: These tools give you read and write access to files and directories on the users computer.
- Memory Tools: These tools help you manage your memories of past events, future planing and everything you need to remember as an agi. 
- Python Tool: Execute arbitary python code 
- Python Editing Tool: Edit .py file efficiently
- User Interaction Tool: Trigger user Interactions 

Your tool call follow standard python syntax, however to destingish between normal chat and actual tool calls each tool call must:
- start in a new line
- prefix function name with @@@
- postfix function call with @@@ and a new line.  
- carefull handle correct escaping or arguments if needed. 
- make sure tool calls always start in a new line.

## Example tool calls:
### Calling `fs_load`:
@@@fs_load(path="foo/some.py")@@@

### Calling `fs_write`:
@@@fs_write(path='example.txt', content=\'\'\'
Make sure to escape arguments properly!
\\'\\'\\'inside inner quotes\\'\\'\\'
\'\'\')@@@


Tool Results will be send to your from the system as a user message starting with <%(marker)s.
This message will list the results of all tool calls in your previous message as:
<%(marker)s function='functionname' argument1="v1" arg2="somev">the actual result content</%(marker)s>
<%(marker)s function='otherf' path="some.file">result content</%(marker)s>

Note that not all arguments of your original tool call are show, only important identifiers like path, action, track, layer and index. Content is generally not show to not blow up the context window.
''' % {"marker":TOOL_RESPONSE_MARKER}

TOOL_RESULT_INJECTION = '''<%(marker)s function='{{function_name}}'{%% for k,v in arguments.items() %%} {{k}}='{{v}}'{%% endfor %%}>{{result | safe}}</%(marker)s>\n''' % {"marker":TOOL_RESPONSE_MARKER}
