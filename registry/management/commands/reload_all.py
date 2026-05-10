from contextlib import contextmanager
import os
import subprocess
import sys
from typing import List, Dict
import yaml
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from pathlib import Path
import frontmatter
from server.models.agents.agent import AgentModel
from server.models.agents.profile import ProfileModel
from server.models.agents.agent_version import AgentVersionModel
from registry.utils import generate_schema_for_function, get_import_strings, get_ai_model
from server.models.enums.task_enums import TaskType
from server.models.project import Project
from server.models.skill import Skill, SkillVersion
from server.models.tasks.task_definition import TaskDefinition
import textwrap
@contextmanager
def temp_sys_path(path:Path):
    """Temporarily adds a directory to sys.path."""
    pathstr = path.as_posix()
    if pathstr not in sys.path:
        sys.path.insert(0, pathstr)
        try:
            yield
        finally:
            sys.path.remove(pathstr)
    else:
        yield

def get_newstes_commit_hash(folder: Path):
    print("get_newstes_commit_hash", folder)
    try:
        cwd = folder if folder.is_dir() else folder.parent
        git_hash = subprocess.check_output(
            ["git", "log", "-n", "1", "--pretty=format:%h", "--", folder.as_posix()], stderr=subprocess.STDOUT, text=True, cwd=cwd
        ).strip()
        return git_hash
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e.output}")
    except FileNotFoundError:
        print("Git is not installed or not in your PATH.")
    return 

# FIND MARKDOWN / PYTHON FILES

def get_agentmd_files(root_dir: Path) -> List[Path]:
    """
    Recursively finds 'agent.md' files. 
    If found, it returns the path and skips that folder's subdirectories.
    """

    found_files = []
    def scan(directory):
        # Check if 'agent.md' exists in the current directory
        agent_file = directory / "agent.md"
        if agent_file.is_file():
            # Match found: add to list and stop recursion for this branch
            found_files.append(agent_file)
        else:
            # No match: search subdirectories
            try:
                for item in directory.iterdir():
                    if item.is_dir():
                        if item.name == ".git" or item.name.startswith("__pycache__"):
                            continue
                        scan(item)
            except PermissionError:
                # Handle directories with restricted access
                pass
    #scan(root_dir)
    paths:list[str|None] = [x.as_posix() for x in root_dir.glob("**/agent.md")]
    paths.sort(key=lambda p:len(paths))
    pathslen = len(paths)
    for index, path in enumerate(list(paths)):
        if not path:
            continue
        parent_str = Path(path).parent.as_posix()
        for index2 in range(index+1, pathslen):
            if not paths[index2]:
                continue
            if paths[index2].startswith(parent_str):
                paths[index2] = None

    return [Path(p) for p in paths if p]

def get_skillmd_files(root_dir: Path) -> List[Path]:
    """
    Recursively finds 'skill.md' files. 
    """
    return list(Path(root_dir).glob("**/skill.md"))

def get_python_script_files(root_dir: Path) -> List[Path]:
    """
    Recursively finds '*.py' files. 
    """
    files =  list(Path(root_dir).glob("**/*.py"))
    results = []
    for file in files:
        content = file.read_text()
        if '\n@tool(' in content or '\n@command(' in content or '\n@task(' in content:
            results.append(file)
    return results


# LOAD FILES 

def load_project_folder(folder: str):
    print("load_project_folder", folder)
    project_folder = Path(folder) / ".agentone"
    project = project_to_database(project_folder / "project.md")

    # Project Scripts
    project_python_files = get_python_script_files(project_folder / "scripts")
    for project_python_file in project_python_files:
        load_python_script_file(project_python_file, parent_project=project)
        
    # Project Skills
    project_skill_mds = get_skillmd_files(project_folder / "skills")
    for project_skill_md in project_skill_mds:
        load_skill_md_file(project_skill_md, parent_project=project)
        
    # Project Agents
    project_agent_mds = get_agentmd_files(project_folder / "agents")
    for project_agent_md in project_agent_mds:
        load_agent_md_file(project_agent_md, project)


def load_agent_md_file(agent_md_path:Path, parent_project = None, parent_agent=None):
    print("load_agent_folder", agent_md_path)
    agent = agentmd_to_database(agent_md_path, parent_project=parent_project, parent_agent=parent_agent)

    agent_md_parent = agent_md_path.parent

    # Agent Scripts
    project_python_files = get_python_script_files(agent_md_parent / "scripts")
    for project_python_file in project_python_files:
        load_python_script_file(project_python_file, parent_project=parent_project, parent_agent=agent)
        
    # Agent Skills
    local_skill_mds = get_skillmd_files(agent_md_parent / "skills")
    for local_skill_md in local_skill_mds:
        skill = load_skill_md_file(local_skill_md, parent_project=parent_project, parent_agent=agent)
        
    # Agent Sub Agents
    local_agent_mds = get_agentmd_files(agent_md_parent / "agents")
    for local_agent_md in local_agent_mds:
        load_agent_md_file(local_agent_md, parent_project=parent_project, parent_agent=agent)


def load_skill_md_file(skill_md_path:Path, parent_project = None, parent_agent=None):
    print("skill_md_path", skill_md_path)
    skill = skillmd_to_database(skill_md_path, parent_project=parent_project, parent_agent=parent_agent)
    for skill_tool_md in get_python_script_files(skill_md_path.parent / "scripts"):
        load_python_script_file(skill_tool_md, parent_project=parent_project, parent_agent=parent_agent, parent_skill=skill)


def load_python_script_file(python_script_path:Path, parent_project = None, parent_agent=None, parent_skill=None): 
    print("load_python_script_file", python_script_path)
    tool = python_script_to_database(python_script_path, parent_project=parent_project, parent_agent=parent_agent, parent_skill=parent_skill)
    

# SAVE TO DB

def agentmd_to_database(agent_md_path, parent_project = None, parent_agent = None, parent_skill=None):
    agent_md = frontmatter.load(agent_md_path)
    '''
        name	           Yes	    Unique identifier using lowercase letters and hyphens
        oldName             No      In case you rename the agent, so the system can find it
        description	       Yes	    When AgentOne should delegate to this subagent
        extends             No      Extend another agent, inherits all its stuff if not overwritten
        model	            No	    Model to use: sonnet, opus, haiku, a full model ID (for example, gemma4:e3b), or inherit. 
        maxRetries          No      In case of error, how many retries do we do
        maxTurns            No      Maximum number of agentic turns before the subagent stops
        maxUnattendedTurns  No      Maximum number of agentic turns before the subagent requires human confirmation
        maxHistoryMessages  No      Maximum number of historic messages the agent sees by default
        executionMode       No      TODO
        toolCallSyntax      No      Custom of default tool call syntax
        skills      	    No	    Skills to load into the subagent’s context at startup. Subagents don’t inherit skills from the parent conversation
        disallowedSkills    No	    Skills to deny, removed from inherited or specified list
        tools	            No	    Tools the agent can use. Inherits all tools if omitted
        disallowedTools	    No	    Tools to deny, removed from inherited or specified list
        tasks	            No	    Tasks the system can use, Inherits all tasks from parent
        disallowedTasks	    No	    Tasks to deny, removed from inherited or specified list
        commands	        No	    Commands the user can use, Inherits all commands from parent
        disallowedCommands  No	    Commands to deny, removed from inherited or specified list
    
    ''' 
    print("agentmd_to_database", agent_md_path)
    # Agent
    if agent_md.get("oldName", None):
        agent =  AgentModel.objects.get(name= agent_md.get("oldName"))
        agent.name = agent_md.get("name")
        agent.save()
    else:
        agent, created_agent = AgentModel.objects.get_or_create(name= agent_md.get("name"))

    # Profile
    aimodel = get_ai_model(agent_md.get("model"))
    extend_agents = []
    extend_agent_names = [x.strip() for x in agent_md.get("extends", "").split(",") if x.strip()]
    if extend_agent_names:
        extend_agents =  AgentModel.objects.filter(name__in= extend_agent_names)
       
    kwargs = {
        #"agent": agent,
        #"name": agent_md.get("name"),
        "aimodel": aimodel,
        #"description":  agent_md.get("description"),
        #"extendsAgentNames": extend_agent_names,
        "max_retries":  agent_md.get("maxRetries", None),
        "max_task_steps":  agent_md.get("maxTurns", None),
        "unattended_steps":  agent_md.get("maxUnattendedTurns", None),
        "max_history_messages":  agent_md.get("maxHistoryMessages", None),
        "execution_mode":  agent_md.get("executionMode", None),
        "tool_call_syntax":  agent_md.get("toolCallSyntax", None),
        
        "commandNames":  [x.strip() for x in agent_md.get("commands", "").split(",") if x.strip() if x.strip()],
        "disallowedCommandNames":  [x.strip() for x in agent_md.get("disallowedCommands", "").split(",") if  x.strip()],

        "taskNames": [x.strip() for x in agent_md.get("tasks", "").split(",")],
        "disallowedTaskNames": [x.strip() for x in agent_md.get("disallowedTasks", "").split(",") if x.strip()],
                
        "toolNames": [x.strip() for x in agent_md.get("tools", "").split(",")],
        "disallowedToolNames": [x.strip() for x in agent_md.get("disallowedTools", "").split(",") if x.strip()] ,

        "skillNames":  [x.strip() for x in agent_md.get("skills", "").split(",")],
        "disallowedSkillNames":  [x.strip() for x in agent_md.get("disallowedSkills", "").split(",") if x.strip()],

        "priority":   agent_md.get("priority", None),
        "thinking":  agent_md.get("thinking", None),

        #"task_prompt": GenericContent.from_text(profile.task_prompt) if profile.task_prompt else None,
        #"system_prompt": GenericContent.from_text(profile.system_prompt) if profile.system_prompt else None,
        "extra_settings":  agent_md.get("", None),
        "commit": get_newstes_commit_hash(agent_md_path),
    }
    kwargs = {k:v for k,v in kwargs.items() if v is not None}
    profile, created_profile = ProfileModel.objects.get_or_create(**kwargs)
    #if extend_agents:
    #    profile.extendsAgents.set(extend_agents)

    # AgentVersion
    current_version_number = 1
    if agent.latest_agent_version:
        current_version_number = agent.latest_agent_version.version_number
    
    '''
    parent_project = models.ForeignKey("server.Project", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills
    parent_agent = models.ForeignKey("server.AgentModel", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
    parent_skill = models.ForeignKey("server.Skill", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
    
    agent = models.ForeignKey("server.AgentModel"        , on_delete=models.CASCADE, related_name="related_agent_versions")

    description = models.TextField(max_length=65500, default="")
    extendsAgentNames = models.JSONField(default=list, blank=True)

    extendsAgents = SortedManyToManyField("server.AgentModel", related_name="related_inheritors", default=None, null=True)
    extendsAgentVersions = SortedManyToManyField("server.AgentVersionModel", related_name="related_inheritors", default=None, null=True)

    agent_profile = models.ForeignKey(ProfileModel ,default=None,null=True, on_delete=models.SET_NULL, related_name="related_agent_versions") # top level profile
     '''
    agent_version, created_agent_version = AgentVersionModel.objects.get_or_create(
        parent_project = parent_project,
        parent_agent = parent_agent,
        parent_skill = parent_skill,
        agent = agent,
        description = agent_md.get("description"),
        extendsAgentNames = extend_agent_names,
        commit = get_newstes_commit_hash(agent_md_path.parent),
        agent_profile = profile,
    )
    if created_agent_version:
        AgentVersionModel.objects.filter(pk=agent_version.pk).update(version_number = current_version_number +1)
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=agent_version)
    return agent


def skillmd_to_database(skill_md_path:Path, parent_project = None, parent_agent = None):
    '''
    name	       Yes	Max 64 characters. Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen.
    description	   Yes	Max 1024 characters. Non-empty. Describes what the skill does and when to use it.
    license	        No	License name or reference to a bundled license file.
    compatibility	No	Max 500 characters. Indicates environment requirements (intended product, system packages, network access, etc.).
    metadata	    No	Arbitrary key-value mapping for additional metadata.
    allowed-tools	No	Space-separated string of pre-approved tools the skill may use. (Experimental)
    '''
    skill_md = frontmatter.load(skill_md_path)
    skill, created_skill = Skill.objects.get_or_create(
        name = skill_md.get("name"),
        parent_agent = parent_agent,
        parent_project = parent_project,
    )

    skill_version, created_skillversion = SkillVersion.objects.get_or_create(
        skill = skill,
        description = skill_md.get("description"),
        path = skill_md_path,
        commit = get_newstes_commit_hash(skill_md_path.parent),
    )
    if created_skillversion:
        Skill.objects.filter(pk = skill.pk).update(latest_skill_version=skill_version)
        

    return skill


def python_script_to_database(python_script_path:Path, parent_project = None, parent_agent = None, parent_skill=None):
    '''
    name           
    task_type       = models.CharField(max_length=20, choices=TaskType.choices)
    description     = models.TextField()
    function_schema = models.JSONField()

    # Options - Startup
    requires_approval = models.BooleanField(default=False)  # required user approval before run
    
    # Options - Run
    time_limit      = models.IntegerField(default=None, null=True)     #   
    max_subtask_errors     = models.IntegerField(default=0)   # for groups,absolute number, also used when timeout
    max_subtask_error_rate = models.IntegerField(default=0)# for groups, in percent, also used when timeout
    limit_subtask_parallel_runs  = models.IntegerField(default=0) # how many subtasks cn run in parallel, for groups 0=no limit
    limit_per_instance_parallel_runs  = models.IntegerField(default=1) #how many times this task can run in parallel per agentInstance it belongs to, 0=no limit
    priority = models.IntegerField(default=0)   # 0 = highest, 1..999 less important

    # Options - Retry
    max_retries  = models.IntegerField(default=99)   # how many retries to we make in case of error
    retry_delay  = models.IntegerField(default=10)  # time between retries in seconds
    retry_requires_approval = models.BooleanField(default=True)  # required user approval before run

    trigger = models.CharField(max_length=255, default=None, blank=True, null=True)

    '''

    exec_globals = {"__builtins__": __builtins__}
    with temp_sys_path( python_script_path.parent):
        exec(python_script_path.read_text(encoding="utf-8"), exec_globals) # Execute the source code
    print("exec_globals", exec_globals)
    defs = {}
    for key, value in  exec_globals.items():
        if key == "__builtins__":
            continue
        if value and hasattr(value, "_task_definition"):
            task_def = value._task_definition.copy()
            # Task/Tool schema generation if missing
            if not task_def.get("schema") and task_def["task_type"] in [TaskType.TOOL, TaskType.TASK, TaskType.COMMAND]:
                # We pass the function to generate schema from its signature
                description, task_def["schema"] = generate_schema_for_function(value)
                task_def["description"]  = description

            existing_tasks_filter_kwargs = {
                "name": task_def.get("name"),
                "task_type": task_def["task_type"],
                "description": textwrap.dedent(task_def.get("description", "")),
                "trigger":  task_def.get("trigger", "") or "",
                "function_schema": task_def.get("schema", {}) or {}  ,
            }
            if requires_approval := task_def.get("requires_approval", None):
                existing_tasks_filter_kwargs["requires_approval"] = requires_approval
            if max_retries := task_def.get("max_retries", None):
                existing_tasks_filter_kwargs["max_retries"] = max_retries
            if retry_delay := task_def.get("retry_delay", None):
                existing_tasks_filter_kwargs["retry_delay"] = retry_delay
            if retry_requires_approval := task_def.get("retry_requires_approval", None):
                existing_tasks_filter_kwargs["retry_requires_approval"] = retry_requires_approval
            if priority := task_def.get("priority", None):
                existing_tasks_filter_kwargs["priority"] = priority
            if thinking := task_def.get("thinking", None) is not None:
                existing_tasks_filter_kwargs["thinking"] = thinking
            task_obj, created = TaskDefinition.objects.get_or_create(
                parent_skill = parent_skill,
                parent_agent = parent_agent,
                parent_project = parent_project,
                path = python_script_path,
                #commit = get_newstes_commit_hash(python_script_path.parent),
                **existing_tasks_filter_kwargs, # Use the same normalized fields for lookup
            )

    print(defs)
    return

    return tool


def project_to_database(project_md_path):
    '''
    name	       Yes	Max 64 characters. Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen.
    description	   Yes	Max 1024 characters. Non-empty. Describes what the project is
    '''
    project_md = frontmatter.load(project_md_path)
    project, created = Project.objects.get_or_create(
        name = project_md.get("name"),
        description = project_md.content,
        defaults = dict(
            path = project_md_path.parent,
        )
    )
    return project



class Command(BaseCommand):
    help = ''

    def add_arguments(self, parser):
        parser.add_argument('folder', type=str, help='Load .agentOne subfolder from folder')

    def handle(self, *args, **options):
        path = Path(options['folder']).resolve()
        if not path.exists():
            raise CommandError(f'Folder not found: {path.as_posix()}')
        
        agentone_path = path / ".agentone"
        if not agentone_path.exists():
            raise CommandError(f'no .agentOne subdir found in {path.as_posix()}')

        # Global Scripts
        project_python_files = get_python_script_files(agentone_path / "scripts")
        for project_python_file in project_python_files:
            load_python_script_file(project_python_file)

        # Global Skills
        local_skill_mds = get_skillmd_files(agentone_path / "skills")
        for local_skill_md in local_skill_mds:
            load_skill_md_file(local_skill_md)

        # Global Agents
        local_agent_mds = get_agentmd_files(agentone_path / "agents")
        for local_agent_md in local_agent_mds:
            load_agent_md_file(local_agent_md)

        with (agentone_path / "projects.yaml").open(encoding="utf-8") as f:
            project_paths =  yaml.safe_load(f) or []
            for project_path in project_paths:
                load_project_folder(project_path)
