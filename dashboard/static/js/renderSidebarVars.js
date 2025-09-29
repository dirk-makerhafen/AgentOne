const sidebarVarsTemplate = Handlebars.compile(`
<div class="sidebar-vars-container">
    {{#if (isEmpty vars)}}
        <div class="sidebar-vars-empty">No variables set.</div>
    {{else}}
        <ul class="sidebar-vars-list">
            {{#each vars}}
            <li class="sidebar-var-item" data-var-key="{{@key}}">
                <div class="sidebar-var-key">{{@key}}</div>
                <div class="sidebar-var-value">
                    <pre>{{json this}}</pre>
                </div>
            </li>
            {{/each}}
        </ul>
    {{/if}}
</div>`);


function renderSidebarVars(varsList, instancePk) {
    const container = document.getElementById(`sidebar-tab-vars_${instancePk}`);
    if (!container) {
        console.error(`VARS container for instance ${instancePk} not found.`);
        return;
    }
    let instanceState = getInstanceVarsState(instancePk);
    allAgentVarsStates[instancePk] = {};     
    if (Array.isArray(varsList)) {
        varsList.forEach(varItem => {
            allAgentVarsStates[instancePk][varItem.key] = varItem.value;
        });
    }
    container.innerHTML = sidebarVarsTemplate({ vars: allAgentVarsStates[instancePk] });
}

function updateSidebarVar(payload, instancePk) {
    const container = document.getElementById(`sidebar-tab-vars_${instancePk}`);
    if (!container) {
        console.error(`VARS container for instance ${instancePk} not found during update.`);
        return;
    }
    let instanceState = getInstanceVarsState(instancePk);
    instanceState[payload.key] = payload.value;
    container.innerHTML = sidebarVarsTemplate({ vars: instanceState });
}


// Client-side cache for VARS, now instance-specific
let allAgentVarsStates = {};

function getInstanceVarsState(instancePk) {
    if (!allAgentVarsStates[instancePk]) {
        allAgentVarsStates[instancePk] = {};
    }
    return allAgentVarsStates[instancePk];
}

