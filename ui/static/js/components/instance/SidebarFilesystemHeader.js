// This file manages the rendering and interactions for the Filesystem sidebar header.

function renderSidebarFilesystemHeader(instancePayload) {
    const sidebarFilesystemHeaderTemplate = getTemplate('SidebarFilesystemHeaderTemplate');
    const headerContainer = document.getElementById(`sidebar-filesystem-header-container_${instancePayload.id}`);
    if (headerContainer) {
        headerContainer.innerHTML = sidebarFilesystemHeaderTemplate(instancePayload);
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
