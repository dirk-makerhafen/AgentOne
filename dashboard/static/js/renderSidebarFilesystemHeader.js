const sidebarFilesystemHeaderTemplate = Handlebars.compile(`
<div class="sidebar-fs-header-new">
    <div id="sidebar-workingdir-display_{{id}}" class="fs-header-item">
        <span id="sidebar-workingdir-text_{{id}}" class="editable-path" onclick="showSidebarWorkingdirEdit('{{id}}')" title="{{workingdir}}">{{workingdir}}</span>
    </div>
    <div id="sidebar-workingdir-edit_{{id}}" class="fs-header-item" style="display: none; width: -webkit-fill-available;">
        <input type="text" id="sidebar-workingdir-input_{{id}}" value="{{workingdir}}" onkeydown="handleSidebarWorkingdirKeydown(event, '{{id}}')" />
        <i class="fa fa-check" onclick="saveSidebarWorkingdir('{{id}}')"></i>
        <i class="fa fa-times" onclick="cancelSidebarWorkingdirEdit('{{id}}')"></i>
    </div>
    <div class="fs-header-item fs-token-count"><span id="total-fs-tokens_{{id}}">0</span></div>
    <div class="sidebar-fs-header-controls">
        <i id="fs-view-toggle_{{id}}" class="fa fa-eye fs-view-toggle" title="Show All Items"></i>
        <i id="fs-write-permission-toggle_{{id}}" 
        class="fa {{#if workingdir_write_allowed}}fa-pencil unlocked{{else}}fa-pencil locked{{/if}} fs-permission-toggle" 
        title="{{#if workingdir_write_allowed}}WD Write: ON{{else}}WD Write: OFF{{/if}}"
        onclick="saveSidebarFsPermission('{{id}}', 'workingdir_write_allowed', {{#if workingdir_write_allowed}}false{{else}}true{{/if}})"></i>
    </div>
</div>`);


function renderSidebarFilesystemHeader(instancePayload) {
    const instancePk = instancePayload.id; // Extract instancePk from payload
    const container = document.getElementById(`sidebar-filesystem-header-container_${instancePk}`);
    if (container) {
        container.innerHTML = sidebarFilesystemHeaderTemplate(instancePayload);
        
        const rulesTextarea = document.getElementById(`fs-access-rules_${instancePk}`);
        if (rulesTextarea) {
            rulesTextarea.value = instancePayload.access_rules || '';
        }
        updateTotalTokensDisplay(instancePk);

        const fsViewToggle = container.querySelector(`#fs-view-toggle_${instancePk}`);
        const fsListContainer = document.getElementById(`sidebar-filesystem-list-${instancePk}`);

        if (fsViewToggle && fsListContainer) {
            if (fsListContainer.classList.contains('show-all-fs-items')) {
                fsViewToggle.title = "Show Only Loaded Items";
                fsViewToggle.classList.remove('fa-eye');
                fsViewToggle.classList.add('fa-eye-slash');
            } else {
                fsViewToggle.title = "Show All Items";
                fsViewToggle.classList.remove('fa-eye-slash');
                fsViewToggle.classList.add('fa-eye');
            }

            fsViewToggle.onclick = function(event) {
                event.preventDefault();
                fsListContainer.classList.toggle('show-all-fs-items');
                
                if (fsListContainer.classList.contains('show-all-fs-items')) {
                    fsViewToggle.title = "Show Only Loaded Items";
                    fsViewToggle.classList.remove('fa-eye');
                    fsViewToggle.classList.add('fa-eye-slash');
                } else {
                    fsViewToggle.title = "Show All Items";
                    fsViewToggle.classList.remove('fa-eye-slash');
                    fsViewToggle.classList.add('fa-eye');
                }
            };
        }
    }
}

function showSidebarWorkingdirEdit(instanceId) {
    document.getElementById(`sidebar-workingdir-display_${instanceId}`).style.display = 'none';
    const editContainer = document.getElementById(`sidebar-workingdir-edit_${instanceId}`);
    editContainer.style.display = 'flex';
    const input = document.getElementById(`sidebar-workingdir-input_${instanceId}`);
    input.value = document.getElementById(`sidebar-workingdir-text_${instanceId}`).textContent;
    input.focus();
    input.select();
}

function cancelSidebarWorkingdirEdit(instanceId) {
    document.getElementById(`sidebar-workingdir-edit_${instanceId}`).style.display = 'none';
    document.getElementById(`sidebar-workingdir-display_${instanceId}`).style.display = 'flex';
}

function saveSidebarWorkingdir(instanceId) {
    const input = document.getElementById(`sidebar-workingdir-input_${instanceId}`);
    const newWorkingdir = input.value.trim();

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'update_instance_data',
            payload: {
                instance_pk: instanceId,
                data: {
                    workingdir: newWorkingdir
                }
            }
        }));
    }
    cancelSidebarWorkingdirEdit(instanceId); // Hide input, UI will update via broadcast
}

function handleSidebarWorkingdirKeydown(event, instanceId) {
    if (event.key === 'Enter') {
        saveSidebarWorkingdir(instanceId);
    } else if (event.key === 'Escape') {
        cancelSidebarWorkingdirEdit(instanceId);
    }
}




