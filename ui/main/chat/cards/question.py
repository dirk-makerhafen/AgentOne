"""
User-question card for the ``ask_user`` tool.

Shown when an ``ask_user`` tool call is parked at ``HALTED_APPROVAL`` by the
scheduler question gate. Renders each question with its discrete options as
clickable buttons (single-select), checkboxes + submit (multi-select), and a
free-text "Other" input. Answers are recorded via
``CallScheduler.answer_question_call``; once every question is answered the
call is approved and the agent resumes with the answers. Declining reuses
the approval-denial path ("proceed with best judgment").
"""
from __future__ import annotations
import json
from typing import TYPE_CHECKING, Any
from server.models.enums.task_enums import TaskCallStatusDetail
from server.models.tasks.agent_task_call import AgentTaskCall
from runtime.user_questions import (
    ASK_USER_TOOL_NAME,
    normalize_questions,
)
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from runtime.session.session import Session


class QuestionCard(PyHtmlView):
    DOM_ELEMENT_EXTRAS = 'role="dialog" aria-labelledby="questionHeading" aria-describedby="questionDesc"'
    TEMPLATE_STR = '''
        <div class="question-inner" style="{% if not pyview.pending_items %}display:none{% endif %}">
            <div class="question-header">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                <span id="questionHeading">Questions for you</span>
            </div>
            <div class="question-desc" id="questionDesc">
                The agent needs your input before it can continue:
            </div>
            {% for item in pyview.pending_items %}
            <div class="question-block">
                {% if item.header %}
                <div class="question-tag">{{ item.header }}</div>
                {% endif %}
                <div class="question-text">{{ item.question }}</div>
                {% if item.answered %}
                <div class="question-answered">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                    {{ item.answer_text }}
                </div>
                {% elif item.multiSelect %}
                <div class="question-options">
                    {% for opt in item.options %}
                    <label class="question-check">
                        <input type="checkbox" data-q="{{ item.call_pk }}-{{ item.qidx }}" value="{{ opt.oidx }}">
                        <span class="question-opt-label">{{ opt.label }}</span>
                        {% if opt.description %}
                        <span class="question-opt-desc">{{ opt.description }}</span>
                        {% endif %}
                    </label>
                    {% endfor %}
                </div>
                <div class="question-other">
                    <input class="question-other-input" id="question_other_{{ item.call_pk }}_{{ item.qidx }}" type="text" placeholder="Other (free text, optional)" autocomplete="off" spellcheck="false">
                </div>
                <div class="question-block-btns">
                    <button class="question-btn submit" onclick="pyview.submit_multiple({{ item.call_pk }}, {{ item.qidx }}, JSON.stringify(Array.from(document.querySelectorAll('input[data-q=&quot;{{ item.call_pk }}-{{ item.qidx }}&quot;]:checked')).map(e=>e.value)), document.getElementById('question_other_{{ item.call_pk }}_{{ item.qidx }}').value)">
                        Submit
                    </button>
                </div>
                {% else %}
                <div class="question-options">
                    {% for opt in item.options %}
                    <button class="question-row" onclick="pyview.submit_option({{ item.call_pk }}, {{ item.qidx }}, {{ opt.oidx }})">
                        <span class="question-opt-label">{{ opt.label }}</span>
                        {% if opt.description %}
                        <span class="question-opt-desc">{{ opt.description }}</span>
                        {% endif %}
                    </button>
                    {% endfor %}
                </div>
                <div class="question-other">
                    <input class="question-other-input" id="question_other_{{ item.call_pk }}_{{ item.qidx }}" type="text" placeholder="Other (free text)" autocomplete="off" spellcheck="false">
                    <button class="question-btn submit" onclick="pyview.submit_text({{ item.call_pk }}, {{ item.qidx }}, document.getElementById('question_other_{{ item.call_pk }}_{{ item.qidx }}').value)">Send</button>
                </div>
                {% endif %}
            </div>
            {% endfor %}
            {% for call_pk in pyview.pending_call_pks %}
            <div class="question-call-btns">
                <input class="question-decline-input" id="question_decline_{{ call_pk }}" type="text" placeholder="Why decline? (optional)" autocomplete="off" spellcheck="false">
                <button class="question-btn decline" onclick="pyview.decline({{ call_pk }}, document.getElementById('question_decline_{{ call_pk }}').value)">
                    Decline — use your best judgment
                </button>
            </div>
            {% endfor %}
        </div>
    '''

    @property
    def DOM_ELEMENT_CLASS(self):
        return 'question-card' + ' visible' if self.pending_items else ""

    def __init__(self, subject: Session, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._session_id = subject.model.pk
        try:
            from ui.lib.model_view import orm_subscribe

            orm_subscribe(
                self,
                f"AgentTaskCall.session:{self._session_id}",
                self._on_orm_event,
            )
        except Exception:
            pass

    @property
    def pending_calls(self) -> list[AgentTaskCall]:
        session = self.subject
        if session is None:
            return []
        return list(AgentTaskCall.objects.filter(
            session=session.model,
            status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
            task_definition__name=ASK_USER_TOOL_NAME,
        ).select_related('task_definition_version__task_definition')[:3])

    @property
    def pending_call_pks(self) -> list[int]:
        return [c.pk for c in self.pending_calls]

    @property
    def pending_items(self) -> list[dict[str, Any]]:
        """Flattened question list for the template (ints only in handlers)."""
        items: list[dict[str, Any]] = []
        for call in self.pending_calls:
            args = call.carguments_json or {}
            answers = args.get("answers") or {}
            for qidx, q in enumerate(normalize_questions(args.get("questions"))):
                raw = answers.get(q["question"])
                if isinstance(raw, list):
                    answer_text = ", ".join(str(v) for v in raw)
                elif raw:
                    answer_text = str(raw)
                else:
                    answer_text = ""
                items.append({
                    "call_pk": call.pk,
                    "qidx": qidx,
                    "header": q["header"],
                    "question": q["question"],
                    "multiSelect": q["multiSelect"],
                    "options": [
                        {"oidx": oidx, "label": o["label"],
                         "description": o["description"]}
                        for oidx, o in enumerate(q["options"])
                    ],
                    "answered": bool(answer_text),
                    "answer_text": answer_text,
                })
        return items

    def _call_or_none(self, pk: int) -> AgentTaskCall | None:
        return AgentTaskCall.objects.filter(
            pk=pk,
            status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
            task_definition__name=ASK_USER_TOOL_NAME,
        ).first()

    def _question_text(self, call: AgentTaskCall, qidx: int) -> str | None:
        questions = normalize_questions((call.carguments_json or {}).get("questions"))
        if 0 <= qidx < len(questions):
            return questions[qidx]["question"]
        return None

    def _answer(self, pk: int, qidx: int, value: Any) -> None:
        from runtime.tasks.call_scheduler import CallScheduler
        call = self._call_or_none(pk)
        if call is None:
            return
        question = self._question_text(call, qidx)
        if question is None:
            return
        CallScheduler.answer_question_call(call.pk, {question: value})
        self.update()

    def submit_option(self, pk: int, qidx: int, oidx: int) -> None:
        """Record a single-select option click (indices → label server-side)."""
        call = self._call_or_none(pk)
        if call is None:
            return
        questions = normalize_questions((call.carguments_json or {}).get("questions"))
        if not (0 <= qidx < len(questions)):
            return
        options = questions[qidx]["options"]
        if not (0 <= oidx < len(options)):
            return
        self._answer(pk, qidx, options[oidx]["label"])

    def submit_multiple(self, pk: int, qidx: int, oidx_json: str, other: str = "") -> None:
        """Record multi-select checkboxes (JSON array of option indices)."""
        try:
            raw = json.loads(oidx_json) if oidx_json else []
        except (ValueError, TypeError):
            raw = []
        call = self._call_or_none(pk)
        if call is None:
            return
        questions = normalize_questions((call.carguments_json or {}).get("questions"))
        if not (0 <= qidx < len(questions)):
            return
        options = questions[qidx]["options"]
        labels = []
        for entry in raw if isinstance(raw, list) else []:
            try:
                oidx = int(entry)
            except (ValueError, TypeError):
                continue
            if 0 <= oidx < len(options):
                labels.append(options[oidx]["label"])
        other = (other or "").strip()
        if other:
            labels.append(other)
        if not labels:
            return
        self._answer(pk, qidx, labels)

    def submit_text(self, pk: int, qidx: int, text: str = "") -> None:
        """Record a free-text ("Other") answer."""
        text = (text or "").strip()
        if not text:
            return
        self._answer(pk, qidx, text)

    def decline(self, pk: int, feedback: str = "") -> None:
        """Decline answering — the agent proceeds with its best judgment."""
        from runtime.tasks.call_scheduler import CallScheduler
        call = self._call_or_none(pk)
        if call:
            CallScheduler.deny_taskcall(call.pk, feedback=feedback)
        self.update()

    def _on_orm_event(self, key=None, model=None, pk=None, action=None, data=None) -> None:
        """Redis observable callback: a session task call changed, re-render."""
        if model == "AgentTaskCall" and action == "update":
            self.update()
