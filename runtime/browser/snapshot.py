"""Text-first page snapshots with stable element refs.

A snapshot is an outline of the *interactive* surface of the page plus its
heading structure, where every actionable element gets a short ref
(``[e12]``).  The ref is injected as a ``data-ao-ref`` attribute so a later
``click``/``type`` can address the element directly.

Refs are only stable until the page mutates: they are re-numbered on every
snapshot and ``page.evaluate`` rewrites them.  Always snapshot, then act.

Why text-first: the primary AgentOne model is local text-only (MLX), so the
default surface has to be cheap to consume.  Pixel output is available
separately via the ``screenshot`` action, which writes a PNG the existing
``read_image`` tool can turn into a vision request.
"""

from __future__ import annotations

from typing import Any

REF_ATTR = "data-ao-ref"

#: Cap on refs emitted per snapshot — keeps a pathological page from flooding
#: the context window. Overflow is reported so the model can narrow its view.
MAX_REFS = 400

_SNAPSHOT_JS = r"""
(refAttr) => {
  const MAX = __MAX__;
  for (const el of document.querySelectorAll('[' + refAttr + ']')) el.removeAttribute(refAttr);

  const SKIP = new Set(['SCRIPT','STYLE','NOSCRIPT','TEMPLATE','HEAD','META','LINK','TITLE','BR','PATH','SVG','IFRAME','CANVAS']);
  const roleOf = (el) => {
    const explicit = (el.getAttribute('role') || '').trim().toLowerCase();
    if (explicit) return explicit;
    const tag = el.tagName;
    if (tag === 'A') return el.hasAttribute('href') ? 'link' : '';
    if (tag === 'BUTTON') return 'button';
    if (tag === 'SELECT') return 'combobox';
    if (tag === 'TEXTAREA') return 'textbox';
    if (tag === 'SUMMARY') return 'button';
    if (tag === 'INPUT') {
      const t = (el.getAttribute('type') || 'text').toLowerCase();
      if (['checkbox','radio','switch'].includes(t)) return t;
      if (['button','submit','reset','image'].includes(t)) return 'button';
      if (['range','number'].includes(t)) return 'spinbutton';
      if (['file'].includes(t)) return 'file';
      return 'textbox';
    }
    if (tag === 'LABEL') return 'label';
    if (el.isContentEditable) return 'textbox';
    return '';
  };
  const INTERACTIVE = 'a[href],button,input,select,textarea,summary,label,[role=button],[role=link],'
    + '[role=checkbox],[role=radio],[role=switch],[role=tab],[role=menuitem],[role=textbox],'
    + '[role=combobox],[role=searchbox],[role=option],[contenteditable="" i],[contenteditable="true" i]';

  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    const st = window.getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || parseFloat(st.opacity) === 0) return false;
    return !el.closest('[aria-hidden="true"]');
  };
  const label = (el, role) => {
    const aria = (el.getAttribute('aria-label') || '').trim();
    if (aria) return aria.replace(/\s+/g, ' ').slice(0, 160);
    if (role === 'file') return (el.getAttribute('name') || 'file input');
    const img = el.querySelector ? el.querySelector('img[alt]:not([alt=""])') : null;
    if (img) return img.getAttribute('alt').replace(/\s+/g, ' ').slice(0, 160);
    const forId = el.getAttribute('for');
    if (forId) { const t = document.querySelector('label[for="' + CSS.escape(forId) + '"]'); if (t) return t.innerText.trim().slice(0,160); }
    const txt = (el.innerText || el.value || el.textContent || '').trim().replace(/\s+/g, ' ');
    if (role === 'textbox' && !txt && el.getAttribute('placeholder')) return el.getAttribute('placeholder').slice(0,160);
    return txt.slice(0, 160);
  };
  const states = (el, role) => {
    const s = [];
    if (el.disabled) s.push('disabled');
    if (role === 'checkbox' || role === 'radio' || role === 'switch') s.push(el.checked ? 'checked' : 'unchecked');
    if (role === 'textbox' && el.value) s.push('value=' + JSON.stringify(String(el.value).slice(0, 120)));
    if (el.getAttribute('aria-expanded')) s.push('expanded=' + el.getAttribute('aria-expanded'));
    if (el.readOnly) s.push('readonly');
    return s.length ? ' [' + s.join(' ') + ']' : '';
  };

  const lines = [];
  let n = 0, overflow = 0;
  const seen = new Set();

  for (const el of document.body.querySelectorAll('*')) {
    if (SKIP.has(el.tagName)) continue;
    if (el.closest('[aria-hidden="true"]')) continue;
    const tag = el.tagName;
    const heading = /^H[1-6]$/.test(tag) ? tag.toLowerCase() : '';
    const role = heading ? '' : roleOf(el);
    if (!heading && !role && tag !== 'LI' && tag !== 'P' && tag !== 'IMG') continue;
    if (!visible(el)) continue;
    // Only the innermost element for a role: a [role=button] wrapper containing
    // a <button> would otherwise produce two refs for one control.
    if (role && el.querySelector(INTERACTIVE) && !['label'].includes(role) && el.closest(INTERACTIVE) !== el) {
      if (el.closest(INTERACTIVE) && el.closest(INTERACTIVE).querySelector(INTERACTIVE)) continue;
    }

    if (heading) {
      const t = label(el, 'heading');
      if (t) lines.push('#'.repeat(Number(tag[1])) + ' ' + t);
      continue;
    }
    if (tag === 'IMG') {
      const alt = (el.getAttribute('alt') || '').trim();
      if (alt) lines.push('img "' + alt.replace(/\s+/g,' ').slice(0,120) + '"');
      continue;
    }
    if (tag === 'P' || tag === 'LI') {
      if (role) { /* fall through to ref emission */ } else { continue; }
    }

    if (role === 'link') {
      const inner = el.querySelector(INTERACTIVE);
      if (inner && inner !== el) continue; // let the inner control own the ref
    }

    if (n >= MAX) { overflow += 1; continue; }
    const ref = 'e' + (++n);
    el.setAttribute(refAttr, ref);
    seen.add(ref);
    let text = role + ' "' + label(el, role) + '"';
    if (role === 'link') {
      const href = el.getAttribute('href') || '';
      if (href && href !== '#') text += ' -> ' + href.slice(0, 200);
    }
    text += states(el, role);
    lines.push('[' + ref + '] ' + text);
  }
  return { title: document.title || '', url: location.href, lines, overflow, refs: n };
}
"""


def _js() -> str:
    return _SNAPSHOT_JS.replace("__MAX__", str(MAX_REFS))


def snapshot(page: Any) -> dict:
    """Return a text snapshot of *page*."""
    data = page.evaluate(_js(), REF_ATTR)  # type: ignore[arg-type]
    title = (data.get("title") or "").strip()
    url = data.get("url") or ""
    lines = data.get("lines") or []
    header = f"Page: {title or '(untitled)'}\nURL: {url}"
    if data.get("overflow"):
        header += f"\n(refs capped at {MAX_REFS}; {data['overflow']} more interactive elements omitted)"
    body = "\n".join(lines) if lines else "(no interactive elements found)"
    return {
        "title": title,
        "url": url,
        "snapshot": f"{header}\n\n{body}",
        "refs": data.get("refs", 0),
    }


def _ref_selector(ref: str) -> str:
    """Build a CSS selector for an injected ref, rejecting anything odd."""
    cleaned = str(ref or "").strip().lstrip("@")
    if not cleaned.startswith("e") or not cleaned[1:].isdigit():
        raise ValueError(f"invalid element ref: {ref!r}")
    return f'[{REF_ATTR}="{cleaned}"]'


def resolve_ref(ref: str) -> str:
    """Resolve an injected *ref* (e.g. ``"e12"``) to a CSS selector."""
    return _ref_selector(ref)


def clear_refs(page: Any) -> None:
    """Drop all injected refs (called after a navigation)."""
    try:
        page.evaluate(
            "(attr) => { for (const el of document.querySelectorAll('[' + attr + ']')) el.removeAttribute(attr); }",
            REF_ATTR,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        pass


def read_text(page: Any, *, max_chars: int = 20000, selector: str | None = None) -> str:
    """Extract readable text from *page* (main content preferred)."""
    js = r"""
    (sel) => {
      const pick = sel ? document.querySelector(sel) : null;
      const root = pick || document.querySelector('main, article, [role=main]') || document.body;
      if (!root) return '';
      const clone = root.cloneNode(true);
      for (const el of clone.querySelectorAll('script,style,noscript,svg,template')) el.remove();
      return clone.innerText || clone.textContent || '';
    }
    """
    try:
        text = page.evaluate(js, selector) or ""
    except Exception:  # pylint: disable=broad-exception-caught
        text = ""
    text = text.strip()
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]
    return text + ("\n…[truncated]" if truncated else "") if text else "(no readable text)"
