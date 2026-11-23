/* htmx UI glue: CSRF, composer ergonomics, and scroll behaviour.
 *
 * Everything else is server-rendered.  Keep this file small and boring; the
 * islands that need real client state (terminal, kanban, charts) get their
 * own files later.
 */
(function () {
    'use strict';

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    // ── Per-document event client (WebSocket transport) ──────────────────
    // The id is unique per loaded document, so duplicated tabs cannot share a
    // Redis channel/watch set (closing one would unsubscribe the other).  A
    // boosted navigation keeps the same document and therefore the same id and
    // socket; reconnects reuse the id on purpose so the server sends `reset`.
    // An inline bootstrap in base.html sets it and sse-connect before htmx
    // processes; this is a resilient fallback for non-standard loads.
    var clientId = window.agentoneClientId || '';
    try {
        if (!clientId) {
            clientId = (window.crypto && crypto.randomUUID)
                ? crypto.randomUUID()
                : 'c' + Date.now() + Math.random().toString(36).slice(2);
            window.agentoneClientId = clientId;
        }
        if (document.body && !document.body.getAttribute('sse-connect')) {
            var eventUrl = document.body.getAttribute('data-ws-url') || '/app/ws/events/';
            document.body.setAttribute(
                'sse-connect',
                eventUrl + (eventUrl.indexOf('?') === -1 ? '?' : '&') + 'client=' + encodeURIComponent(clientId)
            );
            if (window.htmx && typeof htmx.process === 'function') {
                htmx.process(document.body);
            }
        }
    } catch (err) {
        if (window.console && console.error) console.error('client id setup failed:', err);
    }

    function watchUrl() {
        return (document.body && document.body.getAttribute('data-sse-watch-url')) || '/app/sse/watch';
    }

    function collectWatchKeys() {
        var keys = Object.create(null);
        function add(raw) {
            if (!raw) return;
            raw.split(',').forEach(function (part) {
                part = part.trim();
                if (part.slice(0, 4) !== 'sse:') return;
                var name = part.slice(4).split(/\s+/)[0];
                if (name && name !== 'reset') keys[name] = 1;
            });
        }
        function addSwap(raw) {
            if (!raw) return;
            raw.split(',').forEach(function (name) {
                name = name.trim();
                if (name) keys[name] = 1;
            });
        }
        document.querySelectorAll('[hx-trigger], [data-hx-trigger]').forEach(function (el) {
            add(el.getAttribute('hx-trigger'));
            add(el.getAttribute('data-hx-trigger'));
        });
        document.querySelectorAll('[sse-swap], [data-sse-swap]').forEach(function (el) {
            addSwap(el.getAttribute('sse-swap'));
            addSwap(el.getAttribute('data-sse-swap'));
        });
        return Object.keys(keys).sort();
    }

    var lastWatchPayload = '';   // last attempt, for debounce dedupe
    var lastSyncedPayload = '';  // last payload the server actually accepted
    var watchTimer = null;
    var watchRetryTimer = null;

    function syncWatch(force) {
        if (!clientId) return;
        var payload = JSON.stringify({ client: clientId, keys: collectWatchKeys() });
        if (!force && payload === lastWatchPayload) return;
        lastWatchPayload = payload;
        clearTimeout(watchRetryTimer);
        fetch(watchUrl(), {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: payload
        }).then(function (response) {
            if (!response.ok) {
                var error = new Error('watch sync rejected: HTTP ' + response.status);
                error.status = response.status;
                throw error;
            }
            lastSyncedPayload = payload;
        }).catch(function (err) {
            // The server still holds the previous watch set, and heartbeats
            // keep its TTL alive.  Caching the failed payload would leave this
            // tab subscribed to the old view indefinitely.
            lastWatchPayload = lastSyncedPayload;
            if (window.console && console.error) console.error('watch sync failed:', err);
            // A 4xx means these bytes were rejected; retrying them verbatim
            // cannot help.  The next DOM change will build a fresh payload.
            if (err && err.status && err.status < 500) return;
            watchRetryTimer = setTimeout(function () { syncWatch(true); }, 5000);
        });
    }

    function scheduleWatch() {
        clearTimeout(watchTimer);
        watchTimer = setTimeout(syncWatch, 150);
    }

    function markActiveRows() {
        var path = location.pathname.replace(/\/$/, '');
        document.querySelectorAll('a[data-session-id], [data-sidebar-active-key]').forEach(function (el) {
            var link = el.matches('a') ? el : el.querySelector('a');
            if (!link) return;
            var url;
            try { url = new URL(link.href, location.origin); } catch (e) { return; }
            var samePath = url.pathname.replace(/\/$/, '') === path;
            var sameQuery = !url.search || url.search === location.search;
            var active = samePath && sameQuery;
            var target = el.getAttribute('data-sidebar-active-target');
            if (target === 'closest:.ws-row') {
                var row = el.closest('.ws-row');
                if (row) row.classList.toggle('active', active);
            } else {
                el.classList.toggle('active', active);
            }
        });
    }

    // htmx form posts carry the hidden input, but non-form requests (fragment
    // refetches that ever become POSTs) need the header.
    //
    // Component wrappers advertise their ETag in ``data-component-etag``.
    // Ad-hoc live fragments (composer footer, panel body, polling output) use a
    // per-request-path ETag cache instead: their root element is often replaced
    // by the response, so the attribute cannot survive the swap.  Revalidating
    // them is what stops an SSE refresh from replacing unchanged buttons.
    var fragmentEtags = Object.create(null);

    function normalizePath(raw) {
        if (!raw) return '';
        try {
            var url = new URL(raw, window.location.origin);
            return url.pathname + url.search;
        } catch (err) {
            return String(raw);
        }
    }

    function requestPath(evt) {
        var detail = evt && evt.detail;
        if (!detail) return '';
        // ``configRequest`` exposes the resolved URL as ``path``; ``afterRequest``
        // exposes it as ``requestConfig.path`` and also carries ``pathInfo``.
        if (detail.requestConfig && detail.requestConfig.path) {
            return normalizePath(detail.requestConfig.path);
        }
        if (detail.path) return normalizePath(detail.path);
        var pathInfo = detail.pathInfo;
        return pathInfo && pathInfo.requestPath
            ? normalizePath(pathInfo.requestPath)
            : '';
    }

    document.addEventListener('htmx:configRequest', function (evt) {
        var token = csrfToken();
        if (token && evt.detail && evt.detail.headers) {
            evt.detail.headers['X-CSRFToken'] = token;
        }
        var elt = evt.detail && evt.detail.elt;
        var etag = elt && elt.getAttribute
            ? elt.getAttribute('data-component-etag')
            : '';
        // A self-loading component placeholder has no rendered HTML yet, so the
        // ETag cached for its URL belongs to a *different*, already-loaded DOM
        // node.  Reusing it makes the placeholder answer 204 and stay empty
        // when the parent fragment is re-opened.  Loaded components carry
        // their own ETag attribute; ad-hoc fragments keep the path cache.
        var isComponentPlaceholder = !!(elt && elt.getAttribute
            && (elt.getAttribute('hx-trigger') || '').indexOf('load') !== -1
            && elt.hasAttribute('data-component'));
        // A tool card whose detail pane still contains the loading marker is
        // also a first render.  Its URL can be cached from an earlier load or
        // SSE refresh; reusing that ETag answers 204 and leaves "Loading…".
        // Once the pane has rendered, this marker is gone and normal ETag
        // revalidation still prevents needless full-detail swaps.
        var target = evt.detail && evt.detail.target;
        var detailTarget = target && target.classList && target.classList.contains('webui-tool-detail')
            ? target
            : (elt && elt.querySelector ? elt.querySelector('.webui-tool-detail') : null);
        var isUnrenderedDetailPlaceholder = !!(
            detailTarget && detailTarget.querySelector &&
            detailTarget.querySelector('.webui-detail-loading')
        );
        if (!etag && !isComponentPlaceholder && !isUnrenderedDetailPlaceholder) {
            var path = requestPath(evt);
            if (path) etag = fragmentEtags[path] || '';
        }
        if (etag && evt.detail && evt.detail.headers) {
            evt.detail.headers['If-None-Match'] = etag;
            // Mark client-side revalidations: the server must ignore a bare
            // If-None-Match from the browser's own cache so a lazy fragment's
            // first load can never be skipped with a 204.
            evt.detail.headers['X-AgentOne-ETag'] = '1';
        }
    });

    document.addEventListener('htmx:afterRequest', function (evt) {
        var detail = evt.detail || {};
        var xhr = detail.xhr;
        if (!xhr) return;
        var verb = (detail.requestConfig && detail.requestConfig.verb) || 'get';
        if (String(verb).toLowerCase() !== 'get') return;
        var path = requestPath(evt);
        if (!path) return;
        var etag = xhr.getResponseHeader('ETag');
        if (etag) fragmentEtags[path] = etag;
        else delete fragmentEtags[path];
    });

    function autoGrow(el) {
        if (!el) return;
        el.style.height = '';
        var max = Math.max(80, window.innerHeight * 0.5);
        el.style.height = Math.min(el.scrollHeight, max) + 'px';
    }

    function threadEl() {
        return document.getElementById('thread');
    }

    function threadWrapper() {
        var el = threadEl();
        return el ? el.closest('[data-component="chat-thread"]') : null;
    }

    function chatThreadComponent(el) {
        if (!el || !el.closest) return null;
        return el.closest('[data-component="chat-thread"]');
    }

    function isThreadSwap(evt) {
        if (!evt || !evt.detail) return false;
        var target = evt.detail.target;
        if (!target) return false;
        if (target.matches && target.matches('[data-component="chat-thread"]')) return true;
        var el = threadEl();
        if (target === el) return true;
        var wrapper = threadWrapper();
        return !!(wrapper && target === wrapper);
    }

    function isThreadAreaSwap(evt) {
        if (!evt || !evt.detail || !evt.detail.target) return false;
        var target = evt.detail.target;
        return isThreadSwap(evt) || !!chatThreadComponent(target);
    }

    function nearBottom(el) {
        if (!el) return true;
        return el.scrollHeight - el.scrollTop - el.clientHeight < 200;
    }

    function scrollToBottom(el) {
        if (el) el.scrollTop = el.scrollHeight;
    }

    function scheduleScrollToBottom() {
        requestAnimationFrame(function () {
            scrollToBottom(threadEl());
        });
    }

    document.addEventListener('input', function (evt) {
        if (evt.target && evt.target.matches && evt.target.matches('.composer-chat-message')) {
            autoGrow(evt.target);
        }
    });

    document.addEventListener('keydown', function (evt) {
        var ta = evt.target;
        if (!ta || !ta.matches || !ta.matches('.composer-chat-message')) return;
        if (evt.isComposing) return;
        if (evt.key !== 'Enter') return;

        var mode = ta.dataset.sendKey || 'ctrl+enter';
        var send = mode === 'enter' ? !evt.shiftKey : (evt.ctrlKey || evt.metaKey);
        if (!send) return;

        evt.preventDefault();
        var form = ta.closest('form');
        if (!form) return;
        if (form.requestSubmit) form.requestSubmit();
        else form.submit();
    });

    // Remember whether the reader was at the bottom *before* a thread swap so
    // an SSE refresh never yanks them away from history they scrolled back to.
    var wasNearBottom = true;

    // A parent swap can detach a component wrapper while that wrapper's own
    // request is still in flight.  When a new tool call appears, the message
    // (MessagePart.message) and the thread (Message.session) refetch together;
    // whichever lands second leaves the other's target detached.  htmx's
    // preserve pass is document-wide: it pantries any live child whose id
    // matches a preserved element in the response, then cannot find that id in
    // the live DOM and leaves the child pantried.  The visible result is a tool
    // card with an empty <summary> after an event-driven render (a full reload
    // never races).  Such a response is already obsolete — the newer parent
    // swap rendered fresher state — so cancel the request before it is sent.
    document.addEventListener('htmx:beforeRequest', function (evt) {
        var target = evt.detail && evt.detail.target;
        if (target && target.isConnected === false) {
            evt.preventDefault();
        }
    });

    // Component wrappers are hx-preserve so a parent swap can keep an
    // already-loaded child.  htmx's preserve implementation (Re/He) also pantries
    // the swap target itself when the response carries the same preserved id,
    // which breaks a self-targeted outerHTML refresh (placeholder load, SSE/reset
    // refetch) and can drop the element or discard the response.  Hide the
    // target's id from the preserve lookup for the duration of the swap;
    // descendants keep their ids so parent swaps can still preserve loaded
    // children inside the replaced region.
    document.addEventListener('htmx:beforeSwap', function (evt) {
        var detail = evt.detail || {};
        var target = detail.target;
        if (!target || !target.id || !target.getAttribute) return;
        var swap = detail.swapOverride
            || (target.getAttribute('hx-swap') || target.getAttribute('data-hx-swap'))
            || (window.htmx && htmx.config && htmx.config.defaultSwapStyle)
            || 'innerHTML';
        swap = String(swap).split(/\s+/)[0].toLowerCase();
        if (swap.indexOf('outer') === -1) return;
        // Only relevant when the response is expected to preserve this element's id.
        if (!target.hasAttribute('hx-preserve') && !target.hasAttribute('data-hx-preserve')) return;
        target._hxOrigId = target.id;
        target.removeAttribute('id');
    });

    document.addEventListener('htmx:afterSwap', function (evt) {
        var target = evt.detail && evt.detail.target;
        // If the swap failed to replace the target, restore its id so future
        // requests/preserves still work.  After a successful outerHTML swap the
        // original node is detached and this is harmless.
        if (target && target._hxOrigId && !target.id && target.isConnected) {
            target.id = target._hxOrigId;
        }
    });

    // ── Providers settings: keep <details> open across HTMX swaps/reloads ──
    function providersCardEl() {
        return document.getElementById('providers-card');
    }

    function captureProviderOpenState() {
        var el = providersCardEl();
        if (!el) return;
        var open = [];
        try {
            el.querySelectorAll('details[data-open-key]').forEach(function (card) {
                if (card.open) open.push(card.getAttribute('data-open-key'));
            });
            sessionStorage.setItem('agentone:providers:open', JSON.stringify(open));
        } catch (e) {
            if (window.console && console.error) console.error('captureProviderOpenState failed:', e);
        }
    }

    function restoreProviderOpenState() {
        var el = providersCardEl();
        if (!el) return;
        var open = [];
        try {
            open = JSON.parse(sessionStorage.getItem('agentone:providers:open') || '[]');
        } catch (e) {
            open = [];
        }
        var set = new Set(open || []);
        try {
            el.querySelectorAll('details[data-open-key]').forEach(function (card) {
                var key = card.getAttribute('data-open-key');
                var shouldOpen = !!key && set.has(key);
                if (card.open !== shouldOpen) card.open = shouldOpen;
            });
        } catch (e) {
            if (window.console && console.error) console.error('restoreProviderOpenState failed:', e);
        }
    }

    // <details> open state is DOM-only, so any swap inside the thread (a
    // message refetch as well as a whole-thread refresh) would collapse every
    // card.  Track explicit user toggles instead of snapshotting around each
    // request: thread-area swaps overlap while a turn streams, and a snapshot
    // made by one request can be cleared by another before it is restored.
    // Cards the user never touched keep the server-rendered default.
    var openedThreadCards = new Set();
    var closedThreadCards = new Set();

    document.addEventListener('toggle', function (evt) {
        var card = evt.target;
        if (!card || !card.matches || !card.matches('details[data-open-key]')) return;
        var thread = threadEl();
        if (!thread || !thread.contains(card)) return;
        var key = card.getAttribute('data-open-key');
        if (!key) return;
        if (card.open) {
            openedThreadCards.add(key);
            closedThreadCards.delete(key);
        } else {
            closedThreadCards.add(key);
            openedThreadCards.delete(key);
        }
    }, true);

    function restoreOpenCards(el) {
        if (!el) return;
        try {
            el.querySelectorAll('details[data-open-key]').forEach(function (card) {
                var key = card.getAttribute('data-open-key');
                if (!key) return;
                var shouldOpen;
                if (openedThreadCards.has(key)) shouldOpen = true;
                else if (closedThreadCards.has(key)) shouldOpen = false;
                else return;  // server-rendered default wins
                if (card.open === shouldOpen) return;
                card.open = shouldOpen;
                if (shouldOpen && card.hasAttribute('hx-get')) {
                    htmx.trigger(card, 'toggle');
                }
            });
        } catch (e) {
            // Never let a card-restore failure take down the thread swap.
            if (window.console && console.error) console.error('restoreOpenCards failed:', e);
        }
    }

    document.addEventListener('htmx:beforeSwap', function (evt) {
        var pc = providersCardEl();
        if (pc && evt.detail && evt.detail.target === pc) {
            captureProviderOpenState();
        }
    });

    document.addEventListener('htmx:beforeRequest', function (evt) {
        var el = threadEl();
        if (!el) return;
        var trigger = evt.detail && evt.detail.elt;
        var wrapper = threadWrapper();
        var inThread = trigger === el || trigger === wrapper
            || (trigger && el.contains(trigger))
            || (wrapper && trigger && wrapper.contains(trigger))
            || !!(trigger && chatThreadComponent(trigger));
        if (inThread) {
            // Never yank a reader who is selecting text or has scrolled up.
            var selection = window.getSelection ? String(window.getSelection()) : '';
            wasNearBottom = !selection && nearBottom(el);
        }
    });

    document.addEventListener('htmx:afterSwap', function (evt) {
        if (!isThreadAreaSwap(evt)) return;
        var el = threadEl();
        if (el && wasNearBottom) {
            scheduleScrollToBottom();
        }
    });

    // Restore only after htmx finished settling: requests triggered from
    // inside the afterSwap stack are ignored by htmx's own event listeners.
    function ensureComponentPlaceholders(root) {
        try {
            if (!window.htmx) return;
            var scope = root && root.querySelectorAll ? root : document;
            var nodes = scope.querySelectorAll('[data-component][hx-get][hx-trigger]');
            nodes.forEach(function (el) {
                var trigger = el.getAttribute('hx-trigger') || '';
                // Only placeholders self-load on insertion; loaded components use SSE triggers.
                if (trigger.indexOf('load') === -1) return;
                if (el.dataset.phRequested) return;
                el.dataset.phRequested = '1';
                // htmx already processes elements it inserts itself and fires `load`
                // on them.  Triggering a second load here races that request: when both
                // responses succeed, the later outerHTML swap sees the first (already
                // loaded) component by id, moves it into htmx's preserve pantry, and
                // `He()` then removes it because no other node carries the id.  The
                // component disappears instead of rendering.  Only drive placeholders
                // that htmx did not initialize (inserted by plain JS/markup).
                var initialized = !!(el['htmx-internal-data'] && el['htmx-internal-data'].firstInitCompleted);
                if (!initialized) {
                    try { htmx.process(el); } catch (err) { /* already processed */ }
                    try { htmx.trigger(el, 'load'); } catch (err) { /* ignore */ }
                }
                // Keep the delayed safety net below: if the natural load was aborted
                // or failed, it re-issues the request once nothing is in flight.
                setTimeout(function () {
                    if (!el.isConnected) {
                        return;
                    }
                    var t = el.getAttribute('hx-trigger') || '';
                    if (t.indexOf('load') === -1) {
                        return;
                    }
                    // Avoid duplicating an in-flight natural load request.
                    if (el.classList.contains('htmx-request') || el.classList.contains('htmx-swapping')) {
                        setTimeout(function () {
                            if (el.isConnected && (el.getAttribute('hx-trigger') || '').indexOf('load') !== -1) {
                                delete el.dataset.phRequested;
                            }
                        }, 4000);
                        return;
                    }
                    try {
                        htmx.ajax('GET', el.getAttribute('hx-get'), {
                            source: el,
                            target: el,
                            swap: 'outerHTML'
                        });
                    } catch (err) { /* ignore */ }
                    // Permit another ensure pass later if this attempt did not complete.
                    setTimeout(function () {
                        if (el.isConnected && (el.getAttribute('hx-trigger') || '').indexOf('load') !== -1) {
                            delete el.dataset.phRequested;
                        }
                    }, 4000);
                }, 120);
            });
        } catch (e) {
            if (window.console && console.error) console.error('ensureComponentPlaceholders failed:', e);
        }
    }

    document.addEventListener('htmx:afterSettle', function (evt) {
        if (isThreadAreaSwap(evt)) {
            var el = threadEl();
            if (el) restoreOpenCards(el);
            // Placeholder-loaded thread (e.g. boosted nav) appears after settle;
            // ensure we land at the bottom on first render when appropriate.
            if (el && wasNearBottom) scheduleScrollToBottom();
            // After a self-swap (incl. outerHTML), evt.target can be the detached
            // node; scan the live thread/wrapper too so placeholders actually load.
            ensureComponentPlaceholders(el || threadWrapper() || document);
        }
        var pc = providersCardEl();
        if (pc && evt.target === pc) {
            restoreProviderOpenState();
        }
        markActiveRows();
        scheduleWatch();
        // evt.target can be a detached node after outerHTML swaps; always scan the
        // live document so newly inserted placeholders (e.g. thread children after a
        // reset/refetch) get their load requests.
        ensureComponentPlaceholders(document);
    });

    document.addEventListener('htmx:sseError', function () {
        document.documentElement.classList.add('sse-down');
    });

    document.addEventListener('htmx:sseOpen', function () {
        document.documentElement.classList.remove('sse-down');
        lastWatchPayload = '';
        scheduleWatch();
    });

    document.addEventListener('DOMContentLoaded', function () {
        scrollToBottom(threadEl());
        markActiveRows();
        scheduleWatch();
        // Re-post even when nothing changed.  There is no "unsubscribe on an
        // event I no longer render" fallback: a stream that died while a
        // replacement was registering, or a watch set lost to a racing
        // cleanup, would otherwise leave this tab silently unsubscribed.
        window.setInterval(function () {
            if (!document.hidden) syncWatch(true);
        }, 30000);
        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) syncWatch(true);
        });
        ensureComponentPlaceholders(document);
        var ta = document.querySelector('.composer-chat-message');
        if (ta) {
            restoreDraft(ta);
            autoGrow(ta);
            ta.focus();
        }
        bindKanban(document);
        bindMobileSidebar(document);
    });

    // ── Panel / disclosure toggles ───────────────────────────────────────
    function bindPanelToggles(root) {
        root.querySelectorAll('[data-panel-toggle]').forEach(function (btn) {
            if (btn.dataset.bound === '1') return;
            btn.dataset.bound = '1';
            btn.addEventListener('click', function () {
                var body = document.getElementById('chat-body');
                if (body) body.classList.toggle('panel-open');
            });
        });
        root.querySelectorAll('[data-toggle-target]').forEach(function (btn) {
            if (btn.dataset.bound === '1') return;
            btn.dataset.bound = '1';
            btn.addEventListener('click', function () {
                var target = document.querySelector(btn.getAttribute('data-toggle-target'));
                if (!target) return;
                if (target.tagName === 'DETAILS') target.open = true;
                else target.hidden = false;
                target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            });
        });
        // Dropdown toggles
        root.querySelectorAll('[data-dropdown-toggle]').forEach(function (btn) {
            if (btn.dataset.bound === '1') return;
            btn.dataset.bound = '1';
            btn.addEventListener('click', function (evt) {
                evt.stopPropagation();
                var dropdown = btn.closest('[data-dropdown]');
                if (!dropdown) return;
                var isOpen = dropdown.getAttribute('aria-expanded') === 'true';
                dropdown.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
                var menu = dropdown.querySelector('.webui-dropdown-menu');
                if (menu) menu.hidden = isOpen;
            });
        });
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', function (evt) {
        document.querySelectorAll('[data-dropdown][aria-expanded="true"]').forEach(function (dropdown) {
            if (!dropdown.contains(evt.target)) {
                dropdown.setAttribute('aria-expanded', 'false');
                var menu = dropdown.querySelector('.webui-dropdown-menu');
                if (menu) menu.hidden = true;
            }
        });
    });

    // Download format buttons: show "Preparing download…" hint while fetching
    function bindDownloadButtons(root) {
        root.querySelectorAll('.webui-dropdown-item[data-download-url]').forEach(function (btn) {
            if (btn.dataset.bound === '1') return;
            btn.dataset.bound = '1';
            btn.addEventListener('click', function () {
                var url = btn.getAttribute('data-download-url');
                var format = btn.getAttribute('data-download-format');
                var hint = root.querySelector('.webui-download-hint');
                var dropdown = btn.closest('[data-dropdown]');

                // Close dropdown
                if (dropdown) {
                    dropdown.setAttribute('aria-expanded', 'false');
                    var menu = dropdown.querySelector('.webui-dropdown-menu');
                    if (menu) menu.hidden = true;
                }

                // Show preparing hint
                if (hint) {
                    hint.hidden = false;
                }

                // Trigger download via hidden link (avoids navigation)
                var a = document.createElement('a');
                a.href = url;
                a.download = '';
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);

                // Hide hint after a short delay (download should have started)
                // We can't reliably detect when download actually starts, so use a timeout
                if (hint) {
                    // Clear any pending timeout from previous clicks to prevent stacking
                    if (hint._downloadHintTimeout) {
                        clearTimeout(hint._downloadHintTimeout);
                        hint._downloadHintTimeout = null;
                    }
                    // Set new timeout to hide the hint
                    hint._downloadHintTimeout = setTimeout(function () {
                        if (hint) hint.hidden = true;
                    }, 2000);
                }
            });
        });
    }

    // Run on initial load and after htmx swaps
    document.addEventListener('DOMContentLoaded', function () {
        bindDownloadButtons(document);
    });
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        bindDownloadButtons(evt.target);
    });

    // Panel tabs swap the whole body element via htmx, so the new body carries
    // the hx-get for the visible tab. Only the active marker needs syncing
    // here: htmx caches an element's request URL when it processes the node, so
    // rewriting hx-get on the old body would leave SSE refreshes on the tab
    // that was rendered with the page.
    function bindPanelTabs(root) {
        root.querySelectorAll('.webui-panel-tab').forEach(function (btn) {
            if (btn.dataset.bound === '1') return;
            btn.dataset.bound = '1';
            btn.addEventListener('click', function () {
                var strip = btn.closest('.webui-panel-tabs');
                if (strip) {
                    strip.querySelectorAll('.webui-panel-tab').forEach(function (other) {
                        other.classList.toggle('active', other === btn);
                    });
                }
            });
        });
    }

    // ── Mobile sidebar ───────────────────────────────────────────────────
    function bindMobileSidebar(root) {
        var toggle = root.querySelector('[data-mobile-sidebar]');
        var overlay = root.querySelector('[data-mobile-overlay]');

        function setOpen(open) {
            var sidebar = document.getElementById('sidebar');
            if (sidebar) sidebar.classList.toggle('mobile-open', open);
            if (overlay) overlay.classList.toggle('visible', open);
            if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        }

        if (toggle && toggle.dataset.bound !== '1') {
            toggle.dataset.bound = '1';
            toggle.addEventListener('click', function () {
                var sidebar = document.getElementById('sidebar');
                setOpen(!(sidebar && sidebar.classList.contains('mobile-open')));
            });
        }
        if (overlay && overlay.dataset.bound !== '1') {
            overlay.dataset.bound = '1';
            overlay.addEventListener('click', function () { setOpen(false); });
        }
    }

    function restoreMobileSidebar() {
        var overlay = document.querySelector('[data-mobile-overlay]');
        var sidebar = document.getElementById('sidebar');
        if (overlay && sidebar && overlay.classList.contains('visible')) {
            sidebar.classList.add('mobile-open');
        }
    }

    // ── Composer drafts ─────────────────────────────────────────────────
    function draftKey() {
        return 'webui:draft:' + window.location.pathname;
    }

    function saveDraft(ta) {
        try {
            if (ta.value) window.sessionStorage.setItem(draftKey(), ta.value);
            else window.sessionStorage.removeItem(draftKey());
        } catch (err) { /* private mode */ }
    }

    function restoreDraft(ta) {
        try {
            var saved = window.sessionStorage.getItem(draftKey());
            if (saved && !ta.value) ta.value = saved;
        } catch (err) { /* private mode */ }
    }

    document.addEventListener('input', function (evt) {
        if (evt.target && evt.target.matches && evt.target.matches('.composer-chat-message')) {
            saveDraft(evt.target);
        }
    });

    document.addEventListener('submit', function (evt) {
        var form = evt.target;
        if (!form || !form.matches || !form.matches('.webui-composer')) return;
        try { window.sessionStorage.removeItem(draftKey()); } catch (err) { /* private mode */ }
    });

    // ── Kanban drag & drop ───────────────────────────────────────────────
    // Allowed drags map one FSM action to the column it lands in.  The card
    // only carries the actions its current status allows, so an illegal drop
    // simply finds no action and is ignored.
    var ACTION_TARGET = {
        mark_ready: 'ready',
        defer: 'backlog',
        block: 'blocked',
        cancel: 'cancelled',
        finish: 'done',
        approve: 'done',
        reject: 'in_review',
        resume: 'in_progress',
        reopen: 'ready'
    };

    var draggedCard = null;

    function bindKanban(root) {
        root.querySelectorAll('.kanban-card a').forEach(function (a) {
            a.setAttribute('draggable', 'false');
        });
        root.querySelectorAll('.kanban-card').forEach(function (card) {
            if (card.dataset.bound === '1') return;
            card.dataset.bound = '1';
            card.addEventListener('dragstart', function (evt) {
                draggedCard = card;
                card.classList.add('dragging');
                if (evt.dataTransfer) {
                    evt.dataTransfer.effectAllowed = 'move';
                    evt.dataTransfer.setData('text/plain', card.dataset.id || '');
                }
            });
            card.addEventListener('dragend', function () {
                card.classList.remove('dragging');
                document.querySelectorAll('.kanban-column-body.drag-over')
                    .forEach(function (el) { el.classList.remove('drag-over'); });
                draggedCard = null;
            });
        });
        root.querySelectorAll('.kanban-column-body').forEach(function (body) {
            if (body.dataset.bound === '1') return;
            body.dataset.bound = '1';
            body.addEventListener('dragover', function (evt) {
                if (!draggedCard) return;
                evt.preventDefault();
                if (evt.dataTransfer) evt.dataTransfer.dropEffect = 'move';
                body.classList.add('drag-over');
            });
            body.addEventListener('dragleave', function (evt) {
                if (!body.contains(evt.relatedTarget)) body.classList.remove('drag-over');
            });
            body.addEventListener('drop', function (evt) {
                evt.preventDefault();
                body.classList.remove('drag-over');
                if (!draggedCard) return;
                var target = body.getAttribute('data-status');
                var allowed = (draggedCard.dataset.actions || '').split(/\s+/).filter(Boolean);
                var action = allowed.find(function (key) { return ACTION_TARGET[key] === target; });
                if (!action) return;
                postWorkItemAction(draggedCard.dataset.id, action);
            });
        });
    }

    function postWorkItemAction(id, action) {
        if (!id || !action) return;
        var form = document.createElement('form');
        form.method = 'post';
        form.action = '/app/workitems/' + encodeURIComponent(id) + '/action';
        form.style.display = 'none';
        var fields = {
            action: action,
            next: window.location.pathname + window.location.search
        };
        Object.keys(fields).forEach(function (name) {
            var input = document.createElement('input');
            input.type = 'hidden';
            input.name = name;
            input.value = fields[name];
            form.appendChild(input);
        });
        var token = csrfToken();
        if (token) {
            var csrf = document.createElement('input');
            csrf.type = 'hidden';
            csrf.name = 'csrfmiddlewaretoken';
            csrf.value = token;
            form.appendChild(csrf);
        }
        document.body.appendChild(form);
        form.submit();
    }

    // ── Log tail auto-scroll ─────────────────────────────────────────────
    document.addEventListener('htmx:afterSwap', function (evt) {
        var viewer = document.getElementById('log-viewer');
        if (!viewer || evt.target !== viewer) return;
        var pre = document.getElementById('log-tail');
        if (pre) pre.scrollTop = pre.scrollHeight;
    });

    // ── Message actions (copy / listen) ──────────────────────────────────
    function flashButton(btn, text) {
        var previous = btn.getAttribute('title') || '';
        btn.classList.add('copied');
        btn.setAttribute('title', text);
        window.setTimeout(function () {
            btn.classList.remove('copied');
            btn.setAttribute('title', previous);
        }, 1600);
    }

    function copyText(text, done) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(
                function () { done(true); },
                function () { done(false); }
            );
            return;
        }
        var area = document.createElement('textarea');
        area.value = text;
        area.style.position = 'fixed';
        area.style.top = '-9999px';
        document.body.appendChild(area);
        area.select();
        var ok = false;
        try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
        document.body.removeChild(area);
        done(ok);
    }

    document.addEventListener('click', function (evt) {
        var btn = evt.target && evt.target.closest
            ? evt.target.closest('[data-copy], [data-tts]')
            : null;
        if (!btn) return;
        var row = btn.closest('.msg-row');
        if (!row) return;
        var body = row.querySelector('.msg-body');
        var text = body ? (body.innerText || body.textContent || '').trim() : '';
        if (!text) return;

        if (btn.hasAttribute('data-copy')) {
            copyText(text, function (ok) {
                flashButton(btn, ok ? 'Copied!' : 'Copy failed');
            });
            return;
        }

        if (!window.speechSynthesis) {
            flashButton(btn, 'Speech not supported');
            return;
        }
        window.speechSynthesis.cancel();
        var utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = document.documentElement.lang || 'en';
        window.speechSynthesis.speak(utterance);
        flashButton(btn, 'Listening…');
    });

    // ── Image attachments ────────────────────────────────────────────────
    // Images are downscaled to a data URI in the browser (mirroring the
    // legacy composer) and carried in the hidden ``images`` JSON field.
    var ATTACH_MAX_EDGE = 1600;
    var ATTACH_LIMIT = 6;
    var attachItems = [];

    function attachForm() {
        return document.querySelector('.webui-composer');
    }

    function renderAttachTray() {
        var form = attachForm();
        if (!form) return;
        var tray = form.querySelector('[data-attach-tray]');
        var input = form.querySelector('input[name="images"]');
        if (input) {
            input.value = attachItems.length ? JSON.stringify(attachItems) : '';
        }
        if (!tray) return;
        tray.innerHTML = '';
        tray.hidden = attachItems.length === 0;
        attachItems.forEach(function (item, index) {
            var wrap = document.createElement('div');
            wrap.className = 'webui-attach-item';
            var img = document.createElement('img');
            img.src = item.content;
            img.alt = item.name || 'attached image';
            var remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'webui-attach-remove';
            remove.title = 'Remove attachment';
            remove.setAttribute('aria-label', 'Remove attachment');
            remove.textContent = '×';
            remove.addEventListener('click', function () {
                attachItems.splice(index, 1);
                renderAttachTray();
            });
            wrap.appendChild(img);
            wrap.appendChild(remove);
            tray.appendChild(wrap);
        });
    }

    function attachImageFile(file) {
        if (attachItems.length >= ATTACH_LIMIT) return;
        var reader = new FileReader();
        reader.onload = function (evt) {
            var image = new Image();
            image.onload = function () {
                var scale = Math.min(1, ATTACH_MAX_EDGE / Math.max(image.width, image.height));
                var canvas = document.createElement('canvas');
                canvas.width = Math.max(1, Math.round(image.width * scale));
                canvas.height = Math.max(1, Math.round(image.height * scale));
                var ctx = canvas.getContext('2d');
                ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
                var keepAlpha = file.type === 'image/png' || file.type === 'image/webp'
                    || file.type === 'image/gif';
                var dataUri = canvas.toDataURL(keepAlpha ? 'image/png' : 'image/jpeg', 0.85);
                attachItems.push({name: file.name, content: dataUri});
                renderAttachTray();
            };
            image.src = evt.target.result;
        };
        reader.readAsDataURL(file);
    }

    function handleAttachFiles(files) {
        for (var i = 0; i < files.length; i += 1) {
            var file = files[i];
            if (file.type && file.type.indexOf('image/') === 0 && file.type !== 'image/svg+xml') {
                attachImageFile(file);
            }
        }
    }

    document.addEventListener('click', function (evt) {
        if (!evt.target || !evt.target.closest) return;
        if (!evt.target.closest('[data-attach]')) return;
        var form = attachForm();
        var input = form ? form.querySelector('[data-attach-input]') : null;
        if (input) input.click();
    });

    document.addEventListener('change', function (evt) {
        var target = evt.target;
        if (!target || !target.matches || !target.matches('[data-attach-input]')) return;
        if (target.files) handleAttachFiles(target.files);
        target.value = '';
    });

    document.addEventListener('dragover', function (evt) {
        var box = evt.target && evt.target.closest
            ? evt.target.closest('.webui-composer') : null;
        if (!box) return;
        evt.preventDefault();
        if (evt.dataTransfer) evt.dataTransfer.dropEffect = 'copy';
        box.classList.add('drag-over');
    });

    document.addEventListener('dragleave', function (evt) {
        var box = evt.target && evt.target.closest
            ? evt.target.closest('.webui-composer') : null;
        if (box) box.classList.remove('drag-over');
    });

    document.addEventListener('drop', function (evt) {
        var box = evt.target && evt.target.closest
            ? evt.target.closest('.webui-composer') : null;
        if (!box) return;
        evt.preventDefault();
        box.classList.remove('drag-over');
        if (evt.dataTransfer && evt.dataTransfer.files) {
            handleAttachFiles(evt.dataTransfer.files);
        }
    });

    document.addEventListener('paste', function (evt) {
        var box = evt.target && evt.target.closest
            ? evt.target.closest('.webui-composer') : null;
        if (!box) return;
        var items = (evt.clipboardData && evt.clipboardData.items) || [];
        var files = [];
        for (var i = 0; i < items.length; i += 1) {
            var item = items[i];
            if (item.kind === 'file' && item.type && item.type.indexOf('image/') === 0) {
                var file = item.getAsFile();
                if (file) files.push(file);
            }
        }
        if (files.length) {
            evt.preventDefault();
            handleAttachFiles(files);
        }
    });

    document.addEventListener('htmx:afterRequest', function (evt) {
        var elt = evt.detail && evt.detail.elt;
        if (!elt || !elt.classList || !elt.classList.contains('webui-composer')) return;
        if (evt.detail.successful) {
            attachItems = [];
            renderAttachTray();
        }
    });

    // ── Bind dynamic fragments ───────────────────────────────────────────
    document.addEventListener('htmx:afterSettle', function (evt) {
        var target = evt.target;
        if (target && target.querySelectorAll) {
            bindPanelToggles(target);
            bindPanelTabs(target);
            bindKanban(target);
            bindMobileSidebar(target);
            restoreMobileSidebar();
        }
    });
    document.addEventListener('DOMContentLoaded', function () {
        bindPanelToggles(document);
        bindPanelTabs(document);
        bindCommandPalette();
        bindChatToc();
        restoreAroundScroll();
    });

    // ── Slash-command palette ────────────────────────────────────────────
    var commandPaletteDocBound = false;

    function commandData() {
        var node = document.getElementById('webui-commands');
        if (!node) return [];
        try {
            var parsed = JSON.parse(node.textContent || '[]');
            return Array.isArray(parsed) ? parsed : [];
        } catch (err) {
            return [];
        }
    }

    function composerTextarea() {
        return document.querySelector('.webui-composer .composer-chat-message');
    }

    function insertCommand(text) {
        var ta = composerTextarea();
        if (!ta) return;
        ta.value = text;
        ta.focus();
        ta.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function submitComposer() {
        var ta = composerTextarea();
        var form = ta ? ta.closest('form') : null;
        if (form && form.requestSubmit) form.requestSubmit();
    }

    function bindCommandPalette() {
        var palette = document.querySelector('[data-cmd-palette]');
        if (!palette || palette.dataset.bound === '1') return;
        palette.dataset.bound = '1';

        var commands = commandData();
        var list = palette.querySelector('[data-cmd-list]');
        var search = palette.querySelector('[data-cmd-search]');
        var formBox = palette.querySelector('[data-cmd-form]');
        var fieldsBox = palette.querySelector('[data-cmd-fields]');
        var nameBox = palette.querySelector('[data-cmd-form-name]');
        var descBox = palette.querySelector('[data-cmd-form-desc]');
        var active = null;

        function close() {
            palette.hidden = true;
            formBox.hidden = true;
            list.hidden = false;
        }

        function open(query) {
            palette.hidden = false;
            formBox.hidden = true;
            list.hidden = false;
            if (search) {
                search.value = query || '';
                search.focus();
            }
            renderList(query || '');
        }

        function renderList(query) {
            var needle = (query || '').toLowerCase();
            list.innerHTML = '';
            var matches = commands.filter(function (cmd) {
                return !needle
                    || cmd.name.toLowerCase().indexOf(needle) !== -1
                    || (cmd.description || '').toLowerCase().indexOf(needle) !== -1;
            });
            if (!matches.length) {
                var empty = document.createElement('div');
                empty.className = 'webui-cmd-empty';
                empty.textContent = commands.length ? 'No matching commands.' : 'No commands available for this agent.';
                list.appendChild(empty);
                return;
            }
            matches.forEach(function (cmd) {
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'webui-cmd-item';
                button.setAttribute('role', 'option');

                var nameRow = document.createElement('span');
                nameRow.className = 'webui-cmd-item-name';
                nameRow.textContent = '/' + cmd.name;
                var required = (cmd.fields || []).filter(function (field) { return field.required; });
                if (required.length) {
                    var arg = document.createElement('span');
                    arg.className = 'webui-cmd-item-arg';
                    arg.textContent = required.map(function (field) { return '<' + field.name + '>'; }).join(' ');
                    nameRow.appendChild(arg);
                }
                button.appendChild(nameRow);

                if (cmd.description) {
                    var desc = document.createElement('span');
                    desc.className = 'webui-cmd-item-desc';
                    desc.textContent = cmd.description;
                    button.appendChild(desc);
                }
                button.addEventListener('click', function () {
                    active = cmd;
                    if ((cmd.fields || []).length) {
                        showForm(cmd);
                    } else {
                        insertCommand('/' + cmd.name + ' ');
                        close();
                    }
                });
                list.appendChild(button);
            });
        }

        function showForm(cmd) {
            list.hidden = true;
            formBox.hidden = false;
            nameBox.textContent = '/' + cmd.name;
            descBox.textContent = cmd.description || '';
            fieldsBox.innerHTML = '';
            (cmd.fields || []).forEach(function (field) {
                var label = document.createElement('label');
                label.className = 'webui-cmd-field';
                var caption = document.createElement('span');
                caption.textContent = field.name + (field.required ? ' *' : '');
                label.appendChild(caption);

                var input;
                if (field.enum && field.enum.length) {
                    input = document.createElement('select');
                    field.enum.forEach(function (option) {
                        var opt = document.createElement('option');
                        opt.value = String(option);
                        opt.textContent = String(option);
                        input.appendChild(opt);
                    });
                } else if (field.type === 'boolean') {
                    input = document.createElement('select');
                    ['false', 'true'].forEach(function (value) {
                        var opt = document.createElement('option');
                        opt.value = value;
                        opt.textContent = value;
                        input.appendChild(opt);
                    });
                } else {
                    input = document.createElement('input');
                    input.type = field.input_type || 'text';
                    if (field.placeholder) input.placeholder = field.placeholder;
                    if (field.required) input.required = true;
                }
                input.dataset.field = field.name;
                input.dataset.fieldType = field.type || 'string';
                label.appendChild(input);
                if (field.description) {
                    var hint = document.createElement('span');
                    hint.textContent = field.description;
                    label.appendChild(hint);
                }
                fieldsBox.appendChild(label);
            });
        }

        function insertFromForm() {
            if (!active) return;
            var payload = {};
            fieldsBox.querySelectorAll('[data-field]').forEach(function (input) {
                if (input.value === '') return;
                var value = input.value;
                var type = input.dataset.fieldType;
                if (type === 'integer') value = parseInt(value, 10);
                else if (type === 'number') value = parseFloat(value);
                else if (type === 'boolean') value = value === 'true';
                payload[input.dataset.field] = value;
            });
            var text = '/' + active.name;
            if (Object.keys(payload).length) text += ' ' + JSON.stringify(payload);
            insertCommand(text);
            close();
            submitComposer();
        }

        var toggle = document.querySelector('[data-cmd-toggle]');
        if (toggle) {
            toggle.addEventListener('click', function () {
                if (palette.hidden) open('');
                else close();
            });
        }
        var closeBtn = palette.querySelector('[data-cmd-close]');
        if (closeBtn) closeBtn.addEventListener('click', close);
        var backBtn = palette.querySelector('[data-cmd-back]');
        if (backBtn) backBtn.addEventListener('click', function () {
            formBox.hidden = true;
            list.hidden = false;
            if (search) search.focus();
        });
        var insertBtn = palette.querySelector('[data-cmd-insert]');
        if (insertBtn) insertBtn.addEventListener('click', insertFromForm);
        if (search) {
            search.addEventListener('input', function () { renderList(search.value); });
            search.addEventListener('keydown', function (evt) {
                if (evt.key === 'Escape') { evt.preventDefault(); close(); }
            });
        }

        var ta = composerTextarea();
        if (ta) {
            ta.addEventListener('input', function () {
                var value = ta.value;
                if (value.charAt(0) === '/' && value.indexOf(' ') === -1 && value.indexOf('\n') === -1) {
                    if (palette.hidden) open(value.slice(1));
                    else if (search) { search.value = value.slice(1); renderList(value.slice(1)); }
                } else if (!palette.hidden) {
                    close();
                }
            });
            ta.addEventListener('keydown', function (evt) {
                if (evt.key === 'Escape' && !palette.hidden) {
                    evt.preventDefault();
                    close();
                }
            });
        }

        if (!commandPaletteDocBound) {
            commandPaletteDocBound = true;
            document.addEventListener('click', function (evt) {
                var current = document.querySelector('[data-cmd-palette]');
                if (!current || current.hidden) return;
                if (current.contains(evt.target)) return;
                if (evt.target.closest && evt.target.closest('[data-cmd-toggle]')) return;
                current.hidden = true;
            });
        }
    }

    // ── Chat table of contents ───────────────────────────────────────────
    function bindChatToc() {
        var toc = document.getElementById('chat-toc');
        if (!toc || toc.dataset.bound === '1') return;
        toc.dataset.bound = '1';
        toc.querySelectorAll('[data-toc-pk]').forEach(function (button) {
            button.addEventListener('click', function () {
                var pk = button.getAttribute('data-toc-pk');
                var thread = threadEl();
                var target = thread ? thread.querySelector('[data-pk="' + pk + '"]') : null;
                if (target && thread) {
                    var top = target.getBoundingClientRect().top
                        - thread.getBoundingClientRect().top + thread.scrollTop;
                    thread.scrollTo({ top: top, behavior: 'smooth' });
                    return;
                }
                var sessionID = toc.getAttribute('data-session');
                if (sessionID) {
                    window.location = '/app/chat/' + encodeURIComponent(sessionID)
                        + '?around=' + encodeURIComponent(pk);
                }
            });
        });
    }

    function restoreAroundScroll() {
        var params = new URLSearchParams(window.location.search);
        var around = params.get('around');
        if (!around) return;
        var thread = threadEl();
        var target = thread ? thread.querySelector('[data-pk="' + around + '"]') : null;
        if (!target || !thread) return;
        var top = target.getBoundingClientRect().top
            - thread.getBoundingClientRect().top + thread.scrollTop;
        thread.scrollTop = top;
    }

    // ── Inline message editing ───────────────────────────────────────────
    document.addEventListener('click', function (evt) {
        if (!evt.target || !evt.target.closest) return;
        var edit = evt.target.closest('[data-msg-edit]');
        if (edit) {
            var row = edit.closest('.msg-row');
            var form = row ? row.querySelector('.webui-msg-edit') : null;
            if (!form) return;
            form.hidden = !form.hidden;
            if (!form.hidden) {
                var ta = form.querySelector('textarea');
                if (ta) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }
            }
            return;
        }
        var cancel = evt.target.closest('[data-msg-edit-cancel]');
        if (cancel) {
            var parent = cancel.closest('.webui-msg-edit');
            if (parent) parent.hidden = true;
        }
    });

    // Persist provider <details> open state across toggles/submits.
    document.addEventListener('toggle', function (evt) {
        var t = evt.target;
        if (!t || !t.matches || !t.matches('details[data-open-key]')) return;
        var pc = providersCardEl();
        if (pc && pc.contains(t)) captureProviderOpenState();
    }, true);

    document.addEventListener('submit', function (evt) {
        var form = evt.target;
        var pc = providersCardEl();
        if (pc && form && pc.contains(form)) captureProviderOpenState();
    }, true);

    document.addEventListener('DOMContentLoaded', function () {
        restoreProviderOpenState();
    });
    // Initial run in case DOM already ready.
    if (document.readyState !== 'loading') {
        restoreProviderOpenState();
        ensureComponentPlaceholders(document);
    }

    // ── Partial navigation (hx-boost) ────────────────────────────────────
    // A boosted click swaps <body> with the server's shell fragment.  Re-bind
    // the few behaviours that live on nodes instead of using event delegation,
    // and reset per-chat UI state that a full reload used to clear.
    function isNavigation(evt) {
        var detail = evt.detail || {};
        return detail.boosted === true
            || detail.target === document.body
            || evt.target === document.body;
    }

    function initContent(root) {
        if (!root || !root.querySelectorAll) root = document;
        bindPanelToggles(root);
        bindPanelTabs(root);
        bindKanban(root);
        bindMobileSidebar(root);
        bindDownloadButtons(root);
        bindCommandPalette();
        bindChatToc();
        restoreProviderOpenState();
        restoreMobileSidebar();
    }

    function initEntry() {
        // A navigation starts a different conversation; card state must not
        // leak into it.
        openedThreadCards.clear();
        closedThreadCards.clear();
        scrollToBottom(threadEl());
        restoreAroundScroll();
        var ta = document.querySelector('.composer-chat-message');
        if (ta) {
            restoreDraft(ta);
            autoGrow(ta);
            ta.focus();
        }
    }

    // htmx fires ``afterSettle`` once per settled element, so collapse the
    // whole navigation into a single entry reset.
    var navSettled = false;

    document.addEventListener('htmx:afterSettle', function (evt) {
        initContent(evt.target);
        if (isNavigation(evt) && !navSettled) {
            navSettled = true;
            // Attachments and drafts belong to one conversation; a full reload
            // used to clear them.  Do the same now that navigation is partial.
            attachItems = [];
            initEntry();
        }
    });

    // Back/forward restores a cached copy of the page: data attributes survive
    // the clone but DOM listeners / htmx processing state do not, so drop our
    // bound markers, reprocess, and make sure any unloaded placeholders load.
    document.addEventListener('htmx:historyRestore', function () {
        document.querySelectorAll('[data-bound]').forEach(function (el) {
            el.removeAttribute('data-bound');
        });
        document.querySelectorAll('[data-ph-requested]').forEach(function (el) {
            delete el.dataset.phRequested;
        });
        navSettled = false;
        if (window.htmx) {
            try { htmx.process(document.body); } catch (err) { /* ignore */ }
        }
        initContent(document);
        initEntry();
        ensureComponentPlaceholders(document);
        scheduleWatch();
    });

    document.addEventListener('htmx:beforeRequest', function (evt) {
        if (evt.detail && evt.detail.boosted) {
            navSettled = false;
            document.documentElement.classList.add('nav-pending');
        }
    });

    function clearNavPending() {
        document.documentElement.classList.remove('nav-pending');
    }
    document.addEventListener('htmx:afterRequest', clearNavPending);
    document.addEventListener('htmx:sendError', clearNavPending);
    document.addEventListener('htmx:timeout', clearNavPending);

    // If a boosted request fails, fall back to a normal navigation instead of
    // leaving the user on a page that looks alive but does nothing.
    document.addEventListener('htmx:responseError', function (evt) {
        clearNavPending();
        var detail = evt.detail || {};
        if (detail.boosted && detail.pathInfo && detail.pathInfo.requestPath) {
            window.location.href = detail.pathInfo.requestPath;
        }
    });

    // An expired session redirects to the login page.  htmx would happily swap
    // that document into <body>; navigate for real instead.
    document.addEventListener('htmx:beforeSwap', function (evt) {
        var xhr = evt.detail && evt.detail.xhr;
        if (!xhr || !xhr.responseURL) return;
        if (xhr.responseURL.indexOf('/accounts/login/') === -1) return;
        evt.detail.shouldSwap = false;
        window.location.href = xhr.responseURL;
    });
})();

// Workspace sidebar tree collapse (persisted in localStorage).
(function () {
    'use strict';
    var KEY = 'wsCollapsed';
    function load() {
        try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; }
    }
    function save(state) { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }

    function apply() {
        var tree = document.getElementById('ws-sidebar-tree');
        if (!tree) return;
        var state = load();
        var rows = Array.prototype.slice.call(tree.querySelectorAll('.ws-row'));
        // Determine visibility: a row is visible if none of its ancestors (by depth) are collapsed.
        var stack = []; // stack of {pk, depth, visible}
        rows.forEach(function (row) {
            var depth = parseInt(row.getAttribute('data-ws-depth') || '0', 10);
            var pk = row.getAttribute('data-ws-pk');
            // pop stack to parent depth
            while (stack.length && stack[stack.length - 1].depth >= depth) stack.pop();
            var parent = stack.length ? stack[stack.length - 1] : null;
            var visible = !parent || (parent.visible && !state[parent.pk]);
            row.style.display = visible ? '' : 'none';
            // toggle chevron
            var btn = row.querySelector('.ws-tree-toggle');
            if (btn) {
                if (state[pk]) btn.classList.add('collapsed');
                else btn.classList.remove('collapsed');
                btn.textContent = state[pk] ? '▸' : '▾';
            }
            stack.push({ pk: pk, depth: depth, visible: visible });
        });
    }

    document.addEventListener('click', function (e) {
        var btn = e.target && e.target.closest && e.target.closest('.ws-tree-toggle');
        if (!btn) return;
        var pk = btn.getAttribute('data-ws-toggle');
        if (!pk) return;
        e.preventDefault();
        var state = load();
        state[pk] = !state[pk];
        save(state);
        apply();
    });

    // afterSettle rather than afterSwap: boosted navigation hands us a fresh
    // tree only once the swap and attribute settling are done.
    document.addEventListener('htmx:afterSettle', function () { apply(); });
    document.addEventListener('DOMContentLoaded', function () { apply(); });
    // initial (script may run after DOM ready)
    if (document.readyState !== 'loading') apply();
})();

// Draggable resize handles for sidebar / right panel.
(function () {
    'use strict';
    var MIN_W = 200, MAX_W = 600;
    // Below these widths the panels stop being side-by-side columns and become
    // stacked rows / slide-over drawers.  An inline width from a previous
    // desktop drag would override those media-query rules, so only restore a
    // saved width while the panel is actually resizable.
    var desktopMQ = window.matchMedia('(min-width: 901px)');
    function loadWidth(key, fallback) {
        try { var v = parseInt(localStorage.getItem(key), 10); return (v && v >= MIN_W && v <= MAX_W) ? v : fallback; } catch (e) { return fallback; }
    }
    function canResize(panel) {
        return desktopMQ.matches;
    }
    function applyPanelWidth(panel, w) {
        panel.style.width = w + 'px';
        if (!panel.classList.contains('sidebar')) {
            // Entity assistant uses flex-basis in its CSS; set flex so width wins.
            panel.style.flex = '0 0 ' + w + 'px';
        }
    }
    function clearPanelWidth(panel) {
        panel.style.removeProperty('width');
        if (!panel.classList.contains('sidebar')) panel.style.removeProperty('flex');
    }
    function savePanelWidth(panel) {
        var w = parseInt(panel.style.width, 10);
        if (!w) return;
        var key = panel.classList.contains('sidebar') ? 'sidebarWidth' : 'rightpanelWidth';
        try { localStorage.setItem(key, w); } catch (e) {}
    }
    function restoreWidths() {
        var s = document.querySelector('.sidebar');
        if (s) {
            if (desktopMQ.matches) s.style.width = loadWidth('sidebarWidth', 300) + 'px';
            else clearPanelWidth(s);
        }
        var rw = loadWidth('rightpanelWidth', null);
        document.querySelectorAll('.rightbar, .webui-chat-panel, .webui-entity-assistant, .insights-rightbar').forEach(function (r) {
            if (rw && canResize(r)) applyPanelWidth(r, rw);
            else clearPanelWidth(r);
        });
    }
    // Boosted navigation replaces the whole body, so the panel nodes and the
    // observed layout node have to be re-resolved after every swap.
    var observedLayout = null;
    var layoutObserver = null;

    function observeLayout() {
        var layout = document.querySelector('.layout');
        if (layout === observedLayout) return;
        if (layoutObserver) { layoutObserver.disconnect(); layoutObserver = null; }
        observedLayout = layout;
        if (!layout || !window.MutationObserver) return;
        layoutObserver = new MutationObserver(function () {
            if (!window._panelDragging) restoreWidths();
        });
        layoutObserver.observe(layout, { childList: true, subtree: false });
    }

    function refreshLayoutState() {
        restoreWidths();
        observeLayout();
    }

    refreshLayoutState();
    document.addEventListener('htmx:afterSettle', refreshLayoutState);
    desktopMQ.addEventListener('change', refreshLayoutState);

    var handle = null, startX = 0, startW = 0;
    document.addEventListener('mousedown', function (e) {
        var el = e.target && e.target.closest ? e.target.closest('.resize-handle') : null;
        if (!el || el.id === 'terminalResizeHandle') return;
        var panel = el.closest('.sidebar, .rightbar, .webui-chat-panel, .webui-entity-assistant, .insights-rightbar');
        if (!panel) return;
        handle = el;
        startX = e.clientX;
        startW = panel.getBoundingClientRect().width;
        document.body.classList.add('resizing');
        window._panelDragging = true;
        e.preventDefault();
    });
    document.addEventListener('mousemove', function (e) {
        if (!handle) return;
        var panel = handle.closest('.sidebar, .rightbar, .webui-chat-panel, .webui-entity-assistant, .insights-rightbar');
        if (!panel) return;
        var dx = e.clientX - startX;
        // Sidebar: handle on right edge, drag right = increase width
        // Right panels (chat, entity-assistant, insights-rightbar): handle on left edge, drag left = increase width
        var isSidebar = panel.classList.contains('sidebar');
        var w = isSidebar ? (startW + dx) : (startW - dx);
        w = Math.max(MIN_W, Math.min(MAX_W, w));
        applyPanelWidth(panel, w);
    });
    document.addEventListener('mouseup', function () {
        if (!handle) return;
        var panel = handle.closest('.sidebar, .rightbar, .webui-chat-panel, .webui-entity-assistant, .insights-rightbar');
        if (panel) savePanelWidth(panel);
        handle = null;
        document.body.classList.remove('resizing');
        window._panelDragging = false;
    });
    // The handles are focusable separators, so support arrow-key resizing too.
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        var el = e.target && e.target.closest ? e.target.closest('.resize-handle') : null;
        if (!el || el.id === 'terminalResizeHandle') return;
        var panel = el.closest('.sidebar, .rightbar, .webui-chat-panel, .webui-entity-assistant, .insights-rightbar');
        if (!panel || !canResize(panel)) return;
        var step = e.shiftKey ? 40 : 10;
        var delta = e.key === 'ArrowRight' ? step : -step;
        if (!panel.classList.contains('sidebar')) delta = -delta;
        var w = Math.max(MIN_W, Math.min(MAX_W, Math.round(panel.getBoundingClientRect().width) + delta));
        applyPanelWidth(panel, w);
        savePanelWidth(panel);
        e.preventDefault();
    });
})();

// Preserve scroll positions across full-page posts and reloads.
// Form actions (cancel, toggle, save, ...) do a POST + redirect back to the
// same URL; without this every nested scroll container would reset to the top.
(function () {
    'use strict';
    var KEY = 'agentone:scroll';
    var MAX_CONTAINERS = 25;

    function currentUrl() {
        return window.location.pathname + window.location.search;
    }

    function currentPath() {
        return window.location.pathname;
    }

    function elementPath(el) {
        var parts = [];
        while (el && el !== document.body && el.parentElement) {
            var index = 1;
            var sibling = el;
            while ((sibling = sibling.previousElementSibling)) {
                if (sibling.tagName === el.tagName) index += 1;
            }
            parts.unshift(el.tagName.toLowerCase() + ':nth-of-type(' + index + ')');
            el = el.parentElement;
        }
        return parts.length ? 'body>' + parts.join('>') : '';
    }

    function captureScroll() {
        var positions = [];
        var doc = document.scrollingElement || document.documentElement;
        if (doc && doc.scrollTop) positions.push({document: true, top: doc.scrollTop});
        var nodes = document.querySelectorAll('body *');
        for (var i = 0; i < nodes.length && positions.length < MAX_CONTAINERS; i += 1) {
            var el = nodes[i];
            if (!el.scrollTop || el.scrollHeight <= el.clientHeight) continue;
            var path = elementPath(el);
            if (path) positions.push({path: path, top: el.scrollTop});
        }
        try {
            window.sessionStorage.setItem(KEY, JSON.stringify({
                url: currentUrl(),
                path: currentPath(),
                positions: positions
            }));
        } catch (err) { /* private mode */ }
    }

    function restoreScroll() {
        var raw;
        try { raw = window.sessionStorage.getItem(KEY); } catch (err) { return; }
        if (!raw) return;
        try { window.sessionStorage.removeItem(KEY); } catch (err) { /* private mode */ }
        var saved;
        try { saved = JSON.parse(raw); } catch (err) { return; }
        if (!saved || saved.path !== currentPath()) return;
        (saved.positions || []).forEach(function (entry) {
            if (entry.document) {
                var doc = document.scrollingElement || document.documentElement;
                if (doc) doc.scrollTop = entry.top;
                return;
            }
            var target = null;
            try { target = document.querySelector(entry.path); } catch (err) { target = null; }
            if (target) target.scrollTop = entry.top;
        });
    }

    window.addEventListener('pagehide', captureScroll);
    window.addEventListener('pageshow', function (evt) {
        if (evt.persisted) {
            try { window.sessionStorage.removeItem(KEY); } catch (err) { /* private mode */ }
            return;
        }
        restoreScroll();
    });
    if (document.readyState === 'complete') restoreScroll();
})();

// Preserve sidebar scroll position across htmx swaps (SSE/boost refreshes)
// and full page navigations (e.g. clicking an item in a sidebar list).
(function () {
    'use strict';
    var STORAGE_KEY = 'agentone:sidebar-scroll';
    var SCROLL_SELECTORS = ['.session-list', '.side-list', '.ws-tree'];
    var savedSidebarScroll = null;

    function scrollContainers() {
        var nodes = [];
        SCROLL_SELECTORS.forEach(function (sel) {
            document.querySelectorAll('#sidebar ' + sel).forEach(function (el) {
                nodes.push(el);
            });
        });
        return nodes;
    }

    function captureSidebarScroll() {
        savedSidebarScroll = scrollContainers().map(function (el) { return el.scrollTop; });
    }

    function persistSidebarScroll() {
        var tops = scrollContainers().map(function (el) { return el.scrollTop; });
        try {
            window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tops));
        } catch (err) { /* private mode */ }
    }

    function restoreSidebarScroll() {
        var tops = savedSidebarScroll;
        if (!tops) {
            try {
                var raw = window.sessionStorage.getItem(STORAGE_KEY);
                if (raw) tops = JSON.parse(raw);
            } catch (err) { /* private mode */ }
        }
        if (!tops || !tops.length) return;
        var nodes = scrollContainers();
        for (var i = 0; i < nodes.length && i < tops.length; i += 1) {
            var top = parseInt(tops[i], 10);
            if (!isNaN(top)) nodes[i].scrollTop = top;
        }
        savedSidebarScroll = tops;
    }

    function clearPersistedSidebarScroll() {
        try { window.sessionStorage.removeItem(STORAGE_KEY); } catch (err) { /* private mode */ }
        savedSidebarScroll = null;
    }

    function isSidebarSwapTarget(target) {
        return !!target && (
            target.id === 'sidebar' ||
            target === document.body ||
            (target.tagName === 'BODY')
        );
    }

    function activeTargetForLink(link) {
        var sel = link.getAttribute('data-sidebar-active-target');
        if (sel && sel.indexOf('closest:') === 0) {
            return link.closest(sel.slice(8)) || link;
        }
        return link;
    }

    function setActiveSidebarItem(link) {
        if (!link) return;
        var key = link.getAttribute('data-sidebar-active-key') || link.getAttribute('data-session-id');
        if (!key) return;
        var attr = link.hasAttribute('data-sidebar-active-key') ? 'data-sidebar-active-key' : 'data-session-id';
        var links = document.querySelectorAll('a[' + attr + ']');
        links.forEach(function (item) {
            var match = String(item.getAttribute(attr)) === String(key);
            var target = activeTargetForLink(item);
            if (match) target.classList.add('active');
            else target.classList.remove('active');
        });
    }

    document.addEventListener('click', function (evt) {
        var link = evt.target && evt.target.closest
            ? evt.target.closest('a.session-item, a[data-sidebar-active-key]')
            : null;
        if (!link) return;
        persistSidebarScroll();
        captureSidebarScroll();
        setActiveSidebarItem(link);
    }, true);

    document.addEventListener('htmx:beforeRequest', function (evt) {
        var trigger = evt.detail && evt.detail.elt;
        if (trigger && trigger.closest && trigger.closest('a.session-item, a[data-sidebar-active-key]')) {
            persistSidebarScroll();
            captureSidebarScroll();
        }
    });

    document.addEventListener('htmx:beforeSwap', function (evt) {
        var target = evt.detail && evt.detail.target;
        if (isSidebarSwapTarget(target)) {
            captureSidebarScroll();
        }
    });

    document.addEventListener('htmx:afterSwap', function (evt) {
        var target = evt.target;
        if (isSidebarSwapTarget(target)) {
            restoreSidebarScroll();
        }
        var elt = evt.detail && evt.detail.elt;
        if (elt && elt.matches && elt.matches('a.session-item, a[data-sidebar-active-key]')) {
            setActiveSidebarItem(elt);
        }
    });

    document.addEventListener('htmx:afterSettle', function (evt) {
        var target = evt.target;
        if (isSidebarSwapTarget(target)) {
            restoreSidebarScroll();
            clearPersistedSidebarScroll();
        }
    });

    function initRestore() {
        restoreSidebarScroll();
        window.setTimeout(clearPersistedSidebarScroll, 500);
    }

    document.addEventListener('DOMContentLoaded', initRestore);
    if (document.readyState !== 'loading') initRestore();
})();

// Preserve #thread scroll position across htmx swaps of the chat-thread
// component.  The component is replaced wholesale on new messages, which would
// otherwise reset the scroll container to the top.
(function () {
    'use strict';
    var saved = null;
    var wasAtBottom = false;
    var skipRestore = false;
    function threadEl() {
        return document.querySelector("[data-component='chat-thread'] #thread")
            || document.querySelector('#thread');
    }
    document.addEventListener('htmx:beforeSwap', function (evt) {
        var elt = evt && evt.detail && evt.detail.elt;
        skipRestore = !!(elt && elt.closest && elt.closest('.webui-load-older'));
        var el = threadEl();
        if (el) {
            saved = el.scrollTop;
            wasAtBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 40;
        }
    });
    document.addEventListener('htmx:afterSwap', function () {
        window.setTimeout(function () {
            if (!skipRestore) {
                var el = threadEl();
                if (el) {
                    if (wasAtBottom) el.scrollTop = el.scrollHeight;
                    else if (saved !== null) el.scrollTop = saved;
                }
            }
            saved = null;
            wasAtBottom = false;
            skipRestore = false;
        }, 0);
    });
})();
