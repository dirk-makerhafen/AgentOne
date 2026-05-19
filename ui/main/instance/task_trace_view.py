from __future__ import annotations
from collections import defaultdict, deque
import copy
import pprint
import json
import unicodedata

from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui import PyHtmlView
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from ui.lib.model_view import ModelView
from ui.lib.multi_queryset_view import MultiQuerySetView

class TaskTraceView(ModelView):
    DOM_ELEMENT_CLASS = "TaskTraceView resizable-container"
    DOM_ELEMENT_EXTRAS = 'data-orientation="horizontal" style="height: 600px; overflow: scroll;"'
    
    TEMPLATE_STR = """
    <div id="graph-root" style="display:flex">
    <canvas id="graph-lines"></canvas>

    </div>
<style>
    #graph-lines {
        position: absolute;
        top: 0;
        left: 0;
        pointer-events: none;
        z-index: 10;
    }

   #graph-root {
        position: relative;   
        display: flex;
        flex-direction: row;
        gap: 8px;
        padding: 10px;
  
}
.call, .run {
    display: grid;
    grid-template-rows: auto 1fr;
    border-radius: 3px;
    padding: 0px 5px 5px 5px;
    border: 1px solid #2a3140;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    position: relative;
    height: fit-content;
}
.call-header {
    
    color: #7dd3fc;
    margin-bottom: 1px;
    display: flex;
    flex-direction:row;
    justify-content: space-between;
}
.call-title {
    padding-left: 5px;
    padding-right: 5px;
    text-align: center;
}
.run-header {
   
    color: #86efac;
    margin-bottom: 1px;
    display: flex;
    flex-direction:row;
    justify-content: space-between;
}
.before-run-hooks {
    flex-direction: row;
    display: flex;
}
.after-run-hooks {
    flex-direction: row;
    display: flex;
}
.call-body, .run-body {
    display: flex;
    flex-direction: row;
    gap: 8px;
}
.call-inputs,
.run-inputs {
    display: flex;
    justify-content: flex-start;
    flex-direction: column;
}

.call-outputs,
.run-outputs {
    display: flex;
    justify-content: flex-start;
    flex-direction: column;
}
.runs-container,
.run-subcalls {
    display: flex;
    align-items: flex-start;
    margin-left: 5px;
    margin-right: 5px;
}
.call .call,
.run .run {
    
    height:fit-content;
  
}
.runs {
        width: -webkit-fill-available;
}
.unloaded-ref {
    padding: 4px 8px;
    border-radius: 2px;
    background: #2a3140;
    color: #9ca3af;
    font-size: 11px;
    white-space: nowrap;
}
.anchor-point {
    display: flex;
    flex-direction:column;
    gap: 1px;
}

.point {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: #64748b;
    position: relative;
}

#graph-root::before {
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-image: linear-gradient(
        to right,
        rgba(255,255,255,0.03) 1px,
        transparent 1px
    );
    background-size: 80px 100%;
    pointer-events: none;
}



</style>
<script>
canvas = document.getElementById('graph-lines');
ctx = canvas.getContext('2d');

renderCall = (callData) => {
    container = document.createElement('div');
    container.className = 'call';
    container.id = callData.id;
    container.dataset.order_prev = [ ...callData.rev_taskcall_on_success_callbacks, ...callData.rev_taskcall_on_error_callbacks,     ...callData.taskcall_arg_references]
    container.dataset.order_next = [     ...callData.taskcall_on_success_callbacks,     ...callData.taskcall_on_error_callbacks, ...callData.rev_taskcall_arg_references]
    
    container.innerHTML = `
        <div class="call-header">
            <div class="call-inputs" >
                <!-- Spawned By: Incoming flow from parent/previous logic -->
                <div class="spawned-by anchor-point" >
                    <div id="${callData.id}_on_success_destination" class="point" data-reftype="call" data-pointtype="destination" data-remotepostfix="_on_success_source" data-refname="rev_taskcall_on_success_callbacks" data-refs="${[...callData.rev_taskcall_on_success_callbacks].join(',')}"></div>
                    <div id="${callData.id}_on_error_destination"   class="point" data-reftype="call" data-pointtype="destination" data-remote_postfix="_on_error_source" data-refname="rev_taskcall_on_error_callbacks"   data-refs="${[ ...callData.rev_taskcall_on_error_callbacks].join(',')}"></div>
                    <div id="${callData.id}_subrun_destination"     class="point" data-reftype="run"  data-pointtype="destination" data-remote_postfix="_subrun_source" data-refname="parent_taskruns"    data-refs="${[ ...callData.parent_taskruns].join(',')}"></div>
                </div>
                
                <!-- Args: References to results of previous calls -->
                <div class="args anchor-point">
                    <div id="${callData.id}_args_destination" class="point" data-reftype="call" data-pointtype="destination" data-remote_postfix="_args_source" data-refname="taskcall_arg_references"  data-refs="${callData.taskcall_arg_references.join(',')}"> </div>
                </div>
            </div>
            <div class="call-title">
                <div>${callData.agent_name}</div>
                <div>${callData.agent_task_definition_name}</div>
            </div>
            <div class="call-outputs">
                <div class="on_error anchor-point">
                    <div id="${callData.id}_on_error_source" class="point" data-reftype="call" data-remote_postfix="_on_error_destination" data-pointtype="source" data-refname="taskcall_on_error_callbacks"  data-refs="${callData.taskcall_on_error_callbacks.join(',')}"> </div>
                </div>
                <div class="on_success anchor-point">
                    <div id="${callData.id}_on_success_source" class="point" data-reftype="call" data-remote_postfix="_on_success_destination" data-pointtype="source" data-refname="taskcall_on_success_callbacks"  data-refs="${callData.taskcall_on_success_callbacks.join(',')}"> </div>
                </div>
                <div class="call-result anchor-point">
                    <div id="${callData.id}_args_source" class="point" data-reftype="call" data-pointtype="source" data-remote_postfix="_args_destination" data-refname="rev_taskcall_arg_references"  data-refs="${callData.rev_taskcall_arg_references.join(',')}"> </div>
                    <div id="${callData.id}_result_source" class="point" data-reftype="run" data-pointtype="source" data-remote_postfix="_result_destination" data-refname="rev_taskrun_result_references"  data-refs="${callData.rev_taskrun_result_references.join(',')}"> </div>
                    <div id="${callData.id}_resultrun_destination" class="point" data-reftype="run" data-pointtype="destination" data-remote_postfix="_subrun_source" data-refname="taskcall_result_run"  data-ref="${callData.taskcall_result_run}"> </div>
                </div>
            </div>
        </div>
        <div class="runs-container" >
            <!-- Before-Run Hooks -->
            <div class="before-run-hooks">
                ${callData.taskcall_before_run_hooks.map(callId => `<div class="unloaded-ref" data-id="${callId}">${callId}</div>`).join('')}
            </div>

            <!-- Related Runs -->
            <div class="runs">
                ${callData.related_agent_task_runs.map(runId => `<div  class="unloaded-ref" data-id="${runId}">${runId}</div>`).join('')}
            </div>

            <!-- After-Run Hooks -->
            <div class="after-run-hooks">
                ${callData.taskcall_after_run_hooks.map(callId => `<div class="unloaded-ref" class="hook-ref" data-id="${callId}">${callId}</div>`).join('')}
            </div>
        </div>
    `;
    return container;
    
};

renderRun = (runData) => {
    container = document.createElement('div');
    container.className = 'run';
    container.id = runData.id;
    container.dataset.order_prev = [...runData.taskrun_arg_references]
    container.dataset.order_next = [...runData.rev_taskrun_arg_references, ...runData.spawned_calls]
    
    container.innerHTML = `
        <div class="run-header">
            <div class="run-inputs">
                <div class="run-args anchor-point">
                    <div id="${runData.id}_args_destination" class="point" data-reftype="run" data-pointtype="destination" data-remote_postfix="_args_source" data-refname="taskrun_arg_references" data-refs="${[...runData.taskrun_arg_references].join(',')}"><!--- other runs referenced in our arguments ---> </div>
                </div>
            </div>     
            <div class="run-title">${runData.id}</div>
            <div class="run-outputs">
                <div class="run-result anchor-point">
                    <div id="${runData.id}_args_source"  class="point" data-reftype="run" data-pointtype="source" data-remote_postfix="_args_destination" data-refname="rev_taskrun_arg_references" data-refs="${[...runData.rev_taskrun_arg_references].join(',')}"><!---  we are referenced in these runs arguments ---></div>
                    <div id="${runData.id}_result_destination"  class="point" data-reftype="call" data-pointtype="destination" data-remote_postfix="_result_source" data-refname="taskrun_result_references" data-refs="${[...runData.taskrun_result_references].join(',')}"><!--  # our result references these calls--> </div>
                    <div id="${runData.id}_resultrun_source" class="point" data-reftype="call" data-pointtype="source" data-remote_postfix="_result_destination" data-refname="rev_taskcall_result_run" data-refs="${[...runData.rev_taskcall_result_run].join(',')}"><!--- we are the final result of these calls  ---></div>
                </div>
                <div class="spawns anchor-point">
                    <div id="${runData.id}_subrun_source" class="point" data-reftype="call" data-pointtype="source" data-remote_postfix="_subrun_destination" data-refname="spawned_calls" data-ref="${runData.spawned_calls}"><!--- detached spawned ---></div>
                </div>

            </div>
        </div>
        <div class="run-subcalls">
            ${runData.child_taskcalls.map(callId => `<div class="unloaded-ref" data-id="${callId}">${callId}</div>`).join('')}  
        </div>
    `;

    return container;
};


sort_container = (container) => {
 
        const items =  Array.from(container.children).filter(el => (el.matches('.call') || el.matches('.run')));
        
        //const items =  [...Array.from(container.querySelectorAll('.call')), ...Array.from(container.querySelectorAll('.run'))] ;
        const idMap = new Map(items.map(el => [el.id, el]));
        console.log(items);
        const adj = new Map();      // Graph edges
        const inDegree = new Map(); // Count of incoming dependencies

        // 1. Build the graph
        items.forEach(el => {
            const id = el.id;
            if (!inDegree.has(id)) inDegree.set(id, 0);

            const prevs = el.dataset.order_prev?.split(',').filter(Boolean) || [];
            const nexts = el.dataset.order_next?.split(',').filter(Boolean) || [];

            // Relationship: prev -> current
            prevs.forEach(pId => {
                if (!adj.has(pId)) adj.set(pId, []);
                adj.get(pId).push(id);
                inDegree.set(id, (inDegree.get(id) || 0) + 1);
            });

            // Relationship: current -> next
            nexts.forEach(nId => {
                if (!adj.has(id)) adj.set(id, []);
                adj.get(id).push(nId);
                inDegree.set(nId, (inDegree.get(nId) || 0) + 1);
            });
           
        });

        // 2. Sort (Kahn's)
        const queue = [...inDegree.keys()].filter(id => inDegree.get(id) === 0);
        const sorted = [];

        while (queue.length) {
            const u = queue.shift();
            sorted.push(idMap.get(u));
            
            (adj.get(u) || []).forEach(v => {
                inDegree.set(v, inDegree.get(v) - 1);
                if (inDegree.get(v) === 0) queue.push(v);
            });
        }

        // 3. Re-append to DOM in order
        //container.replaceChildren(...sorted.filter(Boolean));
        c = container.children;
        container.append(...sorted.filter(Boolean));
}


update_graph = (container) => {
    container.querySelectorAll('.unloaded-ref').forEach(el => {
        const id = el.dataset.id;
        const existing = document.getElementById(id);
        if (existing) {
            existing.remove();              // detach from old position
            el.replaceWith(existing);       // move into new position
        }
    });

    const existingContainer = document.getElementById(container.id);
    const target = document.querySelector(`.unloaded-ref[data-id="${container.id}"]`);

    if (existingContainer && !target) {
        existingContainer.replaceWith(container);
    }else{
        if (target) {
            if (existingContainer) {
                existingContainer.remove();
            }
            target.replaceWith(container);
            
        }else{
            document.getElementById('graph-root').appendChild(container);
        }
        
    }
    x = document.getElementById(container.id);
    sort_container(x.parentNode);
    refreshConnections();
}

load_data = (root_id) => {
    pyview.resolve(root_id).then(
        function(datas){
            for (let key of Object.keys(datas)) {
                if(key.startsWith("call_") ){
                    container = renderCall(datas[key]);
                }else{
                    container = renderRun(datas[key]);
                }
                update_graph(container);
            }  
        }
    )
};
{% for root_call in pyview.root_calls %}
    load_data("call_{{root_call.pk}}");
{% endfor %}



function getCenter(el) {
    const rect = el.getBoundingClientRect();
    const rootRect = root.getBoundingClientRect();

    return {
        x: rect.left - rootRect.left + root.scrollLeft + rect.width / 2,
        y: rect.top  - rootRect.top  + root.scrollTop  + rect.height / 2
    };
}

function drawLine(from, to, type = "default") {
    const dx = Math.abs(to.x - from.x) * 0.5;

    ctx.beginPath();
    ctx.moveTo(from.x, from.y);

    ctx.bezierCurveTo(
        from.x + dx, from.y,
        to.x - dx, to.y,
        to.x, to.y
    );

    if (type === "run") {
        ctx.strokeStyle = 'rgba(100,255,150,0.5)';
    } else {
        ctx.strokeStyle = 'rgba(100,150,255,0.5)';
    }

    ctx.lineWidth = 2;
    ctx.stroke();
}
function getTargets(point) {
    let ids = [];
    if (point.dataset.refs) {
        ids = point.dataset.refs.split(',').filter(Boolean);
    }
    if (point.dataset.ref) {
        ids.push(point.dataset.ref);
    }
    return ids.map(id => document.getElementById(`${id}${point.dataset.remote_postfix}` )).filter(Boolean);
}

function drawAllConnections() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const points = document.querySelectorAll(`.point[data-pointtype="source"]`);

    points.forEach(point => {
        const from = getCenter(point);
        const targets = getTargets(point);

        targets.forEach(target => {
            const to = getCenter(target);
            drawLine(from, to);
        });
    });
}
function refreshConnections() {
    resizeCanvas();
    requestAnimationFrame(drawAllConnections);
}

root = document.getElementById('graph-root');

function resizeCanvas() {
    rect = root.getBoundingClientRect();
    canvas.width = root.scrollWidth;
    canvas.height = root.scrollHeight;
}

root.addEventListener('scroll', refreshConnections);
window.addEventListener('resize', refreshConnections);
resizeCanvas();

</script>
"""


    def __init__(self, subject, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        super().__init__(subject, parent, **kwargs)

        from server.models.tasks.agent_task_run import AgentTaskRun as _Run
        self.root_calls = [] #subject.agent_task_calls.order_by('-created_at')[0:10]

    def resolve(self, root_call_id, max_depth=50, max_forward_steps=50, max_backward_steps=50, cache=None):
        if not cache:
            cache = {}
        
        is_call = root_call_id.startswith("call_")
        if root_call_id in cache:
            item_obj = cache[root_call_id]
            item_obj["hit_cnt"] += 1
        else:     
            if root_call_id.startswith("call_"):
                item_obj = self.get_call(call_id=root_call_id)
            else:
                item_obj = self.get_run(run_id=root_call_id)
            item_obj["hit_cnt"] = 0
            cache[root_call_id] = item_obj

        #if item_obj["hit_cnt"] >= 5:
        #    return cache
        
        if max_depth > 0:
            if is_call:
                keys = ["taskcall_before_run_hooks", "taskcall_after_run_hooks", "rev_taskcall_before_run_hooks", "rev_taskcall_after_run_hooks", "taskcall_result_run", "related_agent_task_runs"]
            else:
                keys = ["child_taskcalls"]
            for key in keys:
                #print(key, item_obj[key], isinstance(item_obj[key], list) )
                for sub_id in (item_obj[key] if isinstance(item_obj[key], list) else [item_obj[key],]):
                    if sub_id is None:
                        continue
                    if cache.get(sub_id,{}).get("hit_cnt", 0) <= 5:
                        self.resolve(sub_id, max_depth=max_depth-1,  max_forward_steps=max_forward_steps, max_backward_steps=max_backward_steps, cache=cache)
            
        if  max_forward_steps > 0:
            if is_call:
                keys = ["rev_taskcall_arg_references", "taskcall_on_success_callbacks", "taskcall_on_error_callbacks", "rev_taskrun_result_references"]
            else:
                keys = ["rev_taskrun_arg_references"]
            for key in keys:
                for sub_id in (item_obj[key] if isinstance(item_obj[key], list) else [item_obj[key]]):
                    if sub_id is None:
                        continue
                    #print("SUBID2", sub_id)
                    if cache.get(sub_id,{}).get("hit_cnt", 0) <= 5:
                        self.resolve(sub_id, max_depth=max_depth,  max_forward_steps=max_forward_steps-1, max_backward_steps=max_backward_steps, cache=cache)

        if  max_backward_steps > 0:
            if is_call:
                keys =  ["taskcall_arg_references", "rev_taskcall_on_success_callbacks", "rev_taskcall_on_error_callbacks","parent_taskruns" ]
            else:
                keys = ["taskrun_arg_references", "taskrun_result_references", "agent_task_call", "rev_taskcall_result_run"]
            for key in keys :
                for sub_id in (item_obj[key] if isinstance(item_obj[key], list) else [item_obj[key]]):
                    if sub_id is None:
                        continue
                    if cache.get(sub_id,{}).get("hit_cnt", 0) <= 5:
                        self.resolve(sub_id, max_depth=max_depth,  max_forward_steps=max_forward_steps, max_backward_steps=max_backward_steps-1, cache=cache)

        return cache

    def get_call(self, call_id:str):
        if isinstance(call_id, str):
            call_id = int(call_id.split("_")[-1])     
        call = AgentTaskCall.objects.get(pk=int(call_id))
        print("GET_CALL", call)
        return {
            "id": f"call_{call.pk}",
            "agent":                 f"agent:{call.session.agent.pk}",
            "agent_name":            f"{call.session.agent.name}",
            "agent_instance":        f"agent_instance:{call.session.pk}",
            "agent_task_definition": f"{call.task_definition_version.pk if hasattr(call,"agent_task_definition") else ''}",
            "agent_task_definition_name": f"{call.task_definition_version.name}",

            "dont_start_before": int(call.dont_start_before.timestamp()) if call.dont_start_before else 0,
            "dont_start_after":  int(call.dont_start_after.timestamp())  if call.dont_start_after  else 0,
            
            "taskcall_arg_references":     [f"call_{call_pk}" for call_pk in call.taskcall_arg_references.values_list('pk', flat=True)], # calls that are referenced in our args
            "rev_taskcall_arg_references": [f"call_{call_pk}" for call_pk in call.rev_taskcall_arg_references.values_list('pk', flat=True)], # we are referenced in these call args
            
            "taskcall_on_success_callbacks":     [f"call_{call_pk}" for call_pk in call.taskcall_on_success_callbacks.values_list('pk', flat=True)], # these run as a result of our sucess
            "rev_taskcall_on_success_callbacks": [f"call_{call_pk}" for call_pk in call.rev_taskcall_on_success_callbacks.values_list('pk', flat=True)], # we run because these were successfull
            
            "taskcall_on_error_callbacks":    [f"call_{call_pk}" for call_pk in call.taskcall_on_error_callbacks.values_list('pk', flat=True)], # these run as a result of our error
            "rev_taskcall_on_error_callbacks":[f"call_{call_pk}" for call_pk in call.rev_taskcall_on_error_callbacks.values_list('pk', flat=True)], # we run because these failed

            "taskcall_before_run_hooks":      [f"call_{call_pk}" for call_pk in call.taskcall_before_run_hooks.values_list('pk', flat=True)], # these hooks run before our first run is started
            "rev_taskcall_before_run_hooks":  [f"call_{call_pk}" for call_pk in call.rev_taskcall_before_run_hooks.values_list('pk', flat=True)], # we are the hook 

            "taskcall_after_run_hooks":       [f"call_{call_pk}" for call_pk in call.taskcall_after_run_hooks.values_list('pk', flat=True)], # these hooks run after our final run ended
            "rev_taskcall_after_run_hooks":   [f"call_{call_pk}" for call_pk in call.rev_taskcall_after_run_hooks.values_list('pk', flat=True)], # we are the hook

            "rev_taskrun_result_references":  [f"run_{call_pk}" for call_pk in call.rev_taskrun_result_references.values_list('pk', flat=True)],  # we are referenced in the results of these run
            "parent_taskruns": [f"run_{call_pk}" for call_pk in call.parent_taskruns.values_list('pk', flat=True)], # we were created as a result of these runs

            "taskcall_result_run":      f"run_{call.taskcall_result_run.pk}" if  call.taskcall_result_run else None, # the one final run that provides the result for this call 
            "related_agent_task_runs": [f"run_{call_pk}" for call_pk in call.related_agent_task_runs.values_list('pk', flat=True)],  # all run for this call
            
            "created_at": call.created_at.timestamp() if call.created_at else 0,
            "ended_at": call.updated_at.timestamp() if call.updated_at else 0, # use last updateed ts for now
        }

    def get_run(self, run_id:str):
        print("GET_RUN", run_id)
        if isinstance(run_id, str):
            run_id = int(run_id.split("_")[-1])
        run = AgentTaskRun.objects.get(pk=int(run_id))
        print("GET_RUN", run)
        taskrun_result_references  = [f"call_{call_pk}" for call_pk in run.taskrun_result_references.values_list('pk', flat=True)] # our result references these calls
        child_taskcalls = [f"call_{call_pk}" for call_pk in run.child_taskcalls.values_list('pk', flat=True)] # all calls there were created inside of this run
        sub_calls = [x for x in child_taskcalls if x not in taskrun_result_references]
        spawned_calls = [x for x in child_taskcalls if x in taskrun_result_references]
        
        return {
            "id":                    f"run_{run.pk}",
            "agent":                 f"agent:{run.session_version.agent.pk}",
            "agent_instance":        f"agent_instance:{run.session_version.session.pk}",
            "agent_task_call":       f"call_{run.agent_task_call.pk}",
            "agent_task_definition": f"{run.task_definition_version.name}:{run.task_definition_version.pk}",
            "dont_start_before":     int(run.dont_start_before.timestamp()) if run.dont_start_before else 0,
            "dont_start_after":      int(run.dont_start_after.timestamp()) if run.dont_start_after else 0,
            "taskrun_arg_references":     [f"run_{run_pk}"   for run_pk  in run.taskrun_arg_references.values_list('pk', flat=True)], # other runs referenced in our arguments
            "rev_taskrun_arg_references": [f"run_{run_pk}"   for run_pk  in run.rev_taskrun_arg_references.values_list('pk', flat=True)], # we are referenced in these runs arguments
            
            "taskrun_result_references":  taskrun_result_references, # our result references these calls
            "child_taskcalls": child_taskcalls, # all calls there were created inside of this run
            "spawned_calls": spawned_calls,
            "sub_calls": sub_calls,

            "rev_taskcall_result_run":    [f"call_{call_pk}" for call_pk in run.rev_taskcall_result_run.values_list('pk', flat=True)],# we are the final result of these calls

            "created_at": run.created_at.timestamp() if run.created_at else 0,
            "ended_at": run.updated_at.timestamp() if run.updated_at else 0, # use last updateed ts for now
        }
