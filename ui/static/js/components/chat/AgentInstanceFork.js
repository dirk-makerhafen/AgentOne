function renderAgentInstanceForkMessage(payload) {
    const agentInstanceForkTemplate = getTemplate('AgentInstanceForkTemplate');
    const targetInstanceId = payload.target_instance_id;

    const isParent = targetInstanceId === payload.parent_instance_id;
    const isChild = targetInstanceId === payload.child_instance_id;
    
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = agentInstanceForkTemplate({
        id: payload.id,
        targetInstanceId: targetInstanceId,
        created_at: payload.created_at,
        formattedTimestamp: new Date(payload.created_at).toLocaleTimeString(),
        parent_instance_id: payload.parent_instance_id,
        child_instance_id: payload.child_instance_id,
        child_instance_name: payload.child_instance_name,
        isParent: isParent,
        isChild: isChild
    }).trim();
    const newElement = tempDiv.firstChild;
    
    const existingElement = document.getElementById(newElement.id);

    if (existingElement) {
        newElement.classList.add('no-animate'); 
        existingElement.replaceWith(newElement);
    } else {
        addToChatArea(newElement, targetInstanceId);
    }
};