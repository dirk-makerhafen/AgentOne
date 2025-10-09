from datetime import datetime, timezone
import functools
import time
from django.db import models
from core.models.base_model import BaseModel
from executor.primitives import append_file, list_directory, mkdir, read_file, rm, stat_path, write_file
from tools.builtin_filesystem.utils import summarize
from tools.builtin_filesystem.utils.fsutils import apply_patch, format_directory_listing, get_relative_path, make_patch





class FsLogEntryManager(models.Manager):
    def get_or_create_latest(self, agentInstance, path, toolCall=None, action="init", load_mode=None, filter=None, recursive=None, must_be_file=False, must_exist=False):
        """
        Acts as a dispatcher to either create a new FsLogEntry from disk or refresh an existing one.
        Handles validation errors by returning (False, error_dict) and lets system errors raise exceptions.
        """
        snapshot = self.get_queryset().filter(agentInstance=agentInstance, path=path, is_newest_version=True).order_by("-pk").first()

        if not snapshot:
            return self._create_initial_from_disk(
                agentInstance=agentInstance, path=path, toolCall=toolCall, action=action,
                load_mode=load_mode, filter=filter, recursive=recursive,
                must_be_file=must_be_file, must_exist=must_exist
            )
        else:
            return self._refresh_existing(
                snapshot=snapshot, toolCall=toolCall, action=action,
                load_mode=load_mode, filter=filter, recursive=recursive,
                must_be_file=must_be_file, must_exist=must_exist
            )

    def _create_initial_from_disk(self, agentInstance, path, toolCall, action, load_mode, filter, recursive, must_be_file, must_exist):
        """
        Handles the creation of the very first FsLogEntry for a given path.
        """
        # System call: can raise an exception
        stat_result = stat_path(agentInstance=agentInstance, path=path)
        if stat_result.get("status") != "success":
            raise IOError(f"Failed to get stats for {path}: {stat_result}")

        # Validation checks: return specific errors
        if must_exist and not stat_result.get("exists", False):
            return False, {"error": f"{path} does not exist"}
        if must_be_file and stat_result.get("exists", False) and not stat_result.get("is_file", False):
            return False, {"error": f"{path} is not a file"}

        new_content = ""
        if stat_result.get("exists", False):
            if stat_result.get("is_dir", False):
                read_result = list_directory(agentInstance=agentInstance, path=path, recursive=recursive or False)
                if read_result.get("status") != "success":
                    raise IOError(f"Could not read directory {path}: {read_result}")
                new_content = format_directory_listing(read_result.get("content", []))
            else:
                read_result = read_file(agentInstance=agentInstance, path=path)
                if read_result.get("status") != "success":
                    raise IOError(f"Could not read file {path}: {read_result}")
                new_content = read_result.get("content", "")

        snapshot = FsLogEntry(
            agent=agentInstance.agent,
            agentInstance=agentInstance,
            toolCall=toolCall,
            path=path,
            filter=filter or "",
            recursive=recursive or False,
            load_mode=load_mode,
            is_directory=stat_result.get("is_dir", False),
            exists_on_fs=stat_result.get("exists", False),
            fs_created=datetime.fromtimestamp(stat_result.get("ctime", time.time()), tz=timezone.utc),
            fs_modified=datetime.fromtimestamp(stat_result.get("mtime", time.time()), tz=timezone.utc),
            fs_lastread=datetime.now(tz=timezone.utc),
            fs_size=stat_result.get("size", 0) if stat_result.get("is_file", False) else len(new_content),
            action=action,
            content_diff=new_content,
            stored_as="full",
            summary=summarize(path, new_content) if load_mode == "summary" else "",
        )
        snapshot.save()
        return True, snapshot

    def _refresh_existing(self, snapshot, toolCall, action, load_mode, filter, recursive, must_be_file, must_exist):
        """
        Handles refreshing an existing FsLogEntry and performing post-refresh checks.
        """
        # System call: can raise an exception
        result = snapshot.refresh_from_disk(
            toolCall=toolCall,
            action=action,
            recursive=recursive if recursive is not None else snapshot.recursive,
            filter=filter or snapshot.filter,
            load_mode=load_mode or snapshot.load_mode
        )

        # Validation checks: return specific errors
        if must_exist and not result.exists_on_fs:
            return False, {"error": f"{result.path} does not exist"}
        if must_be_file and result.is_directory:
            return False, {"error": f"{result.path} is not a file"}

        # Post-refresh logic
        if result and result.load_mode == 'summary' and result.summary is None:
            result.summary = summarize(result.path, result.content)
            result.save(send_to_client=False)

        return True, result
    






class FsLogEntry(BaseModel):

    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name='fsFileLogEntries')
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='fsFileLogEntries')
    conversationMessage = models.ForeignKey("agents.ConversationMessage", on_delete=models.CASCADE, related_name='fsFileLogEntries', null=True, default=None)
    toolCall = models.ForeignKey("calls.ToolCall", on_delete=models.CASCADE, related_name='fsFileLogEntries', null=True, default=None)
    
    prev_version = models.ForeignKey("self", on_delete=models.CASCADE, related_name='next_versions', null=True, default=None)
    reverted_from_entry = models.ForeignKey("self", on_delete=models.SET_NULL, related_name='reverted_by_entries', null=True, default=None)
    is_newest_version = models.BooleanField(default=True, db_index=True)
    
    path = models.CharField(max_length=512) 
    filter = models.CharField(null=True, default=None, max_length=4096) 
    recursive = models.BooleanField(default=False)

    load_mode = models.CharField(max_length=16, null=True, default=None, db_index=True) # full, summary, None (not loaded)
    is_pinned = models.BooleanField(default=False)
    is_directory = models.BooleanField(default=False)
    exists_on_fs = models.BooleanField(default=False)

    fs_created = models.DateTimeField(default=None, null=True)
    fs_modified = models.DateTimeField(default=None, null=True)
    fs_lastread = models.DateTimeField(default=None, null=True)
    fs_size = models.IntegerField(default=0) 

    action = models.CharField(max_length=16)

    content_diff = models.TextField(max_length=10 * 1024 * 1024, default=b'')
    stored_as = models.CharField(max_length=16) # patch, full, append, replace
    summary = models.CharField(null=True, blank=True, default=None)


    objects = FsLogEntryManager()

    @property
    @functools.lru_cache(maxsize=1000) 
    def content(self):
        if self.stored_as == "full":
            return self.content_diff
        
        if self.stored_as == "patch":  
            return apply_patch(self.prev_version.content if self.prev_version else "",  self.content_diff )
        
        if self.stored_as == "prepend":
            return self.content_diff + (self.prev_version.content if self.prev_version else "")
        
        if self.stored_as == "append":
            return (self.prev_version.content if self.prev_version else "") + self.content_diff
        
        if self.prev_version:
            return self.prev_version.content
        
        return None

    def write(self, content, toolCall= None):
        """
        Overwrite the file with content, and create a new snapshot version.
        """
        write_result = write_file(agentInstance=self.agentInstance, path=self.path, content=content)
        if write_result.get("status") != "success":
            return False, {'status': 'failed', "message": f"Failed to write file {self.path}: {write_result}"}
        
        stat_result = stat_path(agentInstance=self.agentInstance, path=self.path)
        if stat_result.get("status") != "success":
            return False, {'status': 'failed', "message": f"Failed to read file stats after write to {self.path}: {stat_result}"}
        
        stored_as, content_diff = self._get_storage_method(self.content or "", content)
        new_snapshot = self.create_next_version(
            toolCall = toolCall,
            action = "write",
            fs_created = datetime.fromtimestamp(stat_result.get("ctime", time.time()), tz=timezone.utc),
            fs_modified = datetime.fromtimestamp(stat_result.get("mtime", time.time()), tz=timezone.utc),
            fs_lastread = datetime.now(tz=timezone.utc),
            fs_size = stat_result.get("size", 0),
            stored_as = stored_as,
            content_diff = content_diff,

        )
        return True, new_snapshot

    def append(self, content, toolCall = None):
        """
        Append content to the file, and create a new snapshot version.
        """
        append_result = append_file(agentInstance=self.agentInstance, path=self.path, content=content)
        if append_result.get("status") != "success":
            return False, {'status': 'failed', "message": f"Failed to append file {self.path}: {append_result}"}

        # Read the full content back after append
        read_result = read_file(agentInstance=self.agentInstance, path=self.path)
        if read_result.get("status") != "success":
            return False, {'status': 'failed', "message": f"Failed to re-read file after append to{self.path}: {read_result}"}
        
        # Get updated file stats
        stat_result = stat_path(agentInstance=self.agentInstance, path=self.path)
        if stat_result.get("status") != "success":
            return False, {'status': 'failed', "message": f"Failed to re-read file stats after append to {self.path}: {stat_result}"}
        
        # Create new snapshot
        new_content = read_result.get("content", "")
        stored_as, content_diff = self._get_storage_method(self.content or "", new_content)
        new_snapshot = self.create_next_version(
            toolCall = toolCall,
            action = "append",
            fs_created = datetime.fromtimestamp(stat_result.get("ctime", time.time()), tz=timezone.utc),
            fs_modified = datetime.fromtimestamp(stat_result.get("mtime", time.time()), tz=timezone.utc),
            fs_lastread = datetime.now(tz=timezone.utc),
            fs_size = stat_result.get("size", 0),
            stored_as = stored_as,
            content_diff = content_diff,

        )
        return True, new_snapshot

    def refresh_from_disk(self, toolCall=None, recursive=None, filter=None, load_mode=None, action=None):
        """
        Compares the current snapshot with the on-disk state and creates a new version if there are changes in the file's state or the requested view.
        """
        # Part 1: GATHER all necessary information.
        # ----------------------------------------
        requested_view = {
            'recursive': recursive if recursive is not None else self.recursive,
            'filter': filter if filter is not None else self.filter,
            'load_mode': load_mode if load_mode is not None else self.load_mode
        }
        action = action or "refresh"

        on_disk_stat = stat_path(agentInstance=self.agentInstance, path=self.path)
        if on_disk_stat.get("status") != "success":
            # If stat fails, we can't proceed. Raising an exception is safest as the state is unknown.
            raise Exception(f"Failed to read file stats for {self.path}: {on_disk_stat}")

        on_disk_content = ""  # Default to empty string for non-existent files
        if on_disk_stat.get("exists", False):
            if on_disk_stat.get("is_dir", False):
                read_result = list_directory(agentInstance=self.agentInstance, path=self.path, recursive=requested_view['recursive'])
                if read_result.get("status") != "success":
                    raise Exception(f"Could not read directory {self.path}: {read_result}")
                on_disk_content = format_directory_listing(read_result.get("content", []))
            else:  # is_file
                read_result = read_file(agentInstance=self.agentInstance, path=self.path)
                if read_result.get("status") != "success":
                    raise Exception(f"Could not read file {self.path}: {read_result}")
                on_disk_content = read_result.get("content", "")

        # Part 2: DECIDE if a new version is needed.
        # ------------------------------------------
        view_has_changed = (
            requested_view['recursive'] != self.recursive or
            requested_view['filter'] != self.filter or
            requested_view['load_mode'] != self.load_mode
        )

        # Optimized check for files: if view hasn't changed and metadata is the same, skip expensive content comparison.
        is_unchanged_file = False
        if not view_has_changed and self.exists_on_fs and not self.is_directory and on_disk_stat.get("exists", False) and not on_disk_stat.get("is_dir", False):
            db_mtime_ts = self.fs_modified.timestamp() if self.fs_modified else None
            if on_disk_stat.get("mtime") == db_mtime_ts and on_disk_stat.get("size") == self.fs_size:
                is_unchanged_file = True

        state_has_changed = False
        if not is_unchanged_file:
            state_has_changed = (
                on_disk_stat.get("exists", False) != self.exists_on_fs or
                on_disk_stat.get("is_dir", False) != self.is_directory or
                on_disk_content != self.content
            )

        should_create_new_version = view_has_changed or state_has_changed

        # Part 3: ACT on the decision.
        # ----------------------------
        self.fs_lastread = datetime.now(tz=timezone.utc)
        self.save(send_to_client=False)

        if not should_create_new_version:
            return self

        stored_as, content_diff = self._get_storage_method(self.content or "", on_disk_content)

        fs_created_ts = on_disk_stat.get("ctime")
        fs_modified_ts = on_disk_stat.get("mtime")

        return self.create_next_version(
            toolCall=toolCall,
            action=action,
            recursive=requested_view['recursive'],
            filter=requested_view['filter'],
            load_mode=requested_view['load_mode'],
            is_directory=on_disk_stat.get("is_dir", False),
            exists_on_fs=on_disk_stat.get("exists", False),
            fs_created=datetime.fromtimestamp(fs_created_ts, tz=timezone.utc) if fs_created_ts is not None else self.fs_created,
            fs_modified=datetime.fromtimestamp(fs_modified_ts, tz=timezone.utc) if fs_modified_ts is not None else self.fs_modified,
            fs_lastread=self.fs_lastread,
            fs_size=on_disk_stat.get("size", 0) if on_disk_stat.get("is_file", False) else len(on_disk_content),
            stored_as=stored_as,
            content_diff=content_diff,
            summary=summarize(self.path, on_disk_content) if load_mode == "summary" else "",
        )

    def create_next_version(self, **kwargs):
        print("create_next_version", kwargs)
        new_version = FsLogEntry(
            agent = self.agent,
            agentInstance = self.agentInstance,
            path = self.path,
            filter = self.filter,
            recursive = self.recursive,            
            load_mode = self.load_mode,
            is_pinned = self.is_pinned,
            is_directory = self.is_directory,
            exists_on_fs = self.exists_on_fs,
            fs_created = self.fs_created,
            fs_modified = self.fs_modified,
            fs_lastread = self.fs_lastread,
            fs_size = self.fs_size,
            is_newest_version = True,
            prev_version = self,
        )
        for key, value in kwargs.items():
            setattr(new_version, key, value)
        new_version.save()
        self.is_newest_version = False
        self.save()
        return new_version

    def _get_storage_method(self, existing_content, new_content):
        print("_get_storage_method", existing_content, new_content)
        if existing_content == new_content:
            return "", ""
        methods = [["full", new_content], ]
        if existing_content and new_content:
            if new_content.startswith(existing_content):
                methods.append(["append", new_content[len(existing_content):]])
            if new_content.endswith(existing_content):
                methods.append(["prepend", new_content[:-len(existing_content):]])
            methods.append(["patch",  make_patch(existing_content, new_content)])
        # get shorttest representation
        shortest = sorted([m + [len(m[1])] for m in methods], key=lambda x:x[2])[0]
        return shortest[0], shortest[1]

    def as_client_dict(self, include_content=False, include_summary=False):
        calculated_tokens = 0
        if self.load_mode == "summary" and self.summary:
            calculated_tokens = len(self.summary) // 3.8
        elif self.load_mode == "full" and self.content:
            calculated_tokens = len(self.content) // 3.8
        elif not self.is_directory and self.exists_on_fs:
            calculated_tokens = self.fs_size

        data = {
            'object': 'FsLogEntry', 
            'id': self.id,

            'created_at': self.created_at.isoformat(), 
            "agent_id": self.agent_id, 
            "agentInstance_id": self.agentInstance_id, 
            "toolCall_id": self.toolCall_id,

            'action': self.action, 
            'is_newest_version': self.is_newest_version,
            'prev_version_id': self.prev_version_id,

            'path': get_relative_path(self.agentInstance.workingdir, self.path), 
            'filter': self.filter,
            'recursive': self.recursive,

            'load_mode': self.load_mode,
            'is_loaded': self.load_mode in ['full', 'summary'],
            'is_pinned': self.is_pinned,
            'is_directory': self.is_directory,
            'exists_on_fs': self.exists_on_fs,

            'fs_created': self.fs_created.isoformat(), 
            'fs_modified': self.fs_modified.isoformat(), 
            'fs_lastread': self.fs_lastread.isoformat(), 
            'fs_size': self.fs_size, 
            'tokens' : calculated_tokens, 
        }

        if include_content:
            data['content'] = self.content
            data['prev_content'] = self.prev_version.content if  self.prev_version else ''

        if include_summary:
            data['summary'] = self.summary

        return data

    def __str__(self):
        return f"FS:{self.pk} {self.path}"

    def undo(self, toolCall=None):
        """
        Reverts the file to the state *before* this entry (self) was created.
        This action creates a new 'revert' FsLogEntry, which becomes the new newest version.
        Its 'prev_version' points to the FsLogEntry representing the state *before* 'self'.
        """
        # Step 1: Determine the target content and existence state to revert to.
        # This is the state of the file *before* 'self' was created.
        # use self in case used did click to revert the very first entry
        revert_to_item = self.prev_version if self.prev_version else self 
        content_to_restore = revert_to_item.content if revert_to_item else ""

        # Step 2: Perform the actual file system operation (delete, create dir, or write file).
        if not revert_to_item.exists_on_fs: # If reverting to a state where the file/dir didn't exist
            try:
                stat_result = stat_path(agentInstance=self.agentInstance, path=self.path)
                if stat_result.get("status") != "success":
                    return False, {'status': 'failed', "message": f"Failed to read file stats after revert-write/delete for {self.path}: {stat_result}"}

                if stat_result.get("exists", False): # Check if it actually exists on disk before trying to remove
                    rm_result = rm(agentInstance=self.agentInstance, path=self.path, recursive=True)
                    if rm_result.get("status") != "success":
                        return False, {'status': 'failed', "message": f"Failed to read file stats after revert-write/delete for {self.path}: {stat_result}"}
                write_result = {'status': 'success'} # Simulate success for deletion, stat will confirm non-existence
            except OSError as e:
                return False, {'status': 'failed', "message": f"Failed to delete {self.path} during revert: {e}"}

        else: # did exist
            if revert_to_item.is_directory:
                stat_result = stat_path(agentInstance=self.agentInstance, path=self.path)
                if stat_result.get("status") != "success":
                    return False, {'status': 'failed', "message": f"Failed to read file stats after revert-write/delete for {self.path}: {stat_result}"}

                if not stat_result.get("exists", False):  # did exist but no longer, restore dir
                    try:
                        mkdir_result = mkdir(self.path, parents=True, exist_ok=True) 
                        if mkdir_result.get("status") != "success":
                            return False, {'status': 'failed', "message": f"Failed to read file stats after revert-write/delete for {self.path}: {stat_result}"}
                        write_result = {'status': 'success'}
                    except OSError as e:
                        return False, {'status': 'failed', "message": f"Failed to create directory {self.path} during revert: {e}"}
                else:
                    write_result = {'status': 'success'} # Directory already exists
            
            else: # Reverting to a file state with content
                write_result = write_file(agentInstance=self.agentInstance, path=self.path, content=content_to_restore)
                if write_result.get("status") != "success":
                    return False, {'status': 'failed', "message": f"Failed to write file during revert for {self.path}: {write_result}"}

        # Step 3: Get the new file stats from the disk after writing/deleting.
        stat_result = stat_path(agentInstance=self.agentInstance, path=self.path)
        if stat_result.get("status") != "success":
            return False, {'status': 'failed', "message": f"Failed to read file stats after revert-write/delete for {self.path}: {stat_result}"}

        # Step 4: Update `is_newest_version` flags and create the new 'revert' FsLogEntry.
        # Find the *current* newest entry for this path and mark it as not newest. (use all in case for some bug multiple got marked(should never happen)))
        current_newest_entries_for_path = FsLogEntry.objects.filter(agentInstance=self.agentInstance, path=self.path, is_newest_version=True).all()
        for current_newest_entry_for_path in current_newest_entries_for_path:
            current_newest_entry_for_path.is_newest_version = False
            current_newest_entry_for_path.save(send_to_client=False) # Don't send object update twice
        if self in current_newest_entries_for_path: # because code above doe not reload these items
            self.is_newest_version = False
        if revert_to_item in current_newest_entries_for_path:
            revert_to_item.is_newest_version = False

        new_snapshot = revert_to_item.create_next_version(
            toolCall=toolCall,
            action="revert",
            is_directory=stat_result.get("is_dir", False),
            exists_on_fs=stat_result.get("exists", False), # This should be consistent with stat_result
            fs_created=datetime.fromtimestamp(stat_result.get("ctime", time.time()), tz=timezone.utc),
            fs_modified=datetime.fromtimestamp(stat_result.get("mtime", time.time()), tz=timezone.utc),
            fs_lastread=datetime.now(tz=timezone.utc),
            fs_size=stat_result.get("size", 0) if stat_result.get("is_file", False) else len(content_to_restore),
            stored_as="", 
            content_diff=""# content is same a in version_to_restore (prev_version)
        )
        print(new_snapshot, new_snapshot.is_newest_version)
        return True, new_snapshot



