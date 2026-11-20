/* EventSource-shaped WebSocket transport for htmx's `sse:` triggers.
 *
 * The server publishes observable keys as small JSON frames on one WebSocket
 * per tab (see webui/core/events.py).  This shim lets the vendored sse.js
 * extension and every existing `hx-trigger="sse:<key>"` component stay exactly
 * as they are: htmx calls htmx.createEventSource(url), gets an object with the
 * EventSource API, and receives a MessageEvent whose `type` is the key and
 * whose `data` is the JSON hint.
 *
 * Why not a real EventSource?  Chrome counts open EventSource streams against
 * its six-per-origin HTTP/1.1 connection pool, so the 5th/6th tab starves new
 * document and component requests.  WebSockets use a separate, much larger
 * per-host pool (255 in Chromium, 200 in Firefox).
 */
(function () {
    'use strict';

    if (!window.htmx) return;

    function wsUrl(url) {
        var parsed = new URL(url, window.location.href);
        parsed.protocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
        return parsed.href;
    }

    // EventSource's readyState constants: CONNECTING=0, OPEN=1, CLOSED=2.
    // During an internal reconnect we stay at 0, like a native EventSource,
    // so sse.js does not open a second socket alongside the retrying one.
    function WsEventSource(url) {
        this.url = url;
        this.readyState = 0;
        this.onopen = null;
        this.onerror = null;
        this._listeners = Object.create(null);
        this._retry = 0;
        this._closed = false;
        this._connect();
    }

    WsEventSource.prototype._connect = function () {
        if (this._closed) return;
        var socket;
        try {
            socket = new WebSocket(wsUrl(this.url));
        } catch (err) {
            this._retryLater();
            return;
        }
        var self = this;
        this._socket = socket;

        socket.onopen = function (evt) {
            if (self._socket !== socket || self._closed) return;
            self.readyState = 1;
            self._retry = 0;
            if (self.onopen) self.onopen(evt);
        };
        socket.onmessage = function (evt) {
            if (self._socket !== socket || self._closed) return;
            var payload;
            try { payload = JSON.parse(evt.data); } catch (err) { return; }
            if (!payload || typeof payload.event !== 'string') return;
            self._dispatch(payload.event, payload.data === undefined ? '{}' : payload.data);
        };
        socket.onerror = function (evt) {
            if (self._socket !== socket || self._closed) return;
            if (self.onerror) self.onerror(evt);
        };
        socket.onclose = function (evt) {
            if (self._socket !== socket || self._closed) return;
            self._socket = null;
            // 4400/4401 are deliberate server rejections (bad/missing client
            // id or unauthenticated user). Retrying only hammers the server;
            // like a native EventSource on a 401/403, stay closed.
            if (evt.code === 4400 || evt.code === 4401) {
                self.readyState = 2;
                self.close();
                return;
            }
            self.readyState = 0;  // reconnecting, not permanently closed
            if (self.onerror) self.onerror(evt);
            self._retryLater();
        };
    };

    WsEventSource.prototype._retryLater = function () {
        if (this._closed || this._retryTimer) return;
        this._retry = Math.min(this._retry + 1, 5);
        var delay = Math.min(500 * Math.pow(2, this._retry - 1), 10000);
        var self = this;
        this._retryTimer = window.setTimeout(function () {
            self._retryTimer = null;
            self._connect();
        }, delay);
    };

    WsEventSource.prototype._dispatch = function (name, data) {
        var listeners = this._listeners[name];
        if (!listeners || !listeners.length) return;
        var event = new MessageEvent(name, { data: String(data) });
        listeners.slice().forEach(function (fn) { fn(event); });
    };

    WsEventSource.prototype.addEventListener = function (name, fn) {
        if (!name || typeof fn !== 'function') return;
        (this._listeners[name] || (this._listeners[name] = [])).push(fn);
    };

    WsEventSource.prototype.removeEventListener = function (name, fn) {
        var list = this._listeners[name];
        if (!list) return;
        var idx = list.indexOf(fn);
        if (idx !== -1) list.splice(idx, 1);
    };

    WsEventSource.prototype.close = function () {
        if (this._closed) return;
        this._closed = true;
        this.readyState = 2;
        if (this._retryTimer) {
            window.clearTimeout(this._retryTimer);
            this._retryTimer = null;
        }
        var socket = this._socket;
        this._socket = null;
        if (socket) {
            try { socket.close(); } catch (err) { /* already gone */ }
        }
    };

    // sse.js only installs its default when htmx.createEventSource is unset.
    htmx.createEventSource = function (url) { return new WsEventSource(url); };
})();
