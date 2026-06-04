import logging
import time
import threading
import sys
import re 
import os
import watchdog.observers.fsevents as fsevents
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers.fsevents import FSEventsEmitter
from dataclasses import dataclass, field

log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler = logging.StreamHandler(sys.stdout)
log_handler.setFormatter(log_formatter)
root_logger = logging.getLogger()
root_logger.addHandler(log_handler)
root_logger.setLevel(logging.DEBUG) # Set default level - change to DEBUG for more verbose output
fsevents.logger.setLevel(logging.DEBUG)  # Set log level to DEBUG


DEBUG = False
TESTS = '''
2025-05-13 05:08:23,873 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/fooobar", inode=190848082, flags=10800, id=903223066): is_file, is_renamed
2025-05-13 05:08:23,873 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/fooobar23", inode=190848082, flags=10800, id=903223067): is_file, is_renamed
2025-05-13 05:08:25,278 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/fooobar23", inode=190848082, flags=10800, id=903223079): is_file, is_renamed
2025-05-13 05:08:25,278 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/fooobar", inode=190848082, flags=10800, id=903223080): is_file, is_renamed

2025-05-13 02:58:18,508 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/Library/Application Support/Code/Cache/Cache_Data/index-dir/the-real-index", inode=190839926, flags=10800, id=903055169): is_file, is_renamed
2025-05-13 02:58:18,508 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/Library/Application Support/Code/Cache/Cache_Data/index-dir/the-real-index", inode=190839914, flags=10800, id=903055170): is_file, is_renamed

2025-05-13 02:58:21,869 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/Library/Application Support/Google/Chrome/Default/Preferences", inode=190839928, flags=10800, id=903055207): is_file, is_renamed
2025-05-13 02:58:21,870 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/Library/Application Support/Google/Chrome/Default/Preferences", inode=190839169, flags=10800, id=903055208): is_file, is_renamed

2025-05-13 03:09:40,869 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/Library/Biome/tmp/.tmp.9ctHRJeA", inode=190840804, flags=411700, id=903068801): is_cloned, is_coalesced, is_created, is_file, is_inode_meta_mod, is_modified, is_removed
2025-05-13 03:09:40,869 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/Library/Biome/tmp/.tmp.1twcj5TE", inode=190840807, flags=410700, id=903068822): is_cloned, is_coalesced, is_created, is_file, is_inode_meta_mod, is_removed

2025-05-13 03:09:40,869 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/Library/Biome/tmp/.tmp.AFp2gBfcGL", inode=190840805, flags=410900, id=903068796): is_cloned, is_coalesced, is_created, is_file, is_renamed
2025-05-13 03:09:40,869 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/Library/Biome/compute/sessions/C43E51BB-1E9A-4AB6-8F59-A264028D603C/bookmarks/server/com.apple.proactived/FocusModes.ReadingMode", inode=190840805, flags=10800, id=903068797): is_file, is_renamed
2025-05-13 03:09:40,869 - fsevents - DEBUG - NativeEvent(path="/Users/Dirk/Library/Biome/compute/sessions/C43E51BB-1E9A-4AB6-8F59-A264028D603C/bookmarks/server/com.apple.proactived/FocusModes.ReadingMode", inode=190840795, flags=10800, id=903068798): is_file, is_renamed
'''
def noop(*args,**kwargs):pass
debug_log = root_logger.debug if DEBUG else noop

# Filesystem Observer Class

class FsObserver:
    def __init__(self, observed_folders, aggregation_window=10, rename_window_timeout=5, exclude_patterns=None, callback=None):
        self.observed_folders = observed_folders
        self.aggregation_window = aggregation_window
        self.rename_window_timeout = rename_window_timeout
        self.exclude_patterns = exclude_patterns if exclude_patterns is not None else []
        self.callback = callback

        # Calculate CHECK_INTERVAL_SECONDS
        self.check_interval_seconds = min(self.aggregation_window, self.rename_window_timeout) / 2.0

        self.event_handler = AggregatingEventHandler(
            self.aggregation_window, 
            self.rename_window_timeout,
            self.exclude_patterns,
            self.callback
        )
        self.observer = Observer()

    def start(self):
        for folder in self.observed_folders:
            self.observer.schedule(self.event_handler, path=folder, recursive=True)
        self.observer.start()
        print(f"Watching: {self.observed_folders} (Aggregation Window(seconds): {self.aggregation_window}s)", flush=True)

    def stop(self):
        self.observer.stop()
        self.observer.join()
        self.event_handler.shutdown()
        print("Observer stopped.", flush=True)


# Monkey Patch for FsEvent so it just emits raw Generic Events
@dataclass(unsafe_hash=True)
class GenericEvent(FileSystemEvent):
    src_path: bytes | str
    event_type: str = field(default="generic")
    is_directory: bool = field(default=False)
    is_created: bool = field(default=False)
    is_modified: bool = field(default=False)
    is_removed: bool = field(default=False)
    is_renamed: bool = field(default=False)
    inode: int = field(default=0)

class MyFSEventsEmitter(FSEventsEmitter):
    def __init__(self, event_queue, watch, *, timeout = ..., event_filter = None, suppress_history = False):
        super().__init__(event_queue, watch, timeout=timeout, event_filter=event_filter, suppress_history=suppress_history)

    def queue_events(self, timeout: float, events: list[fsevents._fsevents.NativeEvent]) -> None:
        if fsevents.logger.getEffectiveLevel() <= logging.DEBUG:
            for event in events:
                flags = ", ".join(attr for attr in dir(event) if getattr(event, attr) is True)
                fsevents.logger.debug("%s: %s", event, flags)

        if self._starting_state is not None and time.monotonic() - self._start_time > 60:
            self._starting_state = None  # Event history is no longer needed, let's free some memory.

        for event in events:
            src_path = self._encode_path(event.path)
            if not(event.is_created or event.is_removed or event.is_modified or event.is_renamed):
                continue
            if event.is_created and event.is_removed:
                continue
            ge = GenericEvent(src_path)
            ge.is_directory = event.is_directory
            ge.is_created = event.is_created
            ge.is_removed = event.is_removed
            ge.is_modified = event.is_modified
            ge.is_renamed = event.is_renamed
            ge.inode = event.inode
            self.queue_event(ge)

fsevents.FSEventsEmitter = MyFSEventsEmitter


# Our Aggragation Logic
class PendingEvent():
    def __init__(self, path ):
        self.last_received_ts: float = 0.0
        self.path = path
        self.inode: int|None = None
        self.is_directory = False

        self.was_created:bool = False
        self.was_modified:bool = False
        self.was_removed:bool = False
        self.was_renamed:bool = False
        self.was_renamed_to:bool|None = None
        self.was_renamed_from:bool|None = None
        self.was_replaced:bool = False
        self.was_replaced_pending:bool = False # after rename another rename event for the same file may arrive but for a non existing inode, marking that the rename overwrote an existing file, otherwise it created a new file
        
        self.event_types_received = [] # Add list to track received event types, list to preserve order
        self.paired_event_path = None # Add attribute to link rename source/dest
        self.paired_event_inode:int|None = None # Add attribute to link rename source/dest by inode
        self.path_history = [] # Add list to store path history for rename tracking

    def __repr__(self):
        return f"PendingEvent(path='{self.path}', lastTs={self.last_received_ts} events={self.event_types_received}, created={self.was_created}, modified={self.was_modified}, removed={self.was_removed}, renamed={self.was_renamed}, renamed_from='{self.was_renamed_from}', renamed_to='{self.was_renamed_to}', paired_event='{self.paired_event_path}', paired_inode='{self.paired_event_inode}')"

    # Keep as_tup for compatibility if needed elsewhere, but repr is more informative

    def as_tup(self):
        t = [self.path]
        if self.is_directory:
            t += ["is_directory"]
        else:
            t += ["is_file"]
        if self.was_created:
            t += ["was_created"]
        if self.was_modified:
            t += ["was_modified"]
        if self.was_removed:
            t += ["was_removed"]
        if self.was_renamed:
            t += ["was_renamed"]
        if self.was_renamed_to is not None:
            t += ["was_renamed_to", self.was_renamed_to]
        if self.was_renamed_from is not None:
            t += ["was_renamed_from", self.was_renamed_from]
        if self.was_replaced:
            t += ["was_replaced"]
        if self.paired_event_path:
             t += ["paired_event", self.paired_event_path]
        if self.paired_event_inode:
             t += ["paired_inode", self.paired_event_inode]
        return t

class AggregatingEventHandler(FileSystemEventHandler):
    def __init__(self, aggregation_window, rename_window_timeout, exclude_patterns, callback):
        super().__init__()
        self.aggregation_window = aggregation_window
        self.rename_window_timeout = rename_window_timeout
        self.exclude_patterns = exclude_patterns
        self.callback = callback
        self.pending_events: dict[str, PendingEvent] = {} # Change from list to dictionary
        self.inode_to_path: dict[int, str] = {} # Map inode to current path for rename tracking
        self.inode_path_history: dict[int, list[tuple[str, float]]] = {} # Add dictionary to store inode path history
        self.shutdown_event = threading.Event()
        self.eventsbuffer_lock = threading.Lock()
        self.processor = threading.Thread(target=self._event_processor_thread, daemon=True)
        self.processor.start()

    def on_generic(self, inputEvent: GenericEvent):
        if inputEvent.is_created and inputEvent.is_removed:
            return
        debug_log(f"Received event: %s", inputEvent) 
        if not( inputEvent.is_created or inputEvent.is_modified or inputEvent.is_removed or inputEvent.is_renamed):
            debug_log(f"Ignoring event with no relevant flags: %s", inputEvent) 
            return

        # Check against excluded patterns
        if any(pattern in inputEvent.src_path for pattern in self.exclude_patterns):
            debug_log(f"Ignoring excluded path: %s", inputEvent.src_path) 
            return

        with self.eventsbuffer_lock:
            path = inputEvent.src_path
            current_time = time.time()
            inode = inputEvent.inode

            if path not in self.pending_events:
                debug_log(f"Creating new pending event for path: %s", path) 
                self.pending_events[str(path)] = PendingEvent(path)
                self.pending_events[str(path)].is_directory = inputEvent.is_directory
                self.pending_events[str(path)].inode = inode
            else:
                debug_log(f"Updating existing pending event for path: %s", path) 


            pending_event = self.pending_events[str(path)]
            pending_event.last_received_ts = current_time

            # Append the specific event type to the list
            if inputEvent.is_created:
                pending_event.was_created = True
                pending_event.event_types_received.append("created")
                debug_log(f"Added 'created' to %s", path) 
            if inputEvent.is_modified:
                pending_event.was_modified = True
                pending_event.event_types_received.append("modified")
                debug_log(f"Added 'modified' to %s", path) 
            if inputEvent.is_removed:
                pending_event.was_removed = True
                pending_event.event_types_received.append("removed")
                debug_log(f"Added 'removed' to %s", path) 
                # If a file is removed, remove its inode mapping
                if inode in self.inode_to_path and self.inode_to_path[inode] == path:
                     debug_log(f"Removing inode mapping for removed file: %s", inode) 
                     del self.inode_to_path[inode]

            if inputEvent.is_renamed:
                pending_event.was_renamed = True
                pending_event.event_types_received.append("renamed")
                debug_log(f"Added 'renamed' to %s", path) 

                # --- Start of added logic for inode path history ---
                if inode != 0:
                    if inode not in self.inode_path_history:
                        self.inode_path_history[inode] = []
                    self.inode_path_history[inode].append((str(path), current_time))
                    # Keep only history within the aggregation window
                    self.inode_path_history[inode] = [(p, t) for p, t in self.inode_path_history[inode] if current_time - t <= self.aggregation_window]
                    if not self.inode_path_history[inode]:
                         del self.inode_path_history[inode]
                # --- End of added logic ---

                # Improved rename pairing using inode
                if inode != 0: # Only attempt pairing if inode is provided
                    debug_log(f"Checking rename pair for inode %s. Current path: %s. Inode mapped to: %s", inode, path, self.inode_to_path.get(inode)) 
                    
                    # Check if this inode was previously mapped to a different path (potential source)
                    if inode in self.inode_to_path and self.inode_to_path[inode] != path:
                        potential_source_path = self.inode_to_path[inode]
                        # The current event's path is the potential destination
                        potential_destination_path = path

                        # Check if the potential source path is in pending_events
                        if potential_source_path in self.pending_events:
                            potential_source_event = self.pending_events[potential_source_path]

                            # Check if the potential source event is also a rename and within the rename window
                            if potential_source_event.was_renamed and current_time - potential_source_event.last_received_ts < self.rename_window_timeout:
                                 debug_log(f"Found potential rename pair based on inode %s: %s (source) and %s (destination)", inode, potential_source_path, potential_destination_path) 
                                 # Found a potential rename pair
                                 source_event = potential_source_event
                                 destination_event = pending_event # The current event is the destination

                                 # New logic for temporary file creation/rename sequence
                                 destination_event.was_replaced_pending = True 

                                 if source_event.was_created:
                                     debug_log(f"Source event %s was created. Removing source and marking destination as modified.", source_event.path) 
                                     if source_event.path in self.pending_events:
                                         del self.pending_events[source_event.path]
                                     if destination_event.was_renamed_from is None and "renamed" in destination_event.event_types_received:
                                         destination_event.event_types_received.remove("renamed")
                                     if "modified" not in destination_event.event_types_received:
                                         destination_event.event_types_received.append("modified")
                                     # No need to process this pair further in this block, it will be handled as a modified event for the destination
                                 else:
                                    source_event.was_renamed_from = source_event.path
                                    source_event.was_renamed_to = destination_event.path
                                    source_event.paired_event_path = destination_event.path
                                    source_event.paired_event_inode = inode

                                    destination_event.was_renamed_from = source_event.path
                                    destination_event.was_renamed_to = destination_event.path
                                    destination_event.paired_event_path = source_event.path
                                    destination_event.paired_event_inode = inode
                                    debug_log(f"Paired %s (source) and %s (destination)", source_event.path, destination_event.path) 

                            else:
                                 debug_log(f"Potential source event %s not a rename or outside rename window.", potential_source_path) 
                        else:
                             debug_log(f"Potential source path %s not in pending_events.", potential_source_path) 
                    else:
                        # This 'else' block is for cases where the current inode is not in inode_to_path or the path is the same.
                        # We check if this event is the confirming event for a pending replace operation.
                        if pending_event.was_replaced_pending:
                            # If the current event's inode is 0 or not in inode_to_path, it confirms the overwrite.
                            if inode == 0 or inode not in self.inode_to_path:
                                debug_log(f"Inode %s not found or is 0. Confirming replace for %s.", inode, path) 
                                pending_event.was_replaced = True
                                # If it was a replace, it's also a modification
                                if "modified" not in pending_event.event_types_received:
                                     pending_event.event_types_received.append("modified")
                                pending_event.was_modified = True
                                pending_event.was_replaced_pending = False # Resolve the pending state
                                # If it was previously marked as created due to the rename destination logic,
                                # remove created as it's now a modified/replaced event.
                                if "created" in pending_event.event_types_received:
                                     pending_event.event_types_received.remove("created")
                                     pending_event.was_created = False
                            else:
                                # This case should ideally not happen if the logic is correct,
                                # but as a fallback, if was_replaced_pending is true but inode exists,
                                # we might need to re-evaluate or log a warning. For now, just resolve pending.
                                debug_log(f"was_replaced_pending is true for %s but inode %s exists. Resolving pending state.", path, inode) 
                                pending_event.was_replaced_pending = False

                        debug_log(f"Inode %s not found in inode_to_path or path is the same.", inode) 

            # Always update the inode mapping for the current event's path AFTER all pairing logic
            if inode != 0:
                debug_log(f"Updating inode mapping: %s -> %s", inode, path) 
                self.inode_to_path[inode] = str(path)

            debug_log(f"Current pending events: %s", self.pending_events) 
            debug_log(f"Current inode_to_path: %s", self.inode_to_path)   
 

    def _event_processor_thread(self):
        debug_log("Event processor thread started.") 
        check_interval = min(self.aggregation_window, self.rename_window_timeout) / 2.0
        while not self.shutdown_event.is_set():
            current_time = time.time()
            debug_log(f"Event processor checking at %s", current_time) 
            debug_log(f"Current pending events: %s", self.pending_events) 

            with self.eventsbuffer_lock:
                # Process events based on inode path history
                inodes_to_process = list(self.inode_path_history.keys())
                for inode in inodes_to_process:
                    if inode not in self.inode_path_history:
                        continue # Already processed or removed

                    history = self.inode_path_history[inode]
                    # Sort history by timestamp
                    history.sort(key=lambda item: item[1])

                    # Keep only history within the aggregation window
                    history = [(p, t) for p, t in history if current_time - t <= self.aggregation_window]
                    if not history:
                        del self.inode_path_history[inode]
                        continue

                    # Determine the final state based on the history and pending events
                    final_event_type = None
                    source_path = history[0][0]
                    destination_path = history[-1][0]
                    paths_in_history = [p for p, t in history]

                    # Check for removed event in any of the paths in history
                    removed_found = any(p in self.pending_events and "removed" in self.pending_events[p].event_types_received for p in paths_in_history)
                    if removed_found:
                        final_event_type = "removed"
                    else:
                        # Check for created event in the destination path
                        created_found = destination_path in self.pending_events and "created" in self.pending_events[destination_path].event_types_received
                        # Check for modified event in any of the paths in history
                        modified_found = any(p in self.pending_events and "modified" in self.pending_events[p].event_types_received for p in paths_in_history)
                        # Check for rename event (source != destination)
                        renamed_found = source_path != destination_path
                        
                        if renamed_found:
                            final_event_type = "renamed"
                        elif created_found:
                            final_event_type = "created"
                        elif modified_found:
                            final_event_type = "modified"

                    renamed_found = any(p in self.pending_events and "renamed" in self.pending_events[p].event_types_received for p in paths_in_history)
                    if final_event_type is None and renamed_found and not os.path.exists(source_path):
                        final_event_type = "removed"

                    # Trigger callback if a final event type is determined
                    if final_event_type:
                        if final_event_type == "renamed":
                            print(f"Aggregated Event: Type={final_event_type}, From={source_path}, To={destination_path}", flush=True)
                            if self.callback:
                                self.callback(destination_path, final_event_type, old_path=source_path)
                        else:
                            print(f"Aggregated Event: Type={final_event_type}, Path={destination_path}", flush=True)
                            if self.callback:
                                self.callback(destination_path, final_event_type)

                    # Clean up pending events and inode history for this inode
                    for path in paths_in_history:
                        if path in self.pending_events:
                            del self.pending_events[path]
                    if inode in self.inode_path_history:
                        del self.inode_path_history[inode]
                    # Remove inode mapping
                    if inode in self.inode_to_path:
                         del self.inode_to_path[inode]

                # Process remaining expired pending events that don't have inode history
                paths_to_process = []
                for path, pending_event in list(self.pending_events.items()):
                    if current_time - pending_event.last_received_ts >= self.aggregation_window:
                        paths_to_process.append(path)

                for path in paths_to_process:
                    pending_event = self.pending_events.get(path, None)
                    if not pending_event:
                        continue # Already processed as part of an inode history
                    final_event_type = None

                    if "removed" in pending_event.event_types_received:
                        final_event_type = "removed"
                    elif "created" in pending_event.event_types_received:
                        if "removed" in pending_event.event_types_received:
                            final_event_type = None # Created and removed results in no event
                            debug_log(f"%s was created and removed, resulting in no event.", path)
                        else:
                            final_event_type = "created"
                    elif "modified" in pending_event.event_types_received:
                        final_event_type = "modified"
                    # Note: Renames should ideally be handled by inode history processing

                    if final_event_type:
                        print(f"Aggregated Event: Type={final_event_type}, Path={pending_event.path}", flush=True)
                        if self.callback:
                            self.callback(pending_event.path, final_event_type)

                    # Remove after processing
                    if path in self.pending_events:
                        del self.pending_events[path]
                    # Inode mapping should have been removed if it had history,
                    # or it didn't have history to begin with.


            self.shutdown_event.wait(check_interval) # Wait before next check, but wake up sooner if shutdown is requested
        debug_log("Event processor thread finished.")

    def shutdown(self):
        self.shutdown_event.set()
        check_interval = min(self.aggregation_window, self.rename_window_timeout) / 2.0
        self.processor.join(timeout=check_interval + 2) # Wait a bit longer than check interval


def simulate_events_from_log(event_handler: AggregatingEventHandler):
    log_pattern = re.compile(r".*? - fsevents - DEBUG - NativeEvent\(path=\"(.*?)\", inode=(\d+), flags=(\d+), id=(\d+)\): (.*)")

    for line in TESTS.split("\n"):
        match = log_pattern.search(line)
        if match:
            path, inode, flags, id, event_flags_str = match.groups()
            # Parse flags string into boolean attributes
            event_flags = [flag.strip() for flag in event_flags_str.split(',')]
            is_directory = "is_directory" in event_flags
            is_created = "is_created" in event_flags
            is_modified = "is_modified" in event_flags
            is_removed = "is_removed" in event_flags
            is_renamed = "is_renamed" in event_flags
            simulated_event = GenericEvent(
                src_path=path,
                is_directory=is_directory,
                is_created=is_created,
                is_modified=is_modified,
                is_removed=is_removed,
                is_renamed=is_renamed,
                inode=int(inode),
            )
            event_handler.on_generic(simulated_event)

def my_callback(path, event_type, old_path=None):
    # event_type  in  created, modified, renamed, removed
    if event_type == "renamed":
        print(f"Aggregated Event (Callback): Type={event_type}, From={old_path}, To={path}", flush=True)
    else:
        print(f"Aggregated Event (Callback): Type={event_type}, Path={path}", flush=True)



if __name__ == "__main__":
    # Example usage of MyObserver
    if len(sys.argv) == 1:
        print("unknown parameters, add target folders to observe or test to run tests")
        exit(0)



    if len(sys.argv) >= 2 and sys.argv[1] == "test":
        event_handler = AggregatingEventHandler(
            aggregation_window=10,
            rename_window_timeout=5,
            exclude_patterns=[
                '/.git/',
                '/node_modules/',
                '/__pycache__/',
                '/.venv/',
                '/.DS_Store', 
            ],
            callback=my_callback # Pass the callback here for the test simulation
        )
        simulate_events_from_log(event_handler=event_handler)
        time.sleep(max(10, 5, min(10, 5)/2.0)*2.5) # Use the default values for sleep calculation
        event_handler.shutdown() # Ensure the processor thread is shut down
        exit(0)


    observer_instance = FsObserver(
        observed_folders=sys.argv[1:],
        aggregation_window=10,
        rename_window_timeout=5,
        exclude_patterns=[
            '/.git/',
            '/node_modules/',
            '/__pycache__/',
            '/.venv/',
            '/.DS_Store',
        ],
        callback=my_callback # Pass the callback function
    )

    try:
        observer_instance.start()
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received, shutting down...", flush=True)
    finally:
        observer_instance.stop()
        print("Shutdown complete.", flush=True)
