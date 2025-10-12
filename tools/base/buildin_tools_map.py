# Map built-in tool names (as they appear in ToolDefinition.name) to their Python classes.
from tools.builtin_a2a.a2a_tool import A2ATool
from tools.builtin_filesystem.filesystem_tool import FilesystemTool
from tools.builtin_memory.memory_tool import MemoryTool
from tools.builtin_python.python_tool import PythonTool
from tools.builtin_shell.shell_tool import ShellTool
from tools.builtin_subscriptions.subscriptions_tool import SubscriptionsTool
from tools.builtin_userinteraction.user_interaction_tool import UserInteractionTool


BUILTIN_TOOL_CLASS_MAP = {
    'filesystem': FilesystemTool,
    'memory': MemoryTool,
    'python': PythonTool,
    'a2a': A2ATool,
    'userinteraction': UserInteractionTool,
    'shell': ShellTool,
    'subscriptions': SubscriptionsTool,
}