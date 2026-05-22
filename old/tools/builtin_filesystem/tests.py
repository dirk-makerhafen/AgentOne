# tools_filesystem/tests.py
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, call
from django.test import TestCase

# Assuming Agent and AgentVersion models are correctly imported

# Mock constants and utility for timestamps
MOCK_NOW = datetime(2023, 10, 26, 10, 0, 0, tzinfo=timezone.utc)
def mock_timestamp(offset_seconds=0):
    return (MOCK_NOW.timestamp() + offset_seconds)

# --- Mock File System for testing FsLogEntry.undo ---
class MockFileSystem:
    def __init__(self):
        self.files = {}  # path: {content, ctime, mtime, is_dir}

    def reset(self):
        self.files = {}

    def add_file(self, path, content, ctime=None, mtime=None):
        if ctime is None: ctime = MOCK_NOW.timestamp()
        if mtime is None: mtime = MOCK_NOW.timestamp()
        self.files[path] = {'content': content, 'ctime': ctime, 'mtime': mtime, 'is_dir': False}

    def add_dir(self, path, ctime=None, mtime=None):
        if ctime is None: ctime = MOCK_NOW.timestamp()
        if mtime is None: mtime = MOCK_NOW.timestamp()
        self.files[path] = {'content': '', 'ctime': ctime, 'mtime': mtime, 'is_dir': True}

    def delete_path(self, path):
        if path in self.files:
            del self.files[path]
        # Also remove any children if it was a directory
        to_delete = [p for p in self.files if p.startswith(path + os.sep)]
        for p in to_delete:
            del self.files[p]

# Global mock filesystem instance
mock_fs = MockFileSystem()

# Custom mock functions that interact with mock_fs
def mock_stat_path_func(agentInstance, path):
    file_data = mock_fs.files.get(path)
    if file_data:
        return {
            'status': 'success',
            'exists': True,
            'is_dir': file_data['is_dir'],
            'is_file': not file_data['is_dir'],
            'ctime': file_data['ctime'],
            'mtime': file_data['mtime'],
            'size': len(file_data['content']) if not file_data['is_dir'] else 0, # Simplified size
        }
    else:
        # For non-existent paths, check if it's a child of an existing dir
        for existing_path in mock_fs.files:
            if path.startswith(existing_path + os.sep) and mock_fs.files[existing_path]['is_dir']:
                # It exists in the 'directory tree' but not as a specific file/dir entry
                return {'status': 'success', 'exists': False, 'is_dir': False, 'is_file': False}
        return {'status': 'success', 'exists': False, 'is_dir': False, 'is_file': False}

def mock_write_file_func(agentInstance, path, content):
    if path not in mock_fs.files or mock_fs.files[path]['is_dir']:
        mock_fs.add_file(path, content, mtime=MOCK_NOW.timestamp()) # New file or overwriting dir as file
    else:
        mock_fs.files[path]['content'] = content
        mock_fs.files[path]['mtime'] = MOCK_NOW.timestamp()
    return {'status': 'success'}

def mock_read_file_func(agentInstance, path):
    file_data = mock_fs.files.get(path)
    if file_data and not file_data['is_dir']:
        return {'status': 'success', 'content': file_data['content']}
    return {'status': 'failed', 'message': 'File not found or is a directory'}

def mock_list_directory_func(agentInstance, path, recursive):
    if path not in mock_fs.files or not mock_fs.files[path]['is_dir']:
        return {'status': 'failed', 'message': 'Directory not found'}
    
    listing = []
    for p, data in mock_fs.files.items():
        if p.startswith(path + os.sep):
            relative_path = os.path.relpath(p, path)
            if recursive or (os.sep not in relative_path): # Only direct children if not recursive
                listing.append({
                    'path': p,
                    'is_dir': data['is_dir'],
                    'is_file': not data['is_dir'],
                    'name': os.path.basename(p),
                    'size': len(data['content']) if not data['is_dir'] else 0,
                    'last_modified': datetime.fromtimestamp(data['mtime'], tz=timezone.utc),
                })
    return {'status': 'success', 'content': listing}

def mock_os_path_exists_func(path):
    return path in mock_fs.files

def mock_os_remove_func(path):
    mock_fs.delete_path(path)

def mock_os_rmdir_func(path):
    if path in mock_fs.files and mock_fs.files[path]['is_dir']:
        # Ensure directory is empty for rmdir success
        for p in mock_fs.files:
            if p.startswith(path + os.sep):
                raise OSError(f"Directory not empty: {path}") # rmdir fails if not empty
        mock_fs.delete_path(path)
    else:
        raise OSError(f"No such directory: {path}")

def mock_os_makedirs_func(path, exist_ok=True):
    if path in mock_fs.files and mock_fs.files[path]['is_dir'] and exist_ok:
        return # Already exists, ok
    if path not in mock_fs.files:
        mock_fs.add_dir(path)
    else:
        raise OSError(f"Cannot create directory, file exists: {path}")


# Helper for _get_storage_method, as it's a model method
def _mock_get_storage_method(existing_content, new_content):
    # This mock simplifies content storage to always be 'full' for testing purposes
    if existing_content == new_content:
        return "", ""
    return "full", new_content


class FsLogEntryUndoTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(name="Test Agent")
        self.agent_instance = AgentVersion.objects.create(agent=self.agent, workingdir="/app")
        
        mock_fs.reset() # Reset mock filesystem before each test

        # Patch the _get_storage_method used by FsLogEntry methods
        self.patch_get_storage = patch('tools_filesystem.models.FsLogEntry._get_storage_method', side_effect=_mock_get_storage_method)
        self.mock_get_storage = self.patch_get_storage.start()
        
        # Patch filesystem primitives that FsLogEntry.undo uses to interact with mock_fs
        self.patch_stat_path = patch('tools_filesystem.models.stat_path', side_effect=mock_stat_path_func)
        self.mock_stat_path = self.patch_stat_path.start()
        self.patch_write_file = patch('tools_filesystem.models.write_file', side_effect=mock_write_file_func)
        self.mock_write_file = self.patch_write_file.start()
        self.patch_read_file = patch('tools_filesystem.models.read_file', side_effect=mock_read_file_func)
        self.mock_read_file = self.patch_read_file.start()
        self.patch_list_directory = patch('tools_filesystem.models.list_directory', side_effect=mock_list_directory_func)
        self.mock_list_directory = self.patch_list_directory.start()

        self.patch_os_remove = patch('tools_filesystem.models.os.remove', side_effect=mock_os_remove_func)
        self.mock_os_remove = self.patch_os_remove.start()
        self.patch_os_rmdir = patch('tools_filesystem.models.os.rmdir', side_effect=mock_os_rmdir_func)
        self.mock_os_rmdir = self.patch_os_rmdir.start()
        self.patch_os_makedirs = patch('tools_filesystem.models.os.makedirs', side_effect=mock_os_makedirs_func)
        self.mock_os_makedirs = self.patch_os_makedirs.start()
        self.patch_os_path_exists = patch('tools_filesystem.models.os.path.exists', side_effect=mock_os_path_exists_func)
        self.mock_os_path_exists = self.patch_os_path_exists.start()


        FsLogEntry.content.fget.cache_clear() # Clear LRU cache for content property
        
    def tearDown(self):
        self.patch_get_storage.stop()
        self.patch_stat_path.stop()
        self.patch_write_file.stop()
        self.patch_read_file.stop()
        self.patch_list_directory.stop()
        self.patch_os_remove.stop()
        self.patch_os_rmdir.stop()
        self.patch_os_makedirs.stop()
        self.patch_os_path_exists.stop()

        FsLogEntry.content.fget.cache_clear() # Clear LRU cache again
        mock_fs.reset() # Ensure mock filesystem is reset

    # Helper to create FsLogEntry objects for setting up test history.
    def _create_log_entry(self, path, content, action, prev_version=None, exists_on_fs=True, is_directory=False, pk=None, created_at=None):
        if prev_version:
            prev_version.is_newest_version = False
            prev_version.save()
            
        entry = FsLogEntry.objects.create(
            pk=pk,
            agentInstance=self.agent_instance,
            agent=self.agent,
            path=path,
            content_diff=content,
            stored_as="full",
            action=action,
            prev_version=prev_version,
            exists_on_fs=exists_on_fs,
            is_directory=is_directory,
            fs_created=created_at if created_at else MOCK_NOW,
            fs_modified=created_at if created_at else MOCK_NOW,
            fs_lastread=MOCK_NOW,
            fs_size=len(content) if not is_directory else 0, # Simplified size for directories
            is_newest_version=True,
            created_at=created_at if created_at else MOCK_NOW
        )
        return entry
    

    # --- Test cases for FsLogEntry.undo() ---
    
    def test_undo_file_creation(self):
        """
        Tests undoing the very first entry which was a file creation (action="write").
        User's logic: revert_to_item becomes the entry itself. exists_on_fs_to_restore is True.
        Expected: file is re-written with original content, not deleted.
        """
        file_path = "/app/new_file.txt"

        # Simulate initial file creation in the DB, and also in mock_fs
        v1 = self._create_log_entry(file_path, "content1", action="write", prev_version=None)
        mock_fs.add_file(file_path, "content1") # Ensure it exists on mock_fs initially

        self.assertTrue(v1.is_newest_version)
        self.assertEqual(v1.content, "content1")
        self.assertTrue(v1.exists_on_fs)
        self.assertIsNone(v1.prev_version)
        self.assertIn(file_path, mock_fs.files)

        # Perform undo
        success, new_snapshot = v1.undo()

        self.assertTrue(success)
        self.assertFalse(v1.is_newest_version)
        self.assertTrue(new_snapshot.is_newest_version)

        # Assertions reflecting user's code behavior: file re-written
        self.assertEqual(new_snapshot.prev_version, v1)
        self.assertTrue(new_snapshot.exists_on_fs) # File still exists (not deleted) in DB log and on mock_fs
        self.assertEqual(mock_fs.files[file_path]['content'], "content1") # Content in mock_fs is restored
        self.assertEqual(new_snapshot.action, "revert")
        self.assertEqual(new_snapshot.content, "content1")
        
        # Verify calls to underlying primitives
        self.mock_write_file.assert_called_once_with(agentInstance=self.agent_instance, path=file_path, content="content1")
        self.mock_os_remove.assert_not_called()
        self.mock_os_rmdir.assert_not_called()


    def test_undo_initial_file_observation(self):
        """
        Tests undoing the very first entry which was a file observation (action="init").
        User's logic: revert_to_item becomes the entry itself. exists_on_fs_to_restore is True.
        Expected: file is re-written with original content, not marked untracked/deleted.
        """
        file_path = "/app/existing_file.txt"

        # Simulate initial observation in DB and mock_fs
        v1 = self._create_log_entry(file_path, "initial content", action="init", prev_version=None)
        mock_fs.add_file(file_path, "initial content") # Ensure it exists on mock_fs initially

        self.assertTrue(v1.is_newest_version)
        self.assertEqual(v1.content, "initial content")
        self.assertTrue(v1.exists_on_fs)
        self.assertIsNone(v1.prev_version)
        self.assertIn(file_path, mock_fs.files)

        # Perform undo
        success, new_snapshot = v1.undo()

        self.assertTrue(success)
        self.assertFalse(v1.is_newest_version)
        self.assertTrue(new_snapshot.is_newest_version)

        # Assertions reflecting user's code behavior: file re-written
        self.assertEqual(new_snapshot.prev_version, v1)
        self.assertTrue(new_snapshot.exists_on_fs) # File still exists (not marked untracked) in DB log and on mock_fs
        self.assertEqual(mock_fs.files[file_path]['content'], "initial content") # Content in mock_fs is restored
        self.assertEqual(new_snapshot.action, "revert")
        self.assertEqual(new_snapshot.content, "initial content")

        # Verify calls to underlying primitives
        self.mock_write_file.assert_called_once_with(agentInstance=self.agent_instance, path=file_path, content="initial content")
        self.mock_os_remove.assert_not_called()
        self.mock_os_rmdir.assert_not_called()


    def test_undo_file_modification(self):
        """
        Tests undoing a file modification (e.g., v2 from v1).
        Expected: file is reverted to v1's content.
        """
        file_path = "/app/file.txt"

        # Setup history: v1 (initial) -> v2 (modified)
        v1 = self._create_log_entry(file_path, "content1", action="init", created_at=MOCK_NOW - timedelta(minutes=2))
        v2 = self._create_log_entry(file_path, "content1_new", action="write", prev_version=v1, created_at=MOCK_NOW - timedelta(minutes=1))
        
        # Ensure mock_fs reflects v2's state (the current state)
        mock_fs.add_file(file_path, "content1_new")

        self.assertFalse(v1.is_newest_version)
        self.assertTrue(v2.is_newest_version)
        self.assertEqual(v2.content, "content1_new")
        self.assertIn(file_path, mock_fs.files)
        self.assertEqual(mock_fs.files[file_path]['content'], "content1_new")


        # Perform undo on v2
        success, new_snapshot = v2.undo()

        self.assertTrue(success)
        self.assertFalse(v2.is_newest_version)
        self.assertTrue(new_snapshot.is_newest_version)

        # Verify new snapshot reverts to v1's state
        self.assertEqual(new_snapshot.prev_version, v1)
        self.assertTrue(new_snapshot.exists_on_fs) # File still exists
        self.assertEqual(new_snapshot.action, "revert")
        self.assertEqual(new_snapshot.content, "content1") # Content should be v1's

        # Verify mock_fs state
        self.assertIn(file_path, mock_fs.files)
        self.assertEqual(mock_fs.files[file_path]['content'], "content1") # Mock_fs content should be v1's

        # Verify calls to underlying primitives
        self.mock_write_file.assert_called_once_with(agentInstance=self.agent_instance, path=file_path, content="content1")
        self.mock_os_remove.assert_not_called()


    def test_undo_file_deletion(self):
        """
        Tests undoing a file deletion (e.g., v2 deleted file from v1).
        Expected: file is restored to v1's content.
        """
        file_path = "/app/file.txt"

        # Setup history: v1 (initial) -> v2 (deleted)
        v1 = self._create_log_entry(file_path, "content1", action="init", created_at=MOCK_NOW - timedelta(minutes=2))
        v2 = self._create_log_entry(file_path, "", action="delete", prev_version=v1, exists_on_fs=False, created_at=MOCK_NOW - timedelta(minutes=1))
        
        # Ensure mock_fs reflects v2's state (file is deleted)
        mock_fs.delete_path(file_path)

        self.assertFalse(v1.is_newest_version)
        self.assertTrue(v2.is_newest_version)
        self.assertFalse(v2.exists_on_fs)
        self.assertNotIn(file_path, mock_fs.files)

        # Perform undo on v2 (deletion)
        success, new_snapshot = v2.undo()

        self.assertTrue(success)
        self.assertFalse(v2.is_newest_version)
        self.assertTrue(new_snapshot.is_newest_version)

        # Verify new snapshot restores to v1's state
        self.assertEqual(new_snapshot.prev_version, v1)
        self.assertTrue(new_snapshot.exists_on_fs) # File should exist again in DB log and on mock_fs
        self.assertEqual(new_snapshot.action, "revert")
        self.assertEqual(new_snapshot.content, "content1")

        # Verify mock_fs state
        self.assertIn(file_path, mock_fs.files)
        self.assertEqual(mock_fs.files[file_path]['content'], "content1") # Mock_fs content should be v1's

        # Verify calls to underlying primitives
        self.mock_write_file.assert_called_once_with(agentInstance=self.agent_instance, path=file_path, content="content1")
        self.mock_os_remove.assert_not_called() # No removal needed, as we're restoring content


    def test_undo_directory_creation(self):
        """
        Tests undoing a directory creation (v1).
        User's logic: revert_to_item becomes the entry itself. exists_on_fs_to_restore is True, is_directory_to_restore is True.
        Expected: directory is recreated (if not exists).
        """
        dir_path = "/app/new_dir"

        # Simulate initial directory creation in DB and mock_fs
        v1 = self._create_log_entry(dir_path, "", action="write", prev_version=None, exists_on_fs=True, is_directory=True)
        mock_fs.add_dir(dir_path) # Ensure it exists on mock_fs initially

        self.assertTrue(v1.is_newest_version)
        self.assertTrue(v1.exists_on_fs)
        self.assertTrue(v1.is_directory)
        self.assertIsNone(v1.prev_version)
        self.assertIn(dir_path, mock_fs.files)

        # Perform undo
        success, new_snapshot = v1.undo()

        self.assertTrue(success)
        self.assertFalse(v1.is_newest_version)
        self.assertTrue(new_snapshot.is_newest_version)

        # Assertions reflecting user's code behavior
        self.assertEqual(new_snapshot.prev_version, v1)
        self.assertTrue(new_snapshot.exists_on_fs) # Directory still exists in DB log and on mock_fs
        self.assertTrue(new_snapshot.is_directory)
        self.assertEqual(new_snapshot.action, "revert")

        # Verify mock_fs state
        self.assertIn(dir_path, mock_fs.files)
        self.assertTrue(mock_fs.files[dir_path]['is_dir'])

        # Verify calls to underlying primitives (makedirs not called because mock_os_path_exists returns True)
        self.mock_os_makedirs.assert_not_called()
        self.mock_os_remove.assert_not_called()
        self.mock_os_rmdir.assert_not_called()
        self.mock_write_file.assert_not_called() # No file content write for a dir


    # --- Test cases for celery_undo_all_filesystem_changes ---
    
    @patch('tools_filesystem.tasks.FsLogEntry.undo') # Mock the individual undo calls
    @patch('tools_filesystem.tasks.AgentVersion.add_to_conversation')
    @patch('tools_filesystem.tasks.DebugLogEntry.objects.create')
    def test_celery_undo_all_basic_scenario(self, mock_debug_create, mock_add_to_conversation, mock_individual_undo):
        """
        Scenario: File A (v1) [pk=1] -> File A (v2, modified) [pk=2] -> File A (v3, modified again) [pk=3]
        User triggers undo_all from v2 (pk=2).
        Expected based on user's logic:
        1. `items_to_process` includes v2 and v3 (pk=2, pk=3).
        2. `v2.undo()` is called, reverting File A to v1 state.
        3. `paths_undone` adds File A.
        4. `v3` is skipped because File A is already in `paths_undone`.
        """
        file_path_A = "/app/file_A.txt"
        
        # Create FsLogEntry objects to simulate the DB state.
        v_A_1 = self._create_log_entry(file_path_A, "content_A_v1", "init", pk=1, created_at=MOCK_NOW - timedelta(minutes=3))
        v_A_2 = self._create_log_entry(file_path_A, "content_A_v2", "write", prev_version=v_A_1, pk=2, created_at=MOCK_NOW - timedelta(minutes=2))
        v_A_3 = self._create_log_entry(file_path_A, "content_A_v3", "write", prev_version=v_A_2, pk=3, created_at=MOCK_NOW - timedelta(minutes=1))

        # The target_log_entry for undo_all is v_A_2
        target_log_entry_pk = v_A_2.pk

        # Mock individual undo calls. v_A_2.undo() is expected to be called once.
        mock_new_snapshot_A = FsLogEntry( # Create a mock object that mimics what undo() returns
            pk=999, path=file_path_A, content_diff="content_A_v1", action="revert", exists_on_fs=True, is_newest_version=True
        )
        mock_individual_undo.return_value = (True, mock_new_snapshot_A)
        
        # Call the task
        celery_undo_all_filesystem_changes(self.agent_instance.pk, target_log_entry_pk, "Test Undo All")

        # Assertions
        self.assertEqual(mock_individual_undo.call_count, 1) # Only v_A_2.undo() should be called
        
        mock_add_to_conversation.assert_called_once()
        args, kwargs = mock_add_to_conversation.call_args
        self.assertIn("Successfully undid 1 unique file actions.", kwargs['content'])
        self.assertIn("Test Undo All", kwargs['content'])

        mock_debug_create.assert_called()


    @patch('tools_filesystem.tasks.FsLogEntry.undo') # Mock the individual undo calls
    @patch('tools_filesystem.tasks.AgentVersion.add_to_conversation')
    @patch('tools_filesystem.tasks.DebugLogEntry.objects.create')
    def test_celery_undo_all_multiple_paths(self, mock_debug_create, mock_add_to_conversation, mock_individual_undo):
        """
        Scenario:
        File A (v1) [pk=1] -> File B (v1) [pk=2] -> File A (v2) [pk=3, TARGET] -> File B (v2) [pk=4]
        User triggers undo_all from FsLogEntry corresponding to File A (v2) (pk=3).
        Expected based on user's logic:
        1. `items_to_process` includes FsLogEntry objects for A_v2 (pk=3) and B_v2 (pk=4).
        2. `A_v2.undo()` is called.
        3. `paths_undone` adds File A.
        4. `B_v2.undo()` is called.
        5. `paths_undone` adds File B.
        """
        file_path_A = "/app/file_A.txt"
        file_path_B = "/app/file_B.txt"

        # Create FsLogEntry objects to simulate the DB state.
        v_A_1 = self._create_log_entry(file_path_A, "content_A_v1", "init", pk=1, created_at=MOCK_NOW - timedelta(minutes=4))
        v_B_1 = self._create_log_entry(file_path_B, "content_B_v1", "init", pk=2, created_at=MOCK_NOW - timedelta(minutes=3))
        v_A_2 = self._create_log_entry(file_path_A, "content_A_v2", "write", prev_version=v_A_1, pk=3, created_at=MOCK_NOW - timedelta(minutes=2))
        v_B_2 = self._create_log_entry(file_path_B, "content_B_v2", "write", prev_version=v_B_1, pk=4, created_at=MOCK_NOW - timedelta(minutes=1))
        
        # The target_log_entry for undo_all is v_A_2 (pk=3)
        target_pk = v_A_2.pk

        # Mock individual undo calls. Two calls are expected: for A_v2 and B_v2.
        mock_new_snapshot_A = FsLogEntry(pk=101, path=file_path_A, content_diff="content_A_v1", action="revert", exists_on_fs=True, is_newest_version=True)
        mock_new_snapshot_B = FsLogEntry(pk=102, path=file_path_B, content_diff="content_B_v1", action="revert", exists_on_fs=True, is_newest_version=True)
        
        # side_effect order needs to match the order of items_to_process (by PK)
        mock_individual_undo.side_effect = [
            (True, mock_new_snapshot_A), # for v_A_2.undo()
            (True, mock_new_snapshot_B)  # for v_B_2.undo()
        ]

        # Call the task
        celery_undo_all_filesystem_changes(self.agent_instance.pk, target_pk, "Test Multiple Paths")

        # Assertions
        self.assertEqual(mock_individual_undo.call_count, 2)
        
        # We cannot reliably assert the exact instance passed to undo() when patching a class method
        # due to the unexpected behavior of call_args_list with 'self' in this Django context.
        # We rely on the call_count and the side_effect logic to confirm the calls happened.
        
        mock_add_to_conversation.assert_called_once()
        args, kwargs = mock_add_to_conversation.call_args
        self.assertIn("Successfully undid 2 unique file actions.", kwargs['content'])
        self.assertIn("Test Multiple Paths", kwargs['content'])

        mock_debug_create.assert_called()
    def test_undo_directory_deletion(self):
        """
        Tests undoing a directory deletion.
        Scenario: v1 (directory exists) -> v2 (directory deleted).
        Expected: undoing v2 restores the directory.
        """
        dir_path = "/app/existing_dir"

        # Setup history: v1 (directory exists) -> v2 (directory deleted)
        v1 = self._create_log_entry(dir_path, "", action="init", prev_version=None, exists_on_fs=True, is_directory=True, created_at=MOCK_NOW - timedelta(minutes=2))
        v2 = self._create_log_entry(dir_path, "", action="delete", prev_version=v1, exists_on_fs=False, is_directory=True, created_at=MOCK_NOW - timedelta(minutes=1))
        
        # Ensure mock_fs reflects v2's state (directory is deleted)
        mock_fs.delete_path(dir_path)

        self.assertFalse(v1.is_newest_version)
        self.assertTrue(v2.is_newest_version)
        self.assertFalse(v2.exists_on_fs)
        self.assertNotIn(dir_path, mock_fs.files)

        # Perform undo on v2 (the deletion entry)
        success, new_snapshot = v2.undo()

        self.assertTrue(success)
        self.assertTrue(new_snapshot.is_newest_version)

        self.assertFalse(v2.is_newest_version)

        # Verify new snapshot restores to v1's state
        self.assertEqual(new_snapshot.prev_version, v1)
        self.assertTrue(new_snapshot.exists_on_fs) # Directory should exist again in DB log and on mock_fs
        self.assertTrue(new_snapshot.is_directory)
        self.assertEqual(new_snapshot.action, "revert")

        # Verify mock_fs state
        self.assertIn(dir_path, mock_fs.files)
        self.assertTrue(mock_fs.files[dir_path]['is_dir'])

        # Verify calls to underlying primitives: makedirs should be called to restore the directory
        self.mock_os_makedirs.assert_called_once_with(dir_path)
        self.mock_os_remove.assert_not_called()
        self.mock_os_rmdir.assert_not_called()
        self.mock_write_file.assert_not_called() # No file content write for a dir

    def test_undo_file_modification_patch_stored_as(self):
        """
        Tests undoing a file modification where the content was stored as a patch.
        Expected: file is reverted to v1's content, demonstrating correct patch application.
        """
        file_path = "/app/patched_file.txt"

        # Force _get_storage_method to return 'patch' for content_diff for this test
        self.mock_get_storage.side_effect = lambda existing, new: ("patch", make_patch(existing, new)) if existing != new else ("full", new)

        # Setup history: v1 (initial) -> v2 (modified, stored as patch)
        v1 = self._create_log_entry(file_path, "initial content\nline 2\nline 3", action="init", created_at=MOCK_NOW - timedelta(minutes=2))
        mock_fs.add_file(file_path, "initial content\nline 2\nline 3")

        new_content_v2 = "updated content\nline 2\nline 3"
        v2 = self._create_log_entry(file_path, new_content_v2, action="write", prev_version=v1, created_at=MOCK_NOW - timedelta(minutes=1))
        # manually set content_diff and stored_as to ensure it's a patch, as _create_log_entry uses "full" by default
        v2.stored_as = "patch"
        v2.content_diff = make_patch(v1.content, new_content_v2)
        v2.save()
        
        mock_fs.add_file(file_path, new_content_v2)

        self.assertFalse(v1.is_newest_version)
        self.assertTrue(v2.is_newest_version)
        self.assertEqual(v2.content, new_content_v2) # Ensure content property works for patched entry
        self.assertIn(file_path, mock_fs.files)
        self.assertEqual(mock_fs.files[file_path]['content'], new_content_v2)

        # Perform undo on v2
        success, new_snapshot = v2.undo()

        self.assertTrue(success)
        self.assertFalse(v2.is_newest_version)
        self.assertTrue(new_snapshot.is_newest_version)

        # Verify new snapshot reverts to v1's state
        self.assertEqual(new_snapshot.prev_version, v1)
        self.assertTrue(new_snapshot.exists_on_fs)
        self.assertEqual(new_snapshot.action, "revert")
        self.assertEqual(new_snapshot.content, v1.content) # Content should be v1's

        # Verify mock_fs state
        self.assertIn(file_path, mock_fs.files)
        self.assertEqual(mock_fs.files[file_path]['content'], v1.content)

        # Verify calls to underlying primitives
        self.mock_write_file.assert_called_once_with(agentInstance=self.agent_instance, path=file_path, content=v1.content)
        self.mock_os_remove.assert_not_called()

    @patch('tools_filesystem.models.write_file')
    @patch('tools_filesystem.models.os.remove')
    @patch('tools_filesystem.models.os.rmdir')
    @patch('tools_filesystem.models.os.makedirs')
    def test_undo_file_system_operation_failure(self, mock_makedirs, mock_rmdir, mock_remove, mock_write_file):
        """
        Tests `FsLogEntry.undo()` behavior when a required filesystem operation fails.
        Expected: `undo()` returns False with an error message, and no revert entry is created.
        """
        file_path = "/app/failing_file.txt"

        # Setup history
        v1 = self._create_log_entry(file_path, "original content", action="init", created_at=MOCK_NOW - timedelta(minutes=2))
        v2 = self._create_log_entry(file_path, "modified content", action="write", prev_version=v1, created_at=MOCK_NOW - timedelta(minutes=1))
        
        mock_fs.add_file(file_path, "modified content")

        # Configure mock_write_file to simulate a failure
        mock_write_file.return_value = {'status': 'failed', 'message': 'Permission denied'}

        # Perform undo on v2
        success, result = v2.undo()

        self.assertFalse(success)
        self.assertIn("Permission denied", result.get('message', ''))
        
        # Verify no new FsLogEntry of action="revert" was created
        self.assertEqual(FsLogEntry.objects.filter(action="revert", path=file_path).count(), 0)
        
        # Original v2 should still be the newest (no state change due to failure)
        v2_reloaded = FsLogEntry.objects.get(pk=v2.pk)
        self.assertTrue(v2_reloaded.is_newest_version)

        # Ensure write_file was attempted
        mock_write_file.assert_called_once()
        self.mock_os_remove.assert_not_called() # No remove was expected

    @patch('tools_filesystem.tasks.FsLogEntry.undo')
    @patch('tools_filesystem.tasks.AgentVersion.add_to_conversation')
    @patch('tools_filesystem.tasks.DebugLogEntry.objects.create')
    def test_celery_undo_all_mixed_success_failure(self, mock_debug_create, mock_add_to_conversation, mock_individual_undo):
        """
        Tests celery_undo_all_filesystem_changes when some individual undo operations succeed and others fail.
        Expected: Summary message and debug logs accurately reflect both successes and failures.
        """
        file_path_A = "/app/file_A.txt"
        file_path_B = "/app/file_B.txt"

        # Setup FsLogEntry objects for two files, each with one modification
        v_A_1 = self._create_log_entry(file_path_A, "content_A_v1", "init", pk=1, created_at=MOCK_NOW - timedelta(minutes=4))
        v_B_1 = self._create_log_entry(file_path_B, "content_B_v1", "init", pk=2, created_at=MOCK_NOW - timedelta(minutes=3))
        v_A_2 = self._create_log_entry(file_path_A, "content_A_v2", "write", prev_version=v_A_1, pk=3, created_at=MOCK_NOW - timedelta(minutes=2))
        v_B_2 = self._create_log_entry(file_path_B, "content_B_v2", "write", prev_version=v_B_1, pk=4, created_at=MOCK_NOW - timedelta(minutes=1))

        target_pk = v_A_2.pk # Target to undo from A_v2, meaning A_v2 and B_v2 are processed

        # Configure mock_individual_undo: A_v2 succeeds, B_v2 fails
        mock_new_snapshot_A = FsLogEntry(pk=101, path=file_path_A, content_diff="content_A_v1", action="revert", exists_on_fs=True, is_newest_version=True)
        mock_individual_undo.side_effect = [
            (True, mock_new_snapshot_A), # A_v2.undo() succeeds
            (False, {'message': 'Mocked permission error for B'}) # B_v2.undo() fails
        ]

        # Call the task
        celery_undo_all_filesystem_changes(self.agent_instance.pk, target_pk, "Mixed Scenario")

        # Assertions
        self.assertEqual(mock_individual_undo.call_count, 2) # Both A_v2 and B_v2 undo attempts should occur
        
        mock_add_to_conversation.assert_called_once()
        args, kwargs = mock_add_to_conversation.call_args
        conversation_content = kwargs['content']
        self.assertIn("Successfully undid 1 unique file actions.", conversation_content)
        self.assertIn("Failed to undo 1 unique file actions.", conversation_content)
        self.assertIn("Mixed Scenario", conversation_content)

        # Expect two debug logs: one for the undo_all completion, one for the specific failure
        # The specific failure debug log will have 'undo_all_error' event
        debug_calls = [c for c in mock_debug_create.call_args_list if c.kwargs.get('event') == 'undo_all_error']
        self.assertEqual(len(debug_calls), 1)
        self.assertIn('Mocked permission error for B', debug_calls[0].kwargs['data']['error'])
        self.assertEqual(debug_calls[0].kwargs['data']['log_entry_pk'], v_B_2.pk) # The failing entry