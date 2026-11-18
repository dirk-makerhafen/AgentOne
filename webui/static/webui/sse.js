/*
Server Sent Events Extension
============================
Vendored from htmx-ext-sse 2.2.4 (https://github.com/bigskysoftware/htmx-extensions)
with local fixes for listener lifecycle in this app's per-component SSE usage:
- dedupe listener registration per element/event (idempotent registerSSE)
- remove element listeners on cleanup instead of leaking them on the shared source
- reuse/close existing EventSource correctly on reprocess/reconnect
- rebind registered listeners to a new EventSource after reconnect
*/

(function() {
  /** @type {import("../htmx").HtmxInternalApi} */
  var api

  htmx.defineExtension('sse', {

    /**
     * Init saves the provided reference to the internal HTMX API.
     *
     * @param {import("../htmx").HtmxInternalApi} api
     * @returns void
     */
    init: function(apiRef) {
      // store a reference to the internal API.
      api = apiRef

      // set a function in the public API for creating new EventSource objects
      if (htmx.createEventSource == undefined) {
        htmx.createEventSource = createEventSource
      }
    },

    getSelectors: function() {
      return ['[sse-connect]', '[data-sse-connect]', '[sse-swap]', '[data-sse-swap]']
    },

    /**
     * onEvent handles all events passed to this extension.
     *
     * @param {string} name
     * @param {Event} evt
     * @returns void
     */
    onEvent: function(name, evt) {
      var parent = evt.target || evt.detail.elt
      switch (name) {
        case 'htmx:beforeCleanupElement':
          cleanupElement(parent)
          return

        // Try to create EventSources when elements are processed
        case 'htmx:afterProcessNode':
          ensureEventSourceOnElement(parent)
      }
    }
  })

  /// ////////////////////////////////////////////
  // HELPER FUNCTIONS
  /// ////////////////////////////////////////////

  /**
   * createEventSource is the default method for creating new EventSource objects.
   * it is hoisted into htmx.config.createEventSource to be overridden by the user, if needed.
   *
   * @param {string} url
   * @returns EventSource
   */
  function createEventSource(url) {
    return new EventSource(url, { withCredentials: true })
  }

  function getSourceData(sourceElement) {
    var data = api.getInternalData(sourceElement)
    if (!data.sseBoundElements) data.sseBoundElements = []
    return data
  }

  function bindElementToSource(sourceElement, elt) {
    var bound = getSourceData(sourceElement).sseBoundElements
    if (bound.indexOf(elt) === -1) bound.push(elt)
  }

  function unbindElementFromSource(sourceElement, elt) {
    if (!sourceElement) return
    var data = api.getInternalData(sourceElement)
    var bound = data.sseBoundElements
    if (!bound) return
    var idx = bound.indexOf(elt)
    if (idx !== -1) bound.splice(idx, 1)
  }

  function removeElementListeners(elt) {
    var data = api.getInternalData(elt)
    var listeners = data.sseEventListeners
    if (!listeners) return
    var source = data.sseListenerSource
    for (var eventName in listeners) {
      if (Object.prototype.hasOwnProperty.call(listeners, eventName) && source) {
        try { source.removeEventListener(eventName, listeners[eventName]) } catch (e) {}
      }
    }
    data.sseEventListeners = null
    unbindElementFromSource(data.sseListenerSourceElement, elt)
    data.sseListenerSource = null
    data.sseListenerSourceElement = null
  }

  function cleanupElement(elt) {
    if (!elt || !elt.nodeType) return
    var internalData = api.getInternalData(elt)
    // Try to remove an EventSource when the source element is removed
    var source = internalData.sseEventSource
    if (source) {
      api.triggerEvent(elt, 'htmx:sseClose', {
        source,
        type: 'nodeReplaced',
      })
      try { source.close() } catch (e) {}
      internalData.sseEventSource = null
      internalData.sseEventSourceURL = null
      // listeners attached to this (now closed) source are inert; clear bookkeeping on bound elements
      var bound = internalData.sseBoundElements || []
      for (var i = 0; i < bound.length; i++) {
        var child = bound[i]
        if (!child) continue
        var childData = api.getInternalData(child)
        childData.sseEventListeners = null
        childData.sseListenerSource = null
        childData.sseListenerSourceElement = null
      }
      internalData.sseBoundElements = []
    }

    // Remove listeners registered by this element (if it's a swap/trigger element, not the source)
    removeElementListeners(elt)
  }

  /**
   * registerSSE looks for attributes that can contain sse events, right
   * now hx-trigger and sse-swap and adds listeners based on these attributes too
   * the closest event source
   *
   * @param {HTMLElement} elt
   * @param {boolean} [force] rebind listeners even if already registered (used on reconnect)
   */
  function registerSSE(elt, force) {
    // Add message handlers for every `sse-swap` attribute
    if (api.getAttributeValue(elt, 'sse-swap')) {
      // Find closest existing event source
      var sourceElement = api.getClosestMatch(elt, hasEventSource)
      if (sourceElement == null) {
        return null // no eventsource in parentage, orphaned element
      }

      // Set internalData and source
      var source = api.getInternalData(sourceElement).sseEventSource
      var eltData = api.getInternalData(elt)
      if (force && eltData.sseEventListeners) {
        // listeners were attached to a previous (closed) source; drop bookkeeping so we rebind
        eltData.sseEventListeners = null
        eltData.sseListenerSource = null
        eltData.sseListenerSourceElement = null
      }
      if (!eltData.sseEventListeners) eltData.sseEventListeners = {}
      eltData.sseListenerSource = source
      eltData.sseListenerSourceElement = sourceElement

      var sseSwapAttr = api.getAttributeValue(elt, 'sse-swap')
      var sseEventNames = sseSwapAttr.split(',')

      for (var i = 0; i < sseEventNames.length; i++) {
        const sseEventName = sseEventNames[i].trim()
        if (!sseEventName) continue
        if (eltData.sseEventListeners[sseEventName]) continue
        const listener = function(event) {
          // If the source is missing then close SSE
          if (maybeCloseSSESource(sourceElement)) {
            return
          }

          // If the body no longer contains the element, remove the listener
          if (!api.bodyContains(elt)) {
            removeElementListeners(elt)
            return
          }

          // swap the response into the DOM and trigger a notification
          if (!api.triggerEvent(elt, 'htmx:sseBeforeMessage', event)) {
            return
          }
          swap(elt, event.data)
          api.triggerEvent(elt, 'htmx:sseMessage', event)
        }

        // Register the new listener
        eltData.sseEventListeners[sseEventName] = listener
        source.addEventListener(sseEventName, listener)
      }
      bindElementToSource(sourceElement, elt)
    }

    // Add message handlers for every `hx-trigger="sse:*"` attribute
    if (api.getAttributeValue(elt, 'hx-trigger')) {
      // Find closest existing event source
      var sourceElement = api.getClosestMatch(elt, hasEventSource)
      if (sourceElement == null) {
        return null // no eventsource in parentage, orphaned element
      }

      // Set internalData and source
      var source = api.getInternalData(sourceElement).sseEventSource
      var eltData = api.getInternalData(elt)
      if (force && eltData.sseEventListeners) {
        eltData.sseEventListeners = null
        eltData.sseListenerSource = null
        eltData.sseListenerSourceElement = null
      }
      if (!eltData.sseEventListeners) eltData.sseEventListeners = {}
      eltData.sseListenerSource = source
      eltData.sseListenerSourceElement = sourceElement

      var triggerSpecs = api.getTriggerSpecs(elt)
      var added = false
      triggerSpecs.forEach(function(ts) {
        if (ts.trigger.slice(0, 4) !== 'sse:') {
          return
        }
        var eventName = ts.trigger.slice(4)
        if (!eventName) return
        if (eltData.sseEventListeners[eventName]) {
          added = true
          return
        }

        var listener = function (event) {
          if (maybeCloseSSESource(sourceElement)) {
            return
          }
          if (!api.bodyContains(elt)) {
            removeElementListeners(elt)
            return
          }
          // Trigger events to be handled by the rest of htmx
          htmx.trigger(elt, ts.trigger, event)
          htmx.trigger(elt, 'htmx:sseMessage', event)
        }

        // Register the new listener
        eltData.sseEventListeners[eventName] = listener
        source.addEventListener(eventName, listener)
        added = true
      })
      if (added) bindElementToSource(sourceElement, elt)
    }
  }

  /**
   * ensureEventSourceOnElement creates a new EventSource connection on the provided element.
   * If a usable EventSource already exists, then it is returned.  If not, then a new EventSource
   * is created and stored in the element's internalData.
   * @param {HTMLElement} elt
   * @param {number} retryCount
   * @returns {EventSource | null}
   */
  function ensureEventSourceOnElement(elt, retryCount) {
    if (elt == null) {
      return null
    }

    // handle extension source creation attribute
    if (api.getAttributeValue(elt, 'sse-connect')) {
      var sseURL = api.getAttributeValue(elt, 'sse-connect')
      if (sseURL == null) {
        return
      }

      var internalData = api.getInternalData(elt)
      var existing = internalData.sseEventSource
      if (existing) {
        if (retryCount || existing.readyState === EventSource.CLOSED || internalData.sseEventSourceURL !== sseURL) {
          // reconnect or URL changed: replace with a fresh source
          try { existing.close() } catch (e) {}
          internalData.sseEventSource = null
        } else {
          // already connected/connecting to the same URL
        }
      }
      if (!internalData.sseEventSource) {
        ensureEventSource(elt, sseURL, retryCount)
      }
    }

    registerSSE(elt)
  }

  function rebindBoundElements(sourceElement) {
    var data = api.getInternalData(sourceElement)
    var bound = (data.sseBoundElements || []).slice()
    for (var i = 0; i < bound.length; i++) {
      var child = bound[i]
      if (child && api.bodyContains(child)) {
        registerSSE(child, true)
      }
    }
  }

  function ensureEventSource(elt, url, retryCount) {
    var internalData = api.getInternalData(elt)
    var previous = internalData.sseEventSource
    if (previous) {
      try { previous.close() } catch (e) {}
    }

    var source = htmx.createEventSource(url)

    source.onerror = function(err) {
      // Log an error event
      api.triggerErrorEvent(elt, 'htmx:sseError', { error: err, source })

      // If parent no longer exists in the document, then clean up this EventSource
      if (maybeCloseSSESource(elt)) {
        return
      }

      // Otherwise, try to reconnect the EventSource
      if (source.readyState === EventSource.CLOSED) {
        retryCount = retryCount || 0
        retryCount = Math.max(Math.min(retryCount * 2, 128), 1)
        var timeout = retryCount * 500
        window.setTimeout(function() {
          ensureEventSourceOnElement(elt, retryCount)
        }, timeout)
      }
    }

    source.onopen = function(evt) {
      api.triggerEvent(elt, 'htmx:sseOpen', { source })

      if (retryCount && retryCount > 0) {
        // New EventSource instance: rebind all previously registered listeners to it.
        rebindBoundElements(elt)
        // Also pick up any children that were not yet registered.
        const childrenToFix = elt.querySelectorAll("[sse-swap], [data-sse-swap], [hx-trigger], [data-hx-trigger]")
        for (let i = 0; i < childrenToFix.length; i++) {
          registerSSE(childrenToFix[i])
        }
        // We want to increase the reconnection delay for consecutive failed attempts only
        retryCount = 0
      }
    }

    internalData.sseEventSource = source
    internalData.sseEventSourceURL = url


    var closeAttribute = api.getAttributeValue(elt, "sse-close");
    if (closeAttribute) {
      // close eventsource when this message is received
      source.addEventListener(closeAttribute, function() {
        api.triggerEvent(elt, 'htmx:sseClose', {
          source,
          type: 'message',
        })
        try { source.close() } catch (e) {}
      });
    }
  }

  /**
   * maybeCloseSSESource confirms that the parent element still exists.
   * If not, then any associated SSE source is closed and the function returns true.
   *
   * @param {HTMLElement} elt
   * @returns boolean
   */
  function maybeCloseSSESource(elt) {
    if (!api.bodyContains(elt)) {
      var source = api.getInternalData(elt).sseEventSource
      if (source != undefined) {
        api.triggerEvent(elt, 'htmx:sseClose', {
          source,
          type: 'nodeMissing',
        })
        try { source.close() } catch (e) {}
        api.getInternalData(elt).sseEventSource = null
        return true
      }
    }
    return false
  }


  /**
   * @param {HTMLElement} elt
   * @param {string} content
   */
  function swap(elt, content) {
    api.withExtensions(elt, function(extension) {
      content = extension.transformResponse(content, null, elt)
    })

    var swapSpec = api.getSwapSpecification(elt)
    var target = api.getTarget(elt)
    api.swap(target, content, swapSpec, { contextElement: elt })
  }


  function hasEventSource(node) {
    return api.getInternalData(node).sseEventSource != null
  }
})()
