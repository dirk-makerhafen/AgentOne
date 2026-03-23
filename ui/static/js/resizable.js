const gutterSizePx = 5; 
const panelLastSizes = new WeakMap(); 
let allSplitInstances = new Map(); 
function initializeSplitForContainer(containerElement) {
    if (!containerElement.id) {
        containerElement.id = `split-container-${Math.random().toString(36).substr(2, 9)}`;
    }
    //console.log(`[Split.js] --- Initializing split for container: ${containerElement.id || containerElement.tagName}, class: ${containerElement.classList}, orientation: ${containerElement.getAttribute('data-orientation')}. ---`);
    //console.log(`[Split.js] Container dimensions - offsetWidth: ${containerElement.offsetWidth}, offsetHeight: ${containerElement.offsetHeight}`);

    // Destroy existing Split.js instance for this container if it exists
    if (allSplitInstances.has(containerElement.id)) {
        allSplitInstances.get(containerElement.id).destroy();
        allSplitInstances.delete(containerElement.id);
        // Remove associated gutters for this container's direct children
        Array.from(containerElement.children).filter(el => el.classList.contains('gutter')).forEach(gutter => gutter.remove());
    }

    const orientation = containerElement.getAttribute('data-orientation') || 'horizontal'; // Use getAttribute
    const panelElements = Array.from(containerElement.children).filter(el => el.classList.contains('resizable-panel'));
    //console.log(`[Split.js] Identified ${panelElements.length} resizable panels for container ${containerElement.id || containerElement.tagName}:`, panelElements);

    if (panelElements.length > 1) { // Only create split if there's more than one panel
        function getSizePc(panelElements, keyPx, keyPc, minMaxF, defaultValue, containerSize) {
            return panelElements.map(p => {
                let px = Number(p.getAttribute(keyPx) ?? NaN); 
                const pc = Number(p.getAttribute(keyPc) ?? NaN);
                if (!isNaN(px)) { px = 100 / containerSize * px; } // Convert px to pc
                const values = [px, pc].filter(v => !isNaN(v));
                return values.length ? minMaxF(...values) : defaultValue;
            });
        }

        function updateGutters(panelElements){
            panelElements.handles.forEach((handle) => { handle.collapsed = false;}); 
            panelElements.forEach((p, idx) => { 
                if(idx < panelElements.handles.length){
                    const currentContainerSize = panelElements.orientation === 'horizontal' ? panelElements[idx].offsetWidth : panelElements[idx].offsetHeight;
                    const nextContainerSize = panelElements.orientation === 'horizontal' ? panelElements[idx+1]?.offsetWidth : panelElements[idx+1]?.offsetHeight;
                    if(currentContainerSize <= gutterSizePx || nextContainerSize <= gutterSizePx){ panelElements.handles[idx].collapsed = true}
                }
            });
            panelElements.handles.forEach((handle) => { 
                if(handle.collapsed == true){ handle.classList.add("gutter-handle-collapsed");
                }else{ handle.classList.remove("gutter-handle-collapsed")}
            });
        }

        const totalContainerDim = orientation === 'horizontal' ? containerElement.offsetWidth : containerElement.offsetHeight;
        panelElements.container = containerElement;
        panelElements.orientation = orientation;
        
        let defaults = getSizePc(panelElements, "data-size-px", "data-size-pc", Math.min, Infinity, totalContainerDim); 
        let defaultSizesPc = panelElements.map((p, index) => { return panelLastSizes.get(p) || defaults[index]; });
        
        let s = defaultSizesPc.filter(v => v !== Infinity).reduce((a, b) => a + b, 0);
        let rest = s < 100 ? (100 - s) / defaultSizesPc.filter(v => v === Infinity).length : 0;
        defaultSizesPc = defaultSizesPc.map(m => { return m === Infinity ? rest : m; });

        const instance = Split(panelElements, {
            direction: orientation,
            sizes: defaultSizesPc,
            minSize: defaultSizesPc.map(v => 0),
            expandToMin: true,
            gutterSize: gutterSizePx,
            cursor: orientation === 'horizontal' ? 'ew-resize' : 'ns-resize',
            elementStyle: (dimension, size, gutterSize) => ({'flex-basis': `calc(${size}% - ${gutterSize}px)`}),
            gutterStyle: (dimension, gutterSize) => ({'flex-basis': `${gutterSize}px`}),
            onDragEnd: function(sizes) {
                panelElements.forEach((p, idx) => { panelLastSizes.set(p, sizes[idx]); });
                updateGutters(panelElements);
            },
            gutter: (index, direction) => {
                const gutter = document.createElement('div');
                gutter.className = `gutter gutter-${direction}`;
                const gutterHandle = document.createElement('div');
                gutterHandle.classList.add(`gutter-handle`);
                gutterHandle.classList.add(`gutter-handle-${direction}`);
                gutter.appendChild(gutterHandle);
                return gutter;
            },
        });
        allSplitInstances.set(containerElement.id, instance); // Store by unique ID
        panelElements.handles = Array.from(containerElement.children).filter(el => el.classList.contains("gutter")).flatMap(gutter => Array.from(gutter.children).filter(child => child.classList.contains("gutter-handle")));
        updateGutters(panelElements); 

        // After initializing this container's splits, recursively initialize nested splits
        panelElements.forEach(panel => {
            if (panel.classList.contains('resizable-container')) {
                //console.log(`[Split.js] Recursively initializing nested container: ${panel.id || panel.tagName}`);
                initializeSplitForContainer(panel); // Recursive call
            }
        });
    } else {
        //console.log(`[Split.js] Skipping split initialization for container ${containerElement.id || containerElement.tagName}: Less than 2 resizable panels, or no panels found.`);
    }
}

function reinitializeAllSplits() {
    document.querySelectorAll('.resizable-container').forEach(container => {
        initializeSplitForContainer(container);
    });
}
