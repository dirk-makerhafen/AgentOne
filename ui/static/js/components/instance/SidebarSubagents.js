// This file manages the rendering of the Sub-Agents tab in the right sidebar of an agent instance.

function renderSidebarSubagents(subagentLinks, instancePk) {
        const tabContent = document.getElementById(`sidebar-tab-subagents_${instancePk}`); // Correctly target the tab content element from TabInstance.html
    if (!tabContent) return;

    const template = getTemplate('SidebarSubagentsTemplate');
    const context = {
        instance_pk: instancePk,
        subagents: subagentLinks
    };
    tabContent.innerHTML = template(context);
}
