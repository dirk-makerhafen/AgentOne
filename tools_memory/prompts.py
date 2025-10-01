
DESCRIPTION = '''
# Memory Tools
You have access to external memory tool that help you remember things. Because your context length is limited, you must use this memory 
for all information thats valid for more than a few rounds of conversation. Old messages in our conversation will be tagged with @@@TO_BE_FORGOTTEN@@@.
Pay special attention to these messages so you don't forget important information.
Your context contains a special memory section with content representing different memory tracks and time layers. 
These memories store past events, insights, future steps, learned behaviors, goals, and other important details you need as an AGI agent.
You manage several parallel memory tracks (SELF, REVIEW, INSIGHTS, GOALS, STATUS, SYSTEMS, PLANS, PREDICTIONS, MEMORY).
Your memory works like an append only log, with the posibility to correct the last few memories in case they contain errors. 
Items are added to your memory via memory_add. To repair incorrect memory items use memory_correct, but only to correct actually incorrect memory items, or to mark items as completed. Don't change memory text from future/current to past, if
you want to mark tasks/plans/goals with tags, add for example [done],[completed] or [failed]. 
Don't use memory_correct to overwrite older memory items, your memory is a endless appendable log. 
The latest items of your current memory will be injected below. You will only see a limited number of items. Item that may fall our of context when you add more items to a track/layer
will be tagged with [to be forgotten, review now!]. Use the Medium-Term memory for information derived or learned from the Short-Term memory, and use the Long-Term memory for important thinks that might device from Medium-Term memories. 
When you seem to forget a memory track, a hint (starting with !ATTENTION:) will be shown in your current memory content below.

## Memory Tracks:
SELF: What, Where, Why and Who we are. 
REVIEW: What went right or wrong.
INSIGHTS: What we learned  
GOALS: What we want
STATUS: Where we are now in our progress
SYSTEMS: How we work towards success 
PLANS: Steps to make it happen
PREDICTIONS: What we expect to happen next
MEMORY: What happened what we don't want to forget

Each track has three time horizons:
- ST (Short-Term): The last/next few dozen turns or steps.
- MT (Medium-Term): Summaries of multiple ST items, lasting across multiple related tasks or sessions.
- LT (Long-Term): Permanent knowledge — summaries of MT that are relevant to all future work.

## Rules for Memorizing
Always store if:
- The information is important and would be lost otherwise.
- It clearly fits a memory track category.
- It impacts future decisions, goals, processes, or understanding.
- A message begins with @@@TO_BE_FORGOTTEN@@@ but contains unsaved info.

Never store:
- Trivial chatter or pleasantries.
- Common knowledge available elsewhere.
- Outdated or irrelevant information.
- Full file/tool outputs — only save necessary summaries of paths
- If unsure → pick the shortest time layer that will last long enough.

## Output format
Your current memory content will be injected below as a user messages in the following format:

## track_name - track_description
### track_name layer_name - layer_description
- [index][to be forgotten, review now!] content
- [index] content
- [index] content

You never output memory in this format! You MUST always use memory_add to write to your memory. 
Never output memory content without wrapping it in a memory tool call. 

'''

FUNCTIONS = {
    "memory_add": {
        "description": "Add content to memory",
        "parameters": {
            "track": { "type": "string", "description": "Target memory track", "required": True},
            "layer": { "type": "string", "description": "Target memory layer", "required": True},
            "content": { "type": "string", "description": "Content to add to memory", "required": True}
        },
    },
    "memory_correct": {
        "description": "Correct a memory entry if it contains incorrect information or is confusing. Use sparsely only to correct memory entries. To add to your memory, use memory_add",
        "parameters": {
            "track": { "type": "string", "description": "Target memory track", "required": True},
            "layer": { "type": "string", "description": "Target memory layer", "required": True},                
            "index": { "type": "string", "description": "Index of item to correct", "required": True},
            "content": {"type": "string", "description": "Updated content for memory index", "required": True}
        },
    },
    "memory_reposition": {
        "description": "Reposition a memory entry",
        "parameters": {
            "track": { "type": "string", "description": "Target memory track", "required": True},
            "layer": { "type": "string", "description": "Target memory layer", "required": True},                
            "index": { "type": "string", "description": "Index of item to reposition", "required": True},
            "steps": { "type": "number", "description": "How many index positions we move up or down (positive or negative number)", "required": True }
        },
    },       
}

TRACKS = {
    "REVIEW": {
        "description": "Track and evaluate performance over time — spotting what worked, what failed, and why. Spot common llm errors like hallucinations or bad instruction/rule following. Highlights successes, mistakes, and quality issues. Detects patterns in results to guide future improvements. ",
        "layers": {
            "ST": "Immediate reflection on the most recent actions or exchanges. Quick notes on clarity, completeness, and relevance.",
            "MT": "Aggregated trends from several ST reviews. Recurring strengths, weaknesses, or opportunities for improvement.",
            "LT": "Enduring performance patterns and lessons from long-term observation. Historical record of sustained strengths or systemic problems.",
        }
    },
    "SELF": {
        "description": "Defines the identity, role, capabilities, and purpose of the agent — the 'What, Where, Why, and Who.' Captures what you are, who you serve, why you exist, and the boundaries of your role. Includes key constraints, permissions, and unique traits. Summarizes your current environment and capabilities.",
        "layers": {
            "ST": "Immediate context for your current role or active session. Current operational limits or constraints.",
            "MT": "Summary of your identity and mission that remains stable across related tasks. Any mid-term changes to role, capabilities, or environment.",
            "LT": "Permanent identity, core principles, and unchanging traits. Enduring mission, vision, and key constraints.",
        }
    },
    "STATUS": {
        "description": "Snapshot of current position in progress toward goals. Captures “where we are now” in plans, systems, and goals. Helps you quickly orient without rereading full history.",
        "layers": {
            "ST": "Current active task and present conditions. Live state of work in progress. The smallest tasks require a few turns.",
            "MT": "Summary of status over several related sessions or tasks. Key shifts in progress or state.",
            "LT": "Rare — used only if a stable ongoing state must be remembered for long-term reference.",
        }
    },
    "INSIGHTS": {
        "description": "Store what has been learned — new knowledge, understanding, or perspectives gained. Can be from successes, failures, analysis, or experiments. Includes “aha moments” and refined mental models.",
        "layers": {
            "ST": "Fresh insights from the latest few actions or exchanges.",
            "MT": "Generalized lessons from multiple ST insights. Themes or trends in learning.",
            "LT": "Deep, durable principles and facts worth keeping forever. Core wisdom and knowledge to guide future work.",
        }
    },
    "GOALS": {
        "description": "Capture desired outcomes, from small tasks to big ambitions. Answers 'What are we trying to achieve?'. Tracks active goals, progress, and completion/failure states.",
        "layers": {
            "ST": "Short, actionable objectives for immediate focus. Tasks achievable in a single session, a short time frame, or a few llm conversation turns.",
            "MT": "Mid-range milestones that require multiple ST goals to complete. Achievements planned for the near to mid future.",
            "LT": "Major, long-term ambitions or visions. Overarching aims that may take months or years to reach.",
        }
    },
    "SYSTEMS": {
        "description": "Preserve effective, repeatable ways of working — methods, routines, and frameworks that enable success. Encapsulates “how we do things” when it works well. Records updates when a system changes, improves, or fails.",
        "layers": {
            "ST": "Processes or habits for immediate use in the current context. Temporary tweaks to workflows for ongoing tasks.",
            "MT": "Reusable processes applied across related tasks or sessions. Stable methods that last beyond a single session.",
            "LT": "Core philosophies, timeless frameworks, and enduring best practices. Universal systems that can guide work across all future contexts.",
        }
    },
    "PLANS": {
        "description": "Define clear sequences of actions to achieve goals. Shows “what happens next” and in what order. Tracks active progress and changes to plans as they evolve.",
        "layers": {
            "ST": "Immediate, actionable next steps for the current goal. Steps that can be executed within the next few turns or hours.",
            "MT": "Chains of ST actions forming a complete medium-sized project or objective. Covers multiple sessions or phases.",
            "LT": "Road roadmap for major goals and long-term vision. Defines stages, milestones, and dependencies at a high level.",
        }
    },
    "PREDICTIONS": {
        "description": "Record what is expected to happen next, or the anticipated result of an action, tool call, or decision. Captures assumptions and reasoning about future states. Allows later comparison between expected and actual outcomes to refine accuracy.",
        "layers": {
            "ST": "Immediate short-term expectations after a few steps or tool calls. Predictions about the next few turns or actions.",
            "MT": "Patterns or trends in predictions from multiple ST entries. Medium-horizon forecasts based on recent developments.",
            "LT": "Stable predictive models or recurring long-term expectations. Anticipated future events or states far ahead in the roadmap.",
        }
    },
    "MEMORY":  {
        "description": "Stores critical factual context. This includes both historical events ('what happened') and enduring project-specific guidelines ('what is'), such as coding styles, architectural patterns, and key technical decisions. This track is for raw reference points, not interpretations or lessons learned (which belong in INSIGHTS).",
        "layers": {
            "ST": "Recent events, facts, or temporary project-specific notes to keep temporarily.",
            "MT": "Summaries of ST memories or project guidelines relevant across multiple tasks (e.g., 'Use snake_case for all functions in this feature').",
            "LT": "Permanent project records. Includes foundational architectural decisions, core coding standards, and major historical project milestones.",
        }
    },
}

STALLED_WARNING = '''
# Warning:
Some of your memory has not been updated for a long time, please review the following memory tracks:
{% for stall in stalled %}
Track:{{stall.0}} Layer:{{stall.1}}
{% endfor %}
'''

CONTENT_HEADER = '''
# Current Memory Content ({{current_time}}):
'''

CONTENT = '''{% if warn_stall %}!ATTENTION: {{ trackname }} {{ layername }} not updated for a long time.\n{% endif %}{% for item in memories %}
- [{{item.index}}]{% if item.warn_forget %}[to be forgotten, review now!]{% endif %} {{item.content | safe}}
{% endfor %}{% if not memories %}!Attention, no entries yet{% endif %}
'''



helpfullexample = '''

## MEMORY - Important factual events and context that must not be forgotten. Raw historical facts, reference points, or non-trivial data points. Not interpretation or lessons — just “what happened”.
### MEMORY ST - Recent events or facts to keep temporarily.
- [23] ...
### MEMORY MT - Summary of multiple ST memories that may be needed across tasks.
### MEMORY LT - Permanent historical record — major past events and their key facts.
'''