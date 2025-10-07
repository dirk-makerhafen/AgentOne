window.splitPanelCount = 0; // Global counter for unique split panel IDs

function addSplitPanel(orientation) {
    const mainSplitViewContainer = document.getElementById('mainSplitViewContainer');
    if (!mainSplitViewContainer) {
        addToConsoleArea('Error: mainSplitViewContainer not found.', 'error');
        return;
    }

    const currentPanels = Array.from(mainSplitViewContainer.children).filter(child => child.classList.contains('resizable-panel'));
    const isFirstSplit = currentPanels.length === 1 && currentPanels[0].id === 'mainTabPanel';

    if (isFirstSplit) {
        const mainTabPanel = document.getElementById('mainTabPanel');
        if (mainTabPanel) {
            mainTabPanel.setAttribute('data-size-pc', '100');
        }
    }

    window.splitPanelCount++;
    const newPanelId = `mainTabPanel_split_${window.splitPanelCount}`;
    const newTabBarId = `mainTabBar_split_${window.splitPanelCount}`;
    const newPlaceholderTabContentId = `tabContent_split_${window.splitPanelCount}_placeholder`;

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = `
        <div class="resizable-panel flex-column splitpane" id="${newPanelId}" data-size-pc=100 style="max-width: 0; opacity: 0; flex-basis: 0;">
            <div class="tab-controls-area">
                <div class="tab-bar" id="${newTabBarId}" ondragover="allowDrop(event)" ondrop="dropTab(event, '${newTabBarId}')" ondragenter="event.target.classList.add('drag-over')" ondragleave="event.target.classList.remove('drag-over')">
                    <div class="split-controls-container" style="display: flex; margin-left: auto; gap: 5px; padding-top: 2px;">
                    </div>
                </div>
            </div>
            <div id="${newPlaceholderTabContentId}" class="resizable-container tab-content active default-split-content" data-orientation="vertical" ondragover="allowDrop(event)" ondrop="dropOnPlaceholder(event, '${newPanelId}')" ondragenter="event.target.classList.add('drag-over')" ondragleave="event.target.classList.remove('drag-over')">
                <p style="text-align: center; padding: 20px;">New split panel. Drag tabs here or add new content.</p>
            </div>
        </div>
    `;
    const newSplitPanel = tempDiv.firstElementChild;
    mainSplitViewContainer.insertAdjacentElement('beforeend', newSplitPanel);
    
    // Trigger CSS transition after element is in DOM
    requestAnimationFrame(() => {
        newSplitPanel.style.maxWidth = `calc(${newSplitPanel.getAttribute('data-size-pc')}% - ${gutterSizePx}px)`;
        newSplitPanel.style.opacity = '1';
        newSplitPanel.style.flexBasis = `calc(${newSplitPanel.getAttribute('data-size-pc')}% - ${gutterSizePx}px)`;
    });


    addToConsoleArea(`Added new split panel: ${newPanelId}`, 'info');

    if (typeof reinitializeAllSplits === 'function') {
        reinitializeAllSplits();
    } else {
        console.error("reinitializeAllSplits function not found. Split.js setup failed.");
    }
    updateSplitControlButtons();
}

function removeSplitPanel(panelId) {
    if (panelId === 'mainTabPanel') {
        addToConsoleArea(`Error: Attempted to remove mainTabPanel, which is not allowed.`, 'error');
        return;
    }

    const panelToRemove = document.getElementById(panelId);
    if (!panelToRemove) {
        addToConsoleArea(`Error: Split panel with ID ${panelId} not found.`, 'error');
        return;
    }

    const tabsToMove = [];
    panelToRemove.querySelectorAll('.tab-bar .tab-button').forEach(button => {
        const tabContentId = button.dataset.tabContentId;
        const tabContent = document.getElementById(tabContentId);
        if (tabContent) {
            tabsToMove.push({ button: button, content: tabContent });
        }
    });

    const gutterAfterPanel = panelToRemove.nextElementSibling; // Get the gutter element after this panel if it exists

    // Start fade-out and shrink animation
    panelToRemove.style.maxWidth = '0';
    panelToRemove.style.opacity = '0';
    panelToRemove.style.flexBasis = '0';
    if (gutterAfterPanel && gutterAfterPanel.classList.contains('gutter')) {
        gutterAfterPanel.style.maxWidth = '0';
        gutterAfterPanel.style.opacity = '0';
        gutterAfterPanel.style.flexBasis = '0';
    }

    // Remove elements after transition ends
    const handleTransitionEnd = (event) => {
        if (event.propertyName === 'max-width' || event.propertyName === 'flex-basis') {
            panelToRemove.removeEventListener('transitionend', handleTransitionEnd);
            if (tabsToMove.length > 0) {
                const allPanelsAfterRemoval = Array.from(document.querySelectorAll('#mainSplitViewContainer > .resizable-panel.flex-column'));
                let targetParentPanel = allPanelsAfterRemoval.find(panel => panel.id === 'mainTabPanel') || allPanelsAfterRemoval[0];

                if (targetParentPanel) {
                    const targetTabBar = targetParentPanel.querySelector('.tab-bar');
                    const targetTabControlsArea = targetParentPanel.querySelector('.tab-controls-area');
                    const splitControlsContainer = targetTabBar ? targetTabBar.querySelector('.split-controls-container') : null;

                    if (targetTabBar && targetTabControlsArea) {
                        targetParentPanel.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
                        targetParentPanel.querySelectorAll('.tab-content').forEach(content => {
                            content.classList.remove('active');
                            content.style.display = 'none';
                        });
                        
                        const defaultContentInTarget = targetParentPanel.querySelector('.default-split-content');
                        if (defaultContentInTarget) defaultContentInTarget.remove();

                        tabsToMove.forEach((tab, index) => {
                            if (splitControlsContainer) targetTabBar.insertBefore(tab.button, splitControlsContainer);
                            else targetTabBar.appendChild(tab.button);
                            
                            targetParentPanel.insertBefore(tab.content, targetTabControlsArea.nextSibling);
                            
                            const newOnClick = `openMainTab(event, '${tab.content.id}', '${targetParentPanel.id}')`;
                            tab.button.setAttribute('onclick', newOnClick);
                            
                            tab.button.style.display = 'inline-block';
                        });

                        if (tabsToMove.length > 0) {
                            openMainTab(null, tabsToMove[0].content.id, targetParentPanel.id);
                        }
                    }
                }
            }

            const remainingPanels = Array.from(document.querySelectorAll('#mainSplitViewContainer > .resizable-panel.flex-column'));
            if (remainingPanels.length === 1 && remainingPanels[0].id === 'mainTabPanel') {
                remainingPanels[0].setAttribute('data-size-pc', '100');
            }
            panelToRemove.remove();
            if (typeof reinitializeAllSplits === 'function') {
                reinitializeAllSplits();
            }
            updateSplitControlButtons();
        }
    };

    panelToRemove.addEventListener('transitionend', handleTransitionEnd);
}

function updateSplitControlButtons() {
    const mainSplitViewContainer = document.getElementById('mainSplitViewContainer');
    if (!mainSplitViewContainer) return;

    const allPanels = Array.from(mainSplitViewContainer.children).filter(child =>
        child.classList.contains('resizable-panel') && child.classList.contains('flex-column')
    );

    if (allPanels.length === 0) return;

    allPanels.forEach((panel, index) => {
        const splitControlsContainer = panel.querySelector('.split-controls-container');
        if (!splitControlsContainer) return;

        splitControlsContainer.innerHTML = '';

        if (index === allPanels.length - 1) {
            const addSplitBtn = document.createElement('i');
            addSplitBtn.className = 'fa fa-columns add-split-button';
            addSplitBtn.style.color = 'black';
            addSplitBtn.title = 'Split Right';
            addSplitBtn.onclick = (event) => {
                event.stopPropagation();
                addSplitPanel('horizontal');
            };
            splitControlsContainer.appendChild(addSplitBtn);
        }

        if (panel.id !== 'mainTabPanel' && allPanels.length > 1) {
            const removeSplitBtn = document.createElement('i');
            removeSplitBtn.className = 'fa fa-times remove-split-button';
            removeSplitBtn.style.color = 'black';
            removeSplitBtn.title = 'Remove Split';
            removeSplitBtn.onclick = (event) => {
                event.stopPropagation();
                removeSplitPanel(panel.id);
            };
            splitControlsContainer.appendChild(removeSplitBtn);
        }
    });
}