// This file manages the rendering and interactions for the Filesystem sidebar header.

function renderSidebarFilesystemHeader(instancePayload) {
    const headerContainer = document.getElementById(`sidebar-filesystem-header-container_${instancePayload.id}`);
    if (!headerContainer) return;

    const instanceId = instancePayload.id;

    // If the header hasn't been rendered yet, render the full template.
    if (headerContainer.children.length === 0) {
        const sidebarFilesystemHeaderTemplate = getTemplate('SidebarFilesystemHeaderTemplate');
        headerContainer.innerHTML = sidebarFilesystemHeaderTemplate(instancePayload);
    } else {
        // If the header already exists, surgically update the specific elements that
        // are driven by the AgentInstance payload. This is non-destructive.
        
        // Update Working Directory
        const workingDirDisplay = document.getElementById(`sidebar-workingdir-path_${instanceId}`);
        const workingDirInput = document.getElementById(`sidebar-workingdir-input_${instanceId}`);
        const workingDir = instancePayload.workingdir || 'Not Set';
        const workingDirTitle = instancePayload.workingdir || 'Working directory is not set';

        if (workingDirDisplay) {
            workingDirDisplay.textContent = workingDir;
            workingDirDisplay.title = workingDirTitle;
        }
        if (workingDirInput) {
            workingDirInput.value = instancePayload.workingdir || '';
        }

        // Update Write Permission Toggle
        const writePermissionToggle = document.getElementById(`fs-write-permission-toggle_${instanceId}`);
        if (writePermissionToggle) {
            const isAllowed = instancePayload.workingdir_write_allowed;
            const nextValue = !isAllowed; // The value to set on the next click

            writePermissionToggle.classList.toggle('locked', !isAllowed);
            writePermissionToggle.classList.toggle('unlocked', isAllowed);
            writePermissionToggle.title = `WD Write: ${isAllowed ? 'ON' : 'OFF'}`;
            
            // Re-assign the onclick to pass the new value, making it a true toggle
            writePermissionToggle.onclick = (event) => {
                event.stopPropagation();
                saveSidebarFsPermission(instanceId, 'workingdir_write_allowed', nextValue);
            };
        }

        // Update Access Rules Textarea
        const accessRulesTextarea = document.getElementById(`fs-access-rules_${instanceId}`);
        if (accessRulesTextarea) {
            accessRulesTextarea.value = instancePayload.access_rules || '';
        }
    }
}

function showSidebarWorkingdirEdit(instanceId) {
    document.getElementById(`sidebar-workingdir-display_${instanceId}`).style.display = 'none';
    document.getElementById(`sidebar-workingdir-edit_${instanceId}`).style.display = 'flex';
    document.getElementById(`sidebar-workingdir-input_${instanceId}`).focus();
}

function cancelSidebarWorkingdirEdit(instanceId) {
    const display = document.getElementById(`sidebar-workingdir-display_${instanceId}`);
    const edit = document.getElementById(`sidebar-workingdir-edit_${instanceId}`);
    if(display) display.style.display = 'flex';
    if(edit) edit.style.display = 'none';
}

function saveSidebarWorkingdir(instanceId) {
    const input = document.getElementById(`sidebar-workingdir-input_${instanceId}`);
    agentInstanceApi.update(instanceId, { "workingdir": input.value });
    cancelSidebarWorkingdirEdit(instanceId);
}

function handleSidebarWorkingdirKeydown(event, instanceId) {
    if (event.key === 'Enter') saveSidebarWorkingdir(instanceId);
    else if (event.key === 'Escape') cancelSidebarWorkingdirEdit(instanceId);
}
