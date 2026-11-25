(function () {
    'use strict';

    // Single-instance guard – the script runs once per browser session (deferred
    // <script> in the head is not re-executed by htmx).  The guard is reset at
    // the top of init() so that htmx navigation always re-binds splits.
    // bindSplit() uses its own split.dataset.bound guard to avoid double-binding.

    var PLACEHOLDER = '<div class="insights-rightbar-empty">Select a row to see details.</div>';
    var swapListenerBound = false;

    function init() {
        var splits = document.querySelectorAll('[data-insights-split]');
        for (var i = 0; i < splits.length; i++) {
            bindSplit(splits[i]);
        }
        bindRightbarTables();
    }

    // The provider-detail rightbar has its own compact table: no row selection
    // or detail loading, just client-side sorting of the rendered offerings.
    // data-bound is cleared by app.js on history restore, so re-binding there
    // (and after every htmx settle, which re-renders the rightbar body) is safe.
    function bindRightbarTables() {
        document.querySelectorAll('table[data-rp-sortable]').forEach(function (table) {
            if (table.dataset.bound === '1') return;
            table.dataset.bound = '1';
            var body = table.tBodies[0];
            if (!body) return;
            var rows = Array.prototype.slice.call(body.querySelectorAll('tr[data-rp-row]'));
            var headers = Array.prototype.slice.call(table.querySelectorAll('th[data-rp-sort]'));
            if (!rows.length || !headers.length) return;
            var defaultHeader = table.querySelector('th[data-rp-sort-default]') || headers[0];
            var state = {
                col: defaultHeader.getAttribute('data-rp-sort'),
                dir: defaultHeader.getAttribute('data-rp-sort-default') || 'asc'
            };

            function cellValue(row, key) {
                var cell = row.querySelector('td[data-rp-sort-key="' + key + '"]');
                return cell ? (cell.getAttribute('data-rp-sort-value') || '') : '';
            }

            function sortRows() {
                var th = table.querySelector('th[data-rp-sort="' + state.col + '"]');
                var numeric = !!(th && th.getAttribute('data-rp-sort-type') === 'number');
                var sorted = rows.slice();
                sorted.sort(function (a, b) {
                    var av = cellValue(a, state.col);
                    var bv = cellValue(b, state.col);
                    if (numeric) {
                        var an = parseFloat(av);
                        var bn = parseFloat(bv);
                        var aMissing = !isFinite(an);
                        var bMissing = !isFinite(bn);
                        if (aMissing !== bMissing) return aMissing ? 1 : -1;
                        if (aMissing && bMissing) return 0;
                        return state.dir === 'asc' ? an - bn : bn - an;
                    }
                    return state.dir === 'asc'
                        ? String(av).localeCompare(String(bv), undefined, { sensitivity: 'base' })
                        : String(bv).localeCompare(String(av), undefined, { sensitivity: 'base' });
                });
                sorted.forEach(function (row) { body.appendChild(row); });
                headers.forEach(function (header) {
                    if (header.getAttribute('data-rp-sort') === state.col) {
                        header.setAttribute('data-rp-sort-dir', state.dir);
                        header.setAttribute('aria-sort', state.dir === 'asc' ? 'ascending' : 'descending');
                    } else {
                        header.removeAttribute('data-rp-sort-dir');
                        header.removeAttribute('aria-sort');
                    }
                });
            }

            headers.forEach(function (header) {
                header.setAttribute('tabindex', '0');
                header.addEventListener('click', function () {
                    var col = header.getAttribute('data-rp-sort');
                    if (state.col === col) {
                        state.dir = state.dir === 'asc' ? 'desc' : 'asc';
                    } else {
                        state.col = col;
                        state.dir = 'asc';
                    }
                    sortRows();
                });
                header.addEventListener('keydown', function (evt) {
                    if (evt.key === 'Enter' || evt.key === ' ') {
                        evt.preventDefault();
                        header.click();
                    }
                });
            });
            sortRows();
        });
    }

    function bindSplit(split) {
        if (split.dataset.bound === '1') return;
        split.dataset.bound = '1';
        var table = split.querySelector('table[data-insights-table]');
        var body = table ? table.querySelector('tbody') : null;
        if (!table || !body) return;
        var rows = Array.prototype.slice.call(body.querySelectorAll('tr[data-detail-url]'));
        if (!rows.length) return;
        var emptyRow = body.querySelector('.insights-empty-row');
        var search = split.querySelector('[data-insights-search]');
        var count = split.querySelector('[data-insights-count]');
        var panel = document.getElementById('insights-detail');
        var panelBody = document.getElementById('insights-detail-body');
        var closeBtn = document.querySelector('[data-insights-close]');
        var total = rows.length;

        var state = { col: null, dir: 'asc', query: '' };
        // Default sort: first header with data-sort-default, else first sortable header.
        var defaultHeader = table.querySelector('th[data-sort-default]') || table.querySelector('th[data-sort]');
        if (defaultHeader) {
            state.col = defaultHeader.getAttribute('data-sort');
            state.dir = defaultHeader.getAttribute('data-sort-default') || (defaultHeader.getAttribute('data-sort-type') === 'number' ? 'asc' : 'asc');
            defaultHeader.setAttribute('data-sort-dir', state.dir);
        }

        function cellValue(row, key) {
            var td = row.querySelector('td[data-sort-key="' + key + '"]');
            return td ? (td.getAttribute('data-sort-value') || '') : '';
        }

        function sortRows() {
            var th = table.querySelector('th[data-sort="' + state.col + '"]');
            var numeric = !!(th && th.getAttribute('data-sort-type') === 'number');
            var unrankedLast = state.col === 'rank';
            var sorted = rows.slice();
            sorted.sort(function (a, b) {
                var av = cellValue(a, state.col);
                var bv = cellValue(b, state.col);
                if (unrankedLast) {
                    var an = parseFloat(av);
                    var bn = parseFloat(bv);
                    var aMissing = !isFinite(an);
                    var bMissing = !isFinite(bn);
                    if (aMissing !== bMissing) return aMissing ? 1 : -1;
                    if (aMissing && bMissing) return 0;
                    return state.dir === 'asc' ? an - bn : bn - an;
                }
                if (numeric) {
                    var an2 = parseFloat(av);
                    var bn2 = parseFloat(bv);
                    if (!isFinite(an2)) return 1;
                    if (!isFinite(bn2)) return -1;
                    return state.dir === 'asc' ? an2 - bn2 : bn2 - an2;
                }
                return state.dir === 'asc'
                    ? String(av).localeCompare(String(bv), undefined, { sensitivity: 'base' })
                    : String(bv).localeCompare(String(av), undefined, { sensitivity: 'base' });
            });
            sorted.forEach(function (row) { body.appendChild(row); });
            if (emptyRow) body.appendChild(emptyRow);
            // arrow indicators
            table.querySelectorAll('th[data-sort]').forEach(function (h) {
                if (h.getAttribute('data-sort') === state.col) {
                    h.setAttribute('data-sort-dir', state.dir);
                } else {
                    h.removeAttribute('data-sort-dir');
                }
            });
        }

        function applyFilter() {
            var shown = 0;
            rows.forEach(function (row) {
                var match = !state.query || (row.getAttribute('data-search') || '').toLowerCase().indexOf(state.query) !== -1;
                row.hidden = !match;
                if (match) shown++;
            });
            if (emptyRow) emptyRow.hidden = shown !== 0;
            if (count) {
                count.textContent = (shown === total)
                    ? total + (total === 1 ? ' row' : ' rows')
                    : (shown + ' of ' + total);
            }
        }

        function loadDetail(url) {
            if (!url || !panelBody) return;
            panelBody.setAttribute('aria-busy', 'true');
            if (window.htmx) {
                window.htmx.ajax('GET', url, { target: '#insights-detail-body', swap: 'innerHTML' });
            } else {
                fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                    .then(function (r) { return r.text(); })
                    .then(function (html) {
                        panelBody.innerHTML = html;
                        if (window.htmx) window.htmx.process(panelBody);
                    })
                    .catch(function () {
                        panelBody.innerHTML = '<div class="insights-rightbar-empty">Could not load details.</div>';
                    })
                    .finally(function () { panelBody.removeAttribute('aria-busy'); });
            }
        }

        function selectRow(row, opts) {
            opts = opts || {};
            if (!row) return;
            rows.forEach(function (r) {
                r.classList.remove('selected');
                r.removeAttribute('aria-selected');
            });
            row.classList.add('selected');
            row.setAttribute('aria-selected', 'true');
            if (!opts.silentScroll) {
                try { row.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } catch (e) {}
            }
            loadDetail(row.getAttribute('data-detail-url'), row.id);
            if (panel && window.innerWidth <= 900) panel.classList.add('open');
            if (opts.updateHash !== false) {
                try { history.replaceState(null, '', '#' + row.id); } catch (e) {}
            }
        }

        function findRowById(id) {
            for (var i = 0; i < rows.length; i++) {
                if (rows[i].id === id) return rows[i];
            }
            return null;
        }

        // header click → sort
        table.querySelectorAll('th[data-sort]').forEach(function (th) {
            th.addEventListener('click', function () {
                var col = th.getAttribute('data-sort');
                if (state.col === col) {
                    state.dir = state.dir === 'asc' ? 'desc' : 'asc';
                } else {
                    state.col = col;
                    state.dir = 'asc';
                }
                sortRows();
            });
        });

        // search
        if (search) {
            search.addEventListener('input', function () {
                state.query = search.value.trim().toLowerCase();
                applyFilter();
            });
        }

        // row click / keyboard
        rows.forEach(function (row) {
            row.addEventListener('click', function (evt) {
                if (evt.target && evt.target.closest && evt.target.closest('a, button, input, form')) return;
                selectRow(row);
            });
            row.addEventListener('keydown', function (evt) {
                if (evt.key === 'Enter' || evt.key === ' ') {
                    evt.preventDefault();
                    selectRow(row);
                }
            });
        });

        // close
        if (closeBtn) {
            closeBtn.addEventListener('click', function () {
                rows.forEach(function (r) {
                    r.classList.remove('selected');
                    r.removeAttribute('aria-selected');
                });
                if (panelBody) panelBody.innerHTML = PLACEHOLDER;
                if (panel) panel.classList.remove('open');
                try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {}
            });
        }

        // htmx swap bookkeeping for the rightbar body
        if (!swapListenerBound) {
            swapListenerBound = true;
            document.body.addEventListener('htmx:afterSwap', function (evt) {
                var body = document.getElementById('insights-detail-body');
                if (body && evt.detail && evt.detail.target === body) {
                    body.removeAttribute('aria-busy');
                }
            });
        }

        // initial selection
        var initial = null;
        var hash = (location.hash || '').replace('#', '');
        if (hash) initial = findRowById(hash);
        if (!initial && rows.length) initial = rows[0];
        sortRows();
        applyFilter();
        if (initial) {
            window.setTimeout(function () {
                selectRow(initial, { silentScroll: false, updateHash: true });
            }, 500);
        }

        window.addEventListener('hashchange', function () {
            var id = (location.hash || '').replace('#', '');
            var row = findRowById(id);
            if (row) selectRow(row, { silentScroll: false });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    // Partial navigation replaces the page shell, so bind the new table after
    // every htmx settle (the dataset guard makes repeat calls a no-op).
    document.addEventListener('htmx:afterSettle', init);
    // History restores re-insert a cloned tree without its listeners; app.js
    // clears the bound markers on the same event, so re-init here too.
    document.addEventListener('htmx:historyRestore', init);
})();
