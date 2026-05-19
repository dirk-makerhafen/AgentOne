from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal, Optional, Type


from typing import TYPE_CHECKING
#if TYPE_CHECKING:

class Subagent():
    """
    Declares the metadata and lifecycle rules for a subagent type.
    """
    def __init__(self,
                 agent_class: Type, 
                 create: Literal["auto", "agent", "user", "both"] = "both", 
                 visible_to: Literal["agent", "user", "creator", "both"] = "both", 
                 workingdir: str|Path|None=None, 
                 instance_name: Optional[str] = None) -> None:
        """The class of the subagent (e.g., FilesystemAgent).

        Defines how instances of this subagent are created:
        - 'auto': Automatically instantiated once when the parent agent is initialized.
                These are core, always-available components. Requires `instance_name`.
                The parent agent has a direct attribute reference to this instance.
        - 'agent': Instances are created on demand by the parent agent for specific task delegation.
                Multiple independent instances can run concurrently. The parent agent
                manages references to the instances it creates.
        - 'user': Instances are created on demand when the user directly initiates an interactive
                session with this agent type (e.g., ChatAssistant).
        - 'both': Can be created by either the parent agent (for delegation) or directly by the user.
        """
        self.agent_class = agent_class
        self.create_option = create
        self.visible_to = visible_to
        self.instance_name = instance_name
        self.workingdir = workingdir
        # --- Validation for instance_name based on create_option ---
        if self.create_option == "auto":
            if self.instance_name is None:
                # Infer default instance_name if not provided for 'auto'
                inferred_name = self.agent_class.__name__.lower()
                if inferred_name.endswith("agent"):
                    inferred_name = inferred_name[:-5] # Remove common suffix for cleaner names
                self.instance_name = inferred_name
        elif self.instance_name is not None:
            raise ValueError(
                f"Subagent '{self.agent_class.__name__}' has `create='{self.create_option}'` "
                "but an `instance_name` was specified. `instance_name` is only valid when `create='auto'`."
            )


        # --- Validation for visible_to consistency with create_option ---
        if self.create_option == "user" and self.visible_to not in ["user", "both"]:
            raise ValueError(
                f"Subagent '{self.agent_class.__name__}' is user-creatable (`create='user'`) "
                "but `visible_to` is not 'user' or 'both'. User-creatable agents must be user-visible."
            )
        if self.create_option == "both" and self.visible_to != "both":
            raise ValueError(
                f"Subagent '{self.agent_class.__name__}' is creatable by both (`create='both'`) "
                "but `visible_to` is not 'both'. Agents creatable by both must be visible to both."
            )
        if self.create_option == "creator" and self.visible_to not in ["creator", "both"]:
             raise ValueError(
                f"Subagent '{self.agent_class.__name__}' is creatable by creator (`create='creator'`) "
                "but `visible_to` is not 'creator' or 'both'. Agents creatable by creator must be visible to creator."
            )



class Subagents():
    """
    A container class to hold multiple Subagent declarations.
    Allows accessing declarations by attribute (e.g., `parent.subagents.my_subagent`).
    """
    def __init__(self, **kwargs: Subagent) -> None:
        self._subagents: Dict[str, Subagent] = kwargs
        #for k, v in kwargs.items():
        #    setattr(self, k, v) # Binds the Subagent declaration directly to an attribute

    def get(self, name: str) -> Optional[Subagent]:
        """Retrieves a Subagent declaration by its given name."""
        return self._subagents.get(name)

    def all(self) -> Dict[str, Subagent]:
        """Returns all Subagent declarations."""
        return self._subagents

    def runtime_init(self, parent_runtime:BaseAgent):
        for key, subagent in self._subagents.items():
            if subagent.create_option == "auto":
                workingdir = parent_runtime.workingdir or ""
                if subagent.workingdir:
                    if Path(subagent.workingdir).is_absolute():
                        workingdir = subagent.workingdir
                    else:
                        workingdir = Path(workingdir) / Path(subagent.workingdir)

                # We need a closure to capture the current subagent and workingdir
                def make_getter(sa, wd, key, parent_runtime):
                    def get_lazy_rt(self):
                        attr_cache_name = f"_ref_{key}"
                        if hasattr(self, attr_cache_name):
                            return getattr(self, attr_cache_name)
                        rt = sa.agent_class(workingdir=wd, parent=parent_runtime)
                        setattr(self, attr_cache_name, rt)
                        return rt
                    return get_lazy_rt
                # Attach to the CLASS of parent_runtime
                #setattr(parent_runtime, key, property(make_getter(subagent, workingdir, key, parent_runtime)))
                setattr(parent_runtime, key, subagent.agent_class(workingdir=workingdir, parent=parent_runtime))
                #setattr(type(parent_runtime), key, property(make_getter(subagent, workingdir, key, parent_runtime)))
