from __future__ import annotations
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from ui.lib.model_view import ModelView
from server.models.sessions.session import SessionModel
from ui.lib.multi_queryset_view import MultiQuerySetView
from ui.chat.message import MessageView
from ui.chat.query import QueryView
from ui.chat.response import ResponseView
from ui.chat.log_debug import DebugLogView
from ui.chat.log_fs import FilesystemLogView
from ui.chat.task_call import TaskCallView
import unicodedata

class TaskTraceView1(ModelView):
    DOM_ELEMENT_CLASS = "TaskTraceView resizable-container"
    DOM_ELEMENT_EXTRAS = 'data-orientation="horizontal" style="height: 600px;"'
    TEMPLATE_STR = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
 
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

 
  /* ── TOP BAR ─────────────────────────────────────────── */
  .topbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }
  .topbar-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-family: var(--mono);
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 9px;
    border-radius: 3px;
    font-size: 11px;
    font-family: var(--mono);
    font-weight: 500;
    border: 1px solid;
  }
  .pill-blue   { background: var(--call-fill);  border-color: var(--call-stroke);  color: var(--call-text);  }
  .pill-green  { background: var(--run-fill);   border-color: var(--run-stroke);   color: var(--run-text);   }
  .pill-amber  { background: var(--hook-fill);  border-color: var(--hook-stroke);  color: var(--hook-text);  }
  .pill-gray   { background: var(--bg3);        border-color: var(--border2);      color: var(--text2);      }
 
  .spacer { flex: 1; }
 
  .ctrl-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .ctrl-group label {
    font-size: 11px;
    color: var(--text2);
    font-family: var(--mono);
  }
  input[type=range] {
    -webkit-appearance: none;
    appearance: none;
    width: 100px;
    height: 4px;
    background: var(--bg4);
    border-radius: 2px;
    outline: none;
    border: 1px solid var(--border2);
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 14px; height: 14px;
    border-radius: 50%;
    background: var(--accent);
    cursor: pointer;
    border: 2px solid var(--bg);
  }
 
  /* ── TRACE LAYOUT ────────────────────────────────────── */
  .trace-wrap {
    overflow-x: auto;
    overflow-y: auto;
    max-height: calc(100vh - 54px - 200px);
  }
  .trace-inner {
    min-width: 700px;
  }
 
  /* ruler */
  .ruler {
    display: flex;
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
  }
  .ruler-spacer { width: var(--label-col); min-width: var(--label-col); border-right: 1px solid var(--border); }
  .ruler-ticks  { flex: 1; position: relative; height: 28px; }
  .ruler-tick {
    position: absolute;
    top: 0; height: 100%;
    border-left: 1px solid var(--border);
    display: flex;
    align-items: center;
    padding-left: 4px;
  }
  .ruler-tick span {
    font-size: 10px;
    font-family: var(--mono);
    color: var(--text3);
    white-space: nowrap;
  }
 
  /* lane rows */
  .lane {
    display: flex;
    align-items: center;
    height: var(--row-h);
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: background 0.1s;
    position: relative;
  }
  .lane:hover { background: rgba(79,156,249,0.04); }
  .lane.selected { background: rgba(79,156,249,0.07); }
 
  .lane-label {
    width: var(--label-col);
    min-width: var(--label-col);
    padding: 0 10px;
    border-right: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 6px;
    overflow: hidden;
    height: 100%;
  }
  .lane-indent { display: inline-block; flex-shrink: 0; }
  .lane-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .lane-name {
    font-size: 12px;
    color: var(--text);
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
  }
  .lane-dur {
    font-size: 10px;
    font-family: var(--mono);
    color: var(--text3);
    white-space: nowrap;
    flex-shrink: 0;
  }
 
  /* span track */
  .lane-track {
    flex: 1;
    position: relative;
    height: 100%;
    overflow: hidden;
  }
  .span-bar {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    height: 18px;
    border-radius: 3px;
    border-left: 2px solid;
    display: flex;
    align-items: center;
    min-width: 4px;
    cursor: pointer;
    transition: filter 0.1s, opacity 0.1s;
  }
  .span-bar:hover { filter: brightness(1.25); }
  .span-label-in {
    font-size: 10px;
    font-family: var(--mono);
    padding: 0 5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
    pointer-events: none;
  }
  .span-label-out {
    position: absolute;
    left: calc(100% + 5px);
    font-size: 10px;
    font-family: var(--mono);
    color: var(--text2);
    white-space: nowrap;
    pointer-events: none;
  }
 
  /* tree connector lines */
  .lane-track-grid {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }
 
  /* ── DETAIL PANEL ────────────────────────────────────── */
  .detail {
    background: var(--bg2);
    border-top: 1px solid var(--border);
    padding: 14px 16px;
    display: none;
  }
  .detail.open { display: block; }
  .detail-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
  }
  .detail-title {
    font-size: 14px;
    font-weight: 600;
    font-family: var(--mono);
    color: var(--text);
  }
  .detail-grid {
    display: grid;
    grid-template-columns: 160px 1fr;
    gap: 5px 12px;
    font-size: 12px;
  }
  .dk { color: var(--text2); font-family: var(--mono); }
  .dv { color: var(--text);  font-family: var(--mono); word-break: break-all; }
 
  .ref-group { margin-top: 10px; }
  .ref-group-label { font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 5px; font-family: var(--mono); }
  .ref-chips { display: flex; gap: 5px; flex-wrap: wrap; }
  .ref-chip {
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 11px;
    font-family: var(--mono);
    cursor: pointer;
    border: 1px solid var(--border2);
    color: var(--accent);
    background: var(--bg3);
    transition: background 0.1s;
  }
  .ref-chip:hover { background: var(--bg4); border-color: var(--accent2); }
 
  /* ── LOADING / EMPTY ─────────────────────────────────── */
  .state-msg {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 160px;
    color: var(--text3);
    font-family: var(--mono);
    font-size: 12px;
    flex-direction: column;
    gap: 8px;
  }
  .state-msg .spinner {
    width: 20px; height: 20px;
    border: 2px solid var(--border2);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>

 
<!-- ════════════════════════════════════════════════════════
     TOP BAR
═════════════════════════════════════════════════════════ -->
<div class="topbar">
  <span class="topbar-title" id="trace-name">Loading trace…</span>
 
  <span class="pill pill-blue"  id="badge-calls">— calls</span>
  <span class="pill pill-green" id="badge-runs">— runs</span>
  <span class="pill pill-gray"  id="badge-dur">—</span>
 
  <div class="spacer"></div>
 
  <div class="ctrl-group">
    <label>Zoom</label>
    <input type="range" id="zoom-slider" min="1" max="8" step="0.1" value="1">
    <span id="zoom-label" style="font-size:11px;font-family:var(--mono);color:var(--text2);min-width:28px">1×</span>
  </div>
</div>
 
<!-- ════════════════════════════════════════════════════════
     TRACE
═════════════════════════════════════════════════════════ -->
<div class="trace-wrap" id="trace-wrap">
  <div class="trace-inner" id="trace-inner">
    <div class="state-msg" id="state-msg">
      <div class="spinner"></div>
      <span>Loading trace…</span>
    </div>
  </div>
</div>
 
<!-- ════════════════════════════════════════════════════════
     DETAIL
═════════════════════════════════════════════════════════ -->
<div class="detail" id="detail-panel"></div>
 
 
<!-- ════════════════════════════════════════════════════════
     JAVASCRIPT
═════════════════════════════════════════════════════════ -->
<script>

 
/* ── CONFIG ─────────────────────────────────────────── */
SPAN_STYLES = {
  call: { fill: 'var(--call-fill)', stroke: 'var(--call-stroke)', text: 'var(--call-text)', dot: 'var(--call-stroke)' },
  run:  { fill: 'var(--run-fill)',  stroke: 'var(--run-stroke)',  text: 'var(--run-text)',  dot: 'var(--run-stroke)'  },
  hook: { fill: 'var(--hook-fill)', stroke: 'var(--hook-stroke)', text: 'var(--hook-text)', dot: 'var(--hook-stroke)' },
  cb:   { fill: 'var(--cb-fill)',   stroke: 'var(--cb-stroke)',   text: 'var(--cb-text)',   dot: 'var(--cb-stroke)'   },
};
 
/* ── STATE ───────────────────────────────────────────── */
_byId    = {};
_lanes   = [];
_minTs   = 0;
_totalDur = 1;
_zoom    = 1;
_selected = null;
 
/* ── ENTRY POINT ─────────────────────────────────────── */
 
/**
 * Call this function with your trace payload.
 *
 * Shape:
 *   {
 *     root_call_id : "call:123",
 *     calls: [ ...get_call() responses... ],
 *     runs:  [ ...get_run()  responses... ]
 *   }
 */

function renderTrace(data) {
    var { calls = [], runs = [], root_call_id } = data;

    _byId = {};
    [...calls, ...runs].forEach(n => {
        n._type     = n.id.startsWith('run:') ? 'run' : 'call';
        n._children = [];
        n._parent   = null;
        _byId[n.id] = n;
    });

    
    // ADD THESE RIGHT HERE:
    console.log("calls[0]:", calls[0]);
    console.log("calls[0].related_agent_task_runs:", calls[0]?.related_agent_task_runs);
    console.log("byId run keys:", Object.keys(_byId).filter(k => k.startsWith('run:')));

    // link each call → its runs
    calls.forEach(c => {
        (c.related_agent_task_runs || []).forEach(rid => {
            if (_byId[rid]) {
                _byId[c.id]._children.push(_byId[rid]);
                _byId[rid]._parent = _byId[c.id];
            }
        });
    });

    // link each run → its subtask calls AND result calls
    runs.forEach(r => {
        [
            ...(r.child_taskcalls || []),
            ...(r.taskrun_result_references  || []),
        ].forEach(cid => {
            if (_byId[cid] && !_byId[cid]._parent) {
                _byId[r.id]._children.push(_byId[cid]);
                _byId[cid]._parent = _byId[r.id];
            }
        });
    });

    // link calls → callback/hook calls (only if not already parented)
    calls.forEach(c => {
        [
            ...(c.taskcall_on_success_callbacks || []),
            ...(c.taskcall_on_error_callbacks   || []),
            ...(c.taskcall_before_run_hooks     || []),
            ...(c.taskcall_after_run_hooks      || []),
            ...(c.taskcall_arg_references       || []),
        ].forEach(cid => {
            if (_byId[cid] && !_byId[cid]._parent) {
                _byId[c.id]._children.push(_byId[cid]);
                _byId[cid]._parent = _byId[c.id];
            }
        });
    });

    // anything still unparented gets attached to root as a fallback
    calls.forEach(c => {
        if (_byId[c.id] && !_byId[c.id]._parent && c.id !== root_call_id) {
            _byId[root_call_id]._children.push(_byId[c.id]);
            _byId[c.id]._parent = _byId[root_call_id];
        }
    });



    root = _byId[root_call_id] || calls[0];
    if (!root) { showState('No root call found.'); return; }

    // simple DFS flatten — no special run interleaving needed anymore
    _lanes = [];
    function walk(node, depth) {
        node._depth = depth;
        _lanes.push(node);
        node._children.forEach(c => walk(c, depth + 1));
    }
    walk(root, 0);
 
    // time bounds
    allTs = _lanes.flatMap(n => [n.created_at, n.ended_at]).filter(Boolean);
    _minTs    = Math.min(...allTs);
    _totalDur = Math.max(Math.max(...allTs) - _minTs, 0.001);
    
    // badges
    document.getElementById('trace-name').textContent = (root.agent_task_definition || root_call_id || 'Trace').split(':')[0];
    document.getElementById('badge-calls').textContent = `${calls.length} calls`;
    document.getElementById('badge-runs').textContent  = `${runs.length} runs`;
    document.getElementById('badge-dur').textContent   =
        _fmtDur(_totalDur * 1000);
    
    _renderLanes();
}
 
 
/* ── RENDER ──────────────────────────────────────────── */
function _renderLanes() {
  container = document.getElementById('trace-inner');
  container.innerHTML = '';
 
  if (!_lanes.length) { showState('No spans to display.'); return; }
 
  // ruler
  ruler = document.createElement('div');
  ruler.className = 'ruler';
  ruler.innerHTML = `<div class="ruler-spacer"></div><div class="ruler-ticks" id="ruler-ticks"></div>`;
  container.appendChild(ruler);
  _buildRuler();
 
  // lanes
  _lanes.forEach(node => {
    container.appendChild(_buildLane(node));
  });
}
 
function _buildRuler() {
  el = document.getElementById('ruler-ticks');
  if (!el) return;
  el.innerHTML = '';
  TICKS = 8;
  for (i = 0; i <= TICKS; i++) {
    pct = (i / TICKS) * 100 * _zoom;
    if (pct > 100 * _zoom + 1) break;
    t = document.createElement('div');
    t.className = 'ruler-tick';
    t.style.left = pct + '%';
    t.innerHTML = `<span>${_fmtDur((i / TICKS) * _totalDur * 1000)}</span>`;
    el.appendChild(t);
  }
}
 
function _buildLane(node) {
  style  = SPAN_STYLES[node._type] || SPAN_STYLES.call;
  taskName = (node.agent_task_definition || node.id || '').split(':')[0];
  tStart = (node.created_at || _minTs) - _minTs;
  tEnd   = (node.ended_at   || (node.created_at || _minTs) + 0.001) - _minTs;
  leftPct  = (tStart / _totalDur) * 100 * _zoom;
  widthPct = Math.max((tEnd - tStart) / _totalDur * 100 * _zoom, 0.3);
  dur      = Math.round((tEnd - tStart) * 1000);
  indent   = node._depth * 16;
 
  lane = document.createElement('div');
  lane.className  = 'lane' + (_selected === node.id ? ' selected' : '');
  lane.dataset.id = node.id;
  lane.onclick    = () => _selectNode(node.id);
 
  // label column
  lbl = document.createElement('div');
  lbl.className = 'lane-label';
  lbl.innerHTML = `
    <span class="lane-indent" style="width:${indent}px"></span>
    <span class="lane-dot" style="background:${style.dot}"></span>
    <span class="lane-name" title="${taskName}">${taskName}</span>
    <span class="lane-dur">${dur}ms</span>
  `;
 
  // span track
  track = document.createElement('div');
  track.className = 'lane-track';
 
  bar = document.createElement('div');
  bar.className = 'span-bar';
  bar.style.cssText = `
    left: ${leftPct}%;
    width: ${widthPct}%;
    background: ${style.fill};
    border-left-color: ${style.stroke};
  `;
 
  showInside = widthPct > 8;
  if (showInside) {
    bar.innerHTML = `<span class="span-label-in" style="color:${style.text}">${taskName}</span>`;
  } else {
    bar.innerHTML = `<span class="span-label-out">${taskName}</span>`;
  }
 
  track.appendChild(bar);
  lane.appendChild(lbl);
  lane.appendChild(track);
  return lane;
}
 
 
/* ── SELECTION / DETAIL ──────────────────────────────── */
function _selectNode(id) {
  _selected = id;
 
  // highlight
  document.querySelectorAll('.lane').forEach(el => {
    el.classList.toggle('selected', el.dataset.id === id);
  });
 
  node = _byId[id];
  if (!node) return;
 
  tStart = (node.created_at || 0) - _minTs;
  tEnd   = (node.ended_at   || (node.created_at || 0) + 0.001) - _minTs;
  dur    = Math.round((tEnd - tStart) * 1000);
 
  style  = SPAN_STYLES[node._type] || SPAN_STYLES.call;
  taskName = (node.agent_task_definition || id).split(':')[0];
 
  function chips(ids, label) {
    if (!ids?.length) return '';
    inner = ids.map(cid =>
      `<span class="ref-chip" onclick="_selectNode('${cid}')">${cid}</span>`
    ).join('');
    return `<div class="ref-group">
      <div class="ref-group-label">${label}</div>
      <div class="ref-chips">${inner}</div>
    </div>`;
  }
 
  panel = document.getElementById('detail-panel');
  panel.className = 'detail open';
  panel.innerHTML = `
    <div class="detail-header">
      <span class="detail-title">${taskName}</span>
      <span class="pill" style="background:${style.fill};border-color:${style.stroke};color:${style.text}">${node._type}</span>
      <span class="pill pill-gray">${dur}ms</span>
    </div>
    <div class="detail-grid">
      <span class="dk">id</span>            <span class="dv">${node.id}</span>
      <span class="dk">agent</span>         <span class="dv">${node.agent || '—'}</span>
      <span class="dk">agent_instance</span><span class="dv">${node.agent_instance || '—'}</span>
      <span class="dk">task_definition</span><span class="dv">${node.agent_task_definition || '—'}</span>
      <span class="dk">created_at</span>    <span class="dv">${node.created_at ? new Date(node.created_at * 1000).toISOString() : '—'}</span>
      <span class="dk">ended_at</span>      <span class="dv">${node.ended_at ? new Date(node.ended_at * 1000).toISOString() : 'in progress'}</span>
      <span class="dk">dont_start_before</span><span class="dv">${node.dont_start_before ? new Date(node.dont_start_before * 1000).toISOString() : '—'}</span>
      <span class="dk">dont_start_after</span><span class="dv">${node.dont_start_after  ? new Date(node.dont_start_after  * 1000).toISOString() : '—'}</span>
    </div>
    ${chips(node.taskcall_arg_references,        'arg references')}
    ${chips(node.taskcall_on_success_callbacks,  'on success callbacks')}
    ${chips(node.taskcall_on_error_callbacks,    'on error callbacks')}
    ${chips(node.taskcall_before_run_hooks,      'before run hooks')}
    ${chips(node.taskcall_after_run_hooks,       'after run hooks')}
    ${chips(node.taskrun_arg_references,         'run arg references')}
    ${chips(node.taskrun_result_references,      'result references')}
    ${chips(node.child_taskcalls,     'subtask references')}
  `;
}
 
 
/* ── ZOOM ────────────────────────────────────────────── */
document.getElementById('zoom-slider').addEventListener('input', function () {
  _zoom = parseFloat(this.value);
  document.getElementById('zoom-label').textContent = _zoom.toFixed(1) + '×';
  _renderLanes();
  // re-apply selection highlight
  if (_selected) {
    document.querySelectorAll('.lane').forEach(el => {
      el.classList.toggle('selected', el.dataset.id === _selected);
    });
  }
});
 
 
/* ── HELPERS ─────────────────────────────────────────── */
function _fmtDur(ms) {
  if (ms >= 1000) return (ms / 1000).toFixed(2) + 's';
  if (ms >= 1)    return Math.round(ms) + 'ms';
  return (ms * 1000).toFixed(0) + 'µs';
}
 
function showState(msg) {
  document.getElementById('trace-inner').innerHTML =
    `<div class="state-msg"><span>${msg}</span></div>`;
}
 
async function loadTrace() {
  try {
    // ── Step 1: get root call id from the template ──────────
    // PyHtmlGui injects the root call pk via the template variable.
    // The TEMPLATE_STR already sets root_call_pk in a <script> tag
    // (see the companion Python snippet below).
    rootCallId = window.__ROOT_CALL_ID__;
    if (!rootCallId) {
      // Fallback: no root call available for this agent instance
      showState('No root call found for this agent instance.');
      return;
    }
 
    allCalls = {};
    allRuns  = {};
 
    // ── Step 2: BFS walk via pyview ──────────────────────────
    callQueue = [rootCallId];
    runQueue  = [];
 
    while (callQueue.length || runQueue.length) {
        while (callQueue.length) {
            cid = callQueue.shift();
            if (allCalls[cid]) continue;
            callData = await pyview.get_call(cid);
            allCalls[cid] = callData;

            refs = [
                ...(callData.taskcall_arg_references       || []),
                ...(callData.taskcall_on_success_callbacks || []),
                ...(callData.taskcall_on_error_callbacks   || []),
                ...(callData.taskcall_before_run_hooks     || []),
                ...(callData.taskcall_after_run_hooks      || []),
            ];
            refs.forEach(id => { if (!allCalls[id]) callQueue.push(id); });
            if (callData.taskcall_result_run && !allRuns[callData.taskcall_result_run])
                runQueue.push(callData.taskcall_result_run);
            (callData.related_agent_task_runs || []).forEach(rid => {
                if (!allRuns[rid]) runQueue.push(rid);
            });
        }

        while (runQueue.length) {
            rid = runQueue.shift();
            if (allRuns[rid]) continue;
            runData = await pyview.get_run(rid);
            allRuns[rid] = runData;

            refs = [
                ...(runData.taskrun_arg_references    || []),
                ...(runData.taskrun_result_references || []),
                ...(runData.child_taskcalls|| []),
            ];
            refs.forEach(id => {
                if (id.startsWith('call:') && !allCalls[id]) callQueue.push(id);
                if (id.startsWith('run:')  && !allRuns[id])  runQueue.push(id);
            });
        }
        // outer loop repeats if draining runs pushed new calls onto callQueue
    }
    console.log("root:", root?.id, "children:", root?._children?.length);
_lanes.forEach(n => console.log(n.id, "children:", n._children.length));
    console.log("BFS done — calls:", Object.keys(allCalls).length, Object.keys(allCalls));
    console.log("BFS done — runs:", Object.keys(allRuns).length, Object.keys(allRuns));
    renderTrace({
      root_call_id: rootCallId,
      calls: Object.values(allCalls),
      runs:  Object.values(allRuns),
    });
 
  } catch (err) {
    showState('Error loading trace: ' + err.message);
    console.error(err);
  }
}
 
// Kick off load once pyview is ready.
window.__ROOT_CALL_ID__ = "call:{{pyview.root_call.pk if pyview.root_call else ''}}";
loadTrace();

</script>

    """

    def __init__(self, subject, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        instance = subject
        from server.models.tasks.agent_task_run import AgentTaskRun as _Run
        _child_ids = list(_Run.objects.filter(session_version__agent_instance=instance).values_list('child_taskcalls', flat=True)) \
            + list(_Run.objects.filter(session_version__agent_instance=instance).values_list('taskrun_result_references', flat=True))
        _child_ids = [x for x in _child_ids if x is not None]
        self.root_call = instance.agent_task_calls.order_by('created_at').last()

        super().__init__(subject, parent, **kwargs)

    def get_call(self, call_id:str):
        if isinstance(call_id, str):
            call_id = int(call_id.split(":")[-1])     
        call = AgentTaskCall.objects.get(pk=int(call_id))
        return {
            "id": f"call:{call.pk}",
            "agent": f"agent:{call.session.agent.pk}",
            "agent_instance": f"agent_instance:{call.session.pk}",
            "agent_task_definition": f"{call.task_definition_version.name}:{call.task_definition_version.pk}",
            "dont_start_before": int(call.dont_start_before.timestamp()) if call.dont_start_before else 0,
            "dont_start_after": int(call.dont_start_after.timestamp()) if call.dont_start_after else 0,
            "taskcall_arg_references":  [f"call:{call_pk}" for call_pk in call.taskcall_arg_references.values_list('pk', flat=True)],
            "taskcall_on_success_callbacks":  [f"call:{call_pk}" for call_pk in call.taskcall_on_success_callbacks.values_list('pk', flat=True)],
            "taskcall_on_error_callbacks":  [f"call:{call_pk}" for call_pk in call.taskcall_on_error_callbacks.values_list('pk', flat=True)],

            "taskcall_before_run_hooks":  [f"call:{call_pk}" for call_pk in call.taskcall_before_run_hooks.values_list('pk', flat=True)],
            "taskcall_after_run_hooks":  [f"call:{call_pk}" for call_pk in call.taskcall_after_run_hooks.values_list('pk', flat=True)],
            
            "taskcall_result_run":  f"run:{call.taskcall_result_run.pk}" if  call.taskcall_result_run else None, # the one final run that provides the result for this call 
            "related_agent_task_runs": [f"run:{call_pk}" for call_pk in call.related_agent_task_runs.values_list('pk', flat=True)],  # all run for this call
            "created_at": call.created_at.timestamp() if call.created_at else 0,
            "ended_at": call.updated_at.timestamp() if call.updated_at else 0, # use last updateed ts for now
        }

    def get_run(self, run_id:str):
        if isinstance(run_id, str):
            run_id = int(run_id.split(":")[-1])
        run = AgentTaskRun.objects.get(pk=int(run_id))
        return {
            "id": f"run:{run.pk}",
            "agent": f"agent:{run.session_version.agent.pk}",
            "agent_instance": f"agent_instance:{run.session_version.session.pk}",
            "agent_task_definition": f"{run.task_definition_version.name}:{run.task_definition_version.pk}",
            "agent_task_call": f"call:{run.agent_task_call.pk}",
            "dont_start_before": int(run.dont_start_before.timestamp()) if run.dont_start_before else 0,
            "dont_start_after": int(run.dont_start_after.timestamp()) if run.dont_start_after else 0,
            "taskrun_arg_references":  [f"run:{run_pk}" for run_pk in run.taskrun_arg_references.values_list('pk', flat=True)],
            "taskrun_result_references":  [f"call:{call_pk}" for call_pk in run.taskrun_result_references.values_list('pk', flat=True)],
            "child_taskcalls": [f"call:{call_pk}" for call_pk in run.child_taskcalls.values_list('pk', flat=True)],
            "created_at": run.created_at.timestamp() if run.created_at else 0,
            "ended_at": run.updated_at.timestamp() if run.updated_at else 0, # use last updateed ts for now

        }

