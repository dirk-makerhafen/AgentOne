(function () {
    'use strict';

    var PLACEHOLDER = '<div class="insights-rightbar-empty">Select a row to see details.</div>';

    function init() {
        var splits = document.querySelectorAll('[data-insights-split]');
        for (var i = 0; i < splits.length; i++) {
            bindSplit(splits[i]);
        }
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
        var closeBtn = split.querySelector('[data-insights-close]');
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
            if (panel && window.innerWidth <= 1100) panel.classList.add('open');
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
        document.body.addEventListener('htmx:afterSwap', function (evt) {
            if (panelBody && evt.detail && evt.detail.target === panelBody) {
                panelBody.removeAttribute('aria-busy');
            }
        });

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
})();