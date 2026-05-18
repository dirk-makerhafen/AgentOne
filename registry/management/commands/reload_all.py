from contextlib import contextmanager
import hashlib
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
from server.models.settings import SettingsModel
from server.models.agents.agent_version import AgentVersionModel
from registry.utils import generate_schema_for_function, get_import_strings, get_ai_model
from server.models.content import GenericContent
from server.models.enums.task_enums import TaskType
from server.models.project import Project
from server.models.skills.skill import SkillModel, SkillModelVersion
from server.models.tasks.task_definition import TaskDefinition
import textwrap

from server.models.tasks.task_definition_version import TaskDefinitionVersion
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
    #print("get_newstes_commit_hash", folder)
    try:
        cwd = folder if folder.is_dir() else folder.parent
        git_hash = subprocess.check_output(
            ["git", "log", "-n", "1", "--pretty=format:%h", "--", folder.as_posix()], stderr=subprocess.STDOUT, text=True, cwd=cwd
        ).strip()
        print("git hash found", git_hash)
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
        skill, skill_version = load_skill_md_file(project_skill_md, parent_project=project)

    # Project Agents
    project_agent_mds = get_agentmd_files(project_folder / "agents")
    for project_agent_md in project_agent_mds:
        agent, agent_version = load_agent_md_file(project_agent_md, parent_project=project)


def load_agent_md_file(agent_md_path:Path, parent_project = None, parent_agent=None, parent_skill=None):
    print("load_agent_folder", agent_md_path)
    agent_md_parent = agent_md_path.parent

    agent_md = frontmatter.load(agent_md_path)
    '''
        name	           Yes	    Unique identifier using lowercase letters and hyphens
        oldName             No      In case you rename the agent, so the system can find it
        description	       Yes	    When AgentOne should delegate to this subagent
        extends             No      Extend another agent, inherits all its stuff if not overwritten
        model	            No	    Model to use: sonnet, opus, haiku, a full model ID (for example, gemma4:e3b), or inherit. 
        reasoningEffort     No      Reasoning effort to use: none (default), minimal, low, medium, high, xhigh
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
        agent =  AgentModel.objects.get(name= agent_md.get("oldName"), parent_project = parent_project, parent_agent = parent_agent, parent_skill = parent_skill)
        agent.name = agent_md.get("name")
        agent.save()
    else:
        agent, created_agent = AgentModel.objects.get_or_create(name= agent_md.get("name"), parent_project = parent_project, parent_agent = parent_agent, parent_skill = parent_skill)

    # Agent Skills
    defined_skills = []
    local_skill_mds = get_skillmd_files(agent_md_parent / "skills")
    for local_skill_md in local_skill_mds:
        skill, skill_version = load_skill_md_file(local_skill_md, parent_agent=agent)
        defined_skills.append((skill, skill_version))

    # Agent Scripts
    defined_tasks = []
    project_python_files = get_python_script_files(agent_md_parent / "scripts")
    for project_python_file in project_python_files:
        defined_tasks.extend(load_python_script_file(project_python_file, parent_agent=agent))

    # Agent Sub Agents
    local_agent_mds = get_agentmd_files(agent_md_parent / "agents")
    defined_subagents = []
    for local_agent_md in local_agent_mds:
        subagent, subagent_version = load_agent_md_file(local_agent_md, parent_agent=agent)
        defined_subagents.append((subagent, subagent_version))

    # Settings
    aimodel = get_ai_model(agent_md.get("model"))
    extend_agents = []
    def get_list(name):
        l = agent_md.get(name)
        if l is None:
            return l
        if isinstance(l, str):
            l = l.split(",")
        return [x.strip() for x in l if x.strip()]
    
    extend_agent_names = get_list("extends")
    print("FOO232323", extend_agent_names)
    kwargs = {
        #"agent": agent,
        #"name": agent_md.get("name"),
        "aimodel": aimodel,
        #"description":  agent_md.get("description"),
        #"extends_agent_names": extend_agent_names,
        "max_retries":  agent_md.get("maxRetries", None),
        "max_turns":  agent_md.get("maxTurns", None),
        "max_unattended_turns":  agent_md.get("maxUnattendedTurns", None),
        "max_history_messages":  agent_md.get("maxHistoryMessages", None),
        "execution_mode":  agent_md.get("executionMode", None),
        "tool_call_syntax":  agent_md.get("toolCallSyntax", None),
        "reasoning_effort":  agent_md.get("reasoningEffort", None),
        
        "commandNames":  get_list("commands"),
        "disallowedCommandNames":  get_list("disallowedCommands"),

        "taskNames": get_list("tasks"),
        "disallowedTaskNames": get_list("disallowedTasks"),
                
        "toolNames": get_list("tools"),
        "disallowedToolNames": get_list("disallowedTools") ,

        "skillNames": get_list("skills"),
        "disallowedSkillNames":  get_list("disallowedSkills"),

        "priority":   agent_md.get("priority", None),
        "thinking":  agent_md.get("thinking", None),

        "task_prompt": GenericContent.from_text(agent_md.get("task_prompt", "").strip()) ,
        "system_prompt":  GenericContent.from_text(agent_md.content.strip()) ,
        "extra_settings":  agent_md.get("", None),
        "commit": get_newstes_commit_hash(agent_md_path),
    }
    settings, createdsettings = SettingsModel.objects.get_or_create(**kwargs)

    # AgentVersion
    current_version_number = 1
    if agent.latest_agent_version:
        current_version_number = agent.latest_agent_version.version_number
    
    '''
    AgentVersionModel:
    agent = models.ForeignKey("server.AgentModel"        , on_delete=models.CASCADE, related_name="related_agent_versions")
    description = models.TextField(max_length=65500, default="")
    extends_agent_names = models.JSONField(default=list, blank=True)
    extends_agent_versions = SortedManyToManyField("self", related_name="related_inheritors", default=None, null=True)
    defined_skill_versions = models.ManyToManyField(SkillVersion ,default=None,null=True,  related_name="related_agent_versions") # top level profile
    defined_task_versions = models.ManyToManyField(TaskDefinitionVersion ,default=None,null=True, related_name="related_agent_versions") # top level profile
    defined_subagent_versions = models.ManyToManyField("self", related_name="related_parents", default=None, null=True)
    agent_settings = models.ForeignKey(SettingsModel ,default=None,null=True, on_delete=models.SET_NULL, related_name="related_agent_versions") # top level profile
    version_number = models.IntegerField(default=0)
    '''
    extend_agent_versions = []
    for extend_agent_name in extend_agent_names:
        extend_agent = AgentModel.objects.get(name= extend_agent_name)
        extend_agent_versions.append(extend_agent.latest_agent_version)

    hashstr = "_".join([f"{s}" for s in ([x.pk for x in extend_agent_versions] + extend_agent_names + sorted([s[1].pk for s in defined_skills]) +  sorted([s[1].pk for s in defined_tasks]) +  sorted([s[1].pk for s in defined_subagents]))])
    hash = hashlib.sha1(hashstr.encode()).hexdigest()
    agent_version, created_agent_version = AgentVersionModel.objects.get_or_create(
        agent = agent,
        description = agent_md.get("description"),
        extends_agent_names = extend_agent_names,
        commit = get_newstes_commit_hash(agent_md_path.parent),
        agent_settings = settings,
        hash = hash,
    )
    if created_agent_version:
        AgentVersionModel.objects.filter(pk=agent_version.pk).update(version_number = current_version_number +1)
        AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=agent_version)
        agent_version.defined_skill_versions.set([x[1] for x in defined_skills])
        agent_version.defined_task_versions.set([x[1] for x in defined_tasks])
        agent_version.defined_subagent_versions.set([x[1] for x in defined_subagents])
        print("extend_agent_versions", extend_agent_versions)
        agent_version.extends_agent_versions.set(extend_agent_versions)

    return agent, agent_version

def load_skill_md_file(skill_md_path:Path, parent_project = None, parent_agent=None):
    print("skill_md_path", skill_md_path)
    '''
    name	       Yes	Max 64 characters. Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen.
    description	   Yes	Max 1024 characters. Non-empty. Describes what the skill does and when to use it.
    license	        No	License name or reference to a bundled license file.
    compatibility	No	Max 500 characters. Indicates environment requirements (intended product, system packages, network access, etc.).
    metadata	    No	Arbitrary key-value mapping for additional metadata.
    allowed-tools	No	Space-separated string of pre-approved tools the skill may use. (Experimental)
    '''
    skill_md = frontmatter.load(skill_md_path)
    skill, created_skill = SkillModel.objects.get_or_create(
        name = skill_md.get("name"),
        parent_agent = parent_agent,
        parent_project = parent_project,
    )

    skill_version, created_skillversion = SkillModelVersion.objects.get_or_create(
        skill = skill,
        description = skill_md.get("description"),
        path = skill_md_path,
        commit = get_newstes_commit_hash(skill_md_path.parent),
    )
    if created_skillversion:
        SkillModel.objects.filter(pk = skill.pk).update(latest_skill_version=skill_version)

    #for skill_tool_md in get_python_script_files(skill_md_path.parent / "scripts"):
    #    load_python_script_file(skill_tool_md, parent_project=parent_project, parent_agent=parent_agent, parent_skill=skill)
    return skill, skill_version

def load_python_script_file(python_script_path:Path, parent_project = None, parent_agent=None, parent_skill=None): 
    print("load_python_script_file", python_script_path)
    tasks= python_script_to_database(python_script_path, parent_project=parent_project, parent_agent=parent_agent, parent_skill=parent_skill)
    return tasks

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
    #print("exec_globals", exec_globals)
    results = []
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
                #"name": task_def.get("name"),
                #"task_type": task_def["task_type"],
                "description": textwrap.dedent(task_def.get("description", "")),
                "trigger":  task_def.get("trigger", "") or "",
                "function_schema": task_def.get("schema", {}) or {}  ,
            }
            if (requires_approval := task_def.get("requires_approval", None)):
                existing_tasks_filter_kwargs["requires_approval"] = requires_approval
            if (max_retries := task_def.get("max_retries", None)) is not None:
                existing_tasks_filter_kwargs["max_retries"] = max_retries
            if (retry_delay := task_def.get("retry_delay", None)) is not None:
                existing_tasks_filter_kwargs["retry_delay"] = retry_delay
            if (retry_requires_approval := task_def.get("retry_requires_approval", None)) is not None:
                existing_tasks_filter_kwargs["retry_requires_approval"] = retry_requires_approval
            if (priority := task_def.get("priority", None)) is not None:
                existing_tasks_filter_kwargs["priority"] = priority
            if (thinking := task_def.get("thinking", None)) is not None:
                existing_tasks_filter_kwargs["thinking"] = thinking

            task_definition, task_definition_version_created = TaskDefinition.objects.get_or_create(
                parent_skill = parent_skill,
                parent_agent = parent_agent,
                parent_project = parent_project,
                name = task_def.get("name"),
                task_type = task_def["task_type"],
            )
            task_definition_version, task_definition_version_created = TaskDefinitionVersion.objects.get_or_create(
                task_definition = task_definition,
                path = python_script_path,
                commit = get_newstes_commit_hash(python_script_path.parent),
                **existing_tasks_filter_kwargs, # Use the same normalized fields for lookup
            )
            if task_definition_version_created:
                TaskDefinition.objects.filter(pk = task_definition.pk).update(latest_task_version=task_definition_version)
            results.append((task_definition, task_definition_version))

    return results


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
            skill, skill_version = load_skill_md_file(local_skill_md)

        # Global Agents
        local_agent_mds = get_agentmd_files(agentone_path / "agents")
        for local_agent_md in local_agent_mds:
            agent, agent_version = load_agent_md_file(local_agent_md)

        with (agentone_path / "projects.yaml").open(encoding="utf-8") as f:
            project_paths =  yaml.safe_load(f) or []
            for project_path in project_paths:
                load_project_folder(project_path)
