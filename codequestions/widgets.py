# codequestions/widgets.py
from __future__ import annotations
from django.forms.widgets import Widget
from django.utils.safestring import mark_safe
import json
import html

class StandardIoTestsWidget(Widget):
    """
    Renders a table-based editor for standardIo tests (name, stdin, stdout)
    and stores the value as JSON in a hidden input.
    """
    template_name = None  # we render inline HTML

    def render(self, name, value, attrs=None, renderer=None):
        tests = []
        if value:
            try:
                tests = json.loads(value)
                if not isinstance(tests, list):
                    tests = []
            except Exception:
                tests = []
        # ensure at least one row
        if not tests:
            tests = [{"name": "case1", "stdin": "", "stdout": ""}]

        # escape into data attribute
        data_json = html.escape(json.dumps(tests), quote=True)
        input_id = attrs.get("id", f"id_{name}") if attrs else f"id_{name}"

        html_out = f"""
<div class="stdio-tests-editor">
  <input type="hidden" name="{name}" id="{input_id}" value='{data_json}' />

  <div class="card bg-base-200" style="padding:1rem;">
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-lg font-semibold">Standard IO Tests</h3>
      <div class="join">
        <button type="button" class="btn btn-sm join-item" data-action="add-row">+ Add</button>
        <button type="button" class="btn btn-sm btn-error join-item" data-action="clear-all">Clear</button>
      </div>
    </div>

    <div class="overflow-x-auto">
      <table class="table table-zebra w-full">
        <thead>
          <tr>
            <th style="width: 14rem;">Name</th>
            <th>stdin</th>
            <th>stdout</th>
            <th style="width: 6rem;">Actions</th>
          </tr>
        </thead>
        <tbody data-rows></tbody>
      </table>
    </div>
  </div>
</div>

<script>
(function() {{
  const root = document.currentScript.previousElementSibling;
  const hidden = root.querySelector("#{input_id}");
  const rowsEl = root.querySelector("[data-rows]");

  function rowTemplate(t, idx) {{
    const esc = (s) => s == null ? "" : String(s);
    return `
      <tr data-row>
        <td>
          <input class="input input-bordered w-full" data-field="name" value="${{esc(t.name)}}" />
        </td>
        <td>
          <textarea class="textarea textarea-bordered w-full" rows="3" data-field="stdin">${{esc(t.stdin)}}</textarea>
        </td>
        <td>
          <textarea class="textarea textarea-bordered w-full" rows="3" data-field="stdout">${{esc(t.stdout)}}</textarea>
        </td>
        <td class="text-right">
          <button type="button" class="btn btn-xs btn-outline" data-action="dup">Duplicate</button>
          <button type="button" class="btn btn-xs btn-error" data-action="del">Delete</button>
        </td>
      </tr>`;
  }}

  function readHidden() {{
    try {{ return JSON.parse(hidden.value || "[]"); }}
    catch {{ return []; }}
  }}

  function writeHidden() {{
    const tests = Array.from(rowsEl.querySelectorAll("[data-row]")).map(tr => {{
      return {{
        name: tr.querySelector('[data-field="name"]').value.trim() || "case",
        stdin: tr.querySelector('[data-field="stdin"]').value,
        stdout: tr.querySelector('[data-field="stdout"]').value,
      }};
    }});
    hidden.value = JSON.stringify(tests);
  }}

  function render() {{
    const tests = readHidden();
    rowsEl.innerHTML = tests.map(rowTemplate).join("");
  }}

  function addRow(prefill) {{
    const tests = readHidden();
    tests.push(prefill || {{name: "case" + (tests.length+1), stdin: "", stdout: ""}});
    hidden.value = JSON.stringify(tests);
    render();
  }}

  root.addEventListener("click", (e) => {{
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.getAttribute("data-action");
    if (action === "add-row") {{
      addRow();
    }} else if (action === "clear-all") {{
      hidden.value = "[]";
      addRow(); // leave one fresh row
    }} else if (action === "del" || action === "dup") {{
      const tr = btn.closest("[data-row]");
      const idx = Array.from(rowsEl.children).indexOf(tr);
      const tests = readHidden();
      if (action === "del") {{
        tests.splice(idx, 1);
        if (tests.length === 0) tests.push({{name:"case1", stdin:"", stdout:""}});
      }} else {{
        const copy = Object.assign({{}}, tests[idx]);
        copy.name = copy.name + "_copy";
        tests.splice(idx+1, 0, copy);
      }}
      hidden.value = JSON.stringify(tests);
      render();
    }}
  }});

  root.addEventListener("input", (e) => {{
    if (e.target.matches("[data-field]")) writeHidden();
  }});

  // initial render from hidden value
  render();
}})();
</script>
"""
        return mark_safe(html_out)





#### FUNCTIONS ####
class FunctionTestsWidget(Widget):
    """
    Editable table for function tests. Renders inputs for each argument (from data-arg-names),
    and falls back to inferring arg names from the first row's args mapping if missing.
    Stores JSON in a hidden input with shape:
      [
        {
          name: str,
          args: { <argName>: <valueStr> },
          outcome: "expected" | "exception",
          expected?: valueStr,
          exception_type?: str,
          exception_message?: str
        }
      ]
    """
    def render(self, name, value, attrs=None, renderer=None):
        import html, json
        input_id = (attrs or {}).get("id", f"id_{name}")

        # Parse incoming rows JSON (if any)
        rows = []
        if value:
            try:
                rows = json.loads(value)
                if not isinstance(rows, list):
                    rows = []
            except Exception:
                rows = []
        if not rows:
            rows = [dict(name="baseCase", args={}, outcome="expected", expected="")]

        # Stringify for the hidden field
        data_json = html.escape(json.dumps(rows), quote=True)

        # arg names supplied by the form (preferred)
        arg_names_attr = (attrs or {}).get("data-arg-names", "[]")
        arg_names_attr = html.escape(arg_names_attr, quote=True)

        return mark_safe(f"""
<div class="fn-tests-editor">
  <input type="hidden" name="{name}" id="{input_id}" value='{data_json}' data-arg-names='{arg_names_attr}' />
  <div class="card bg-base-200" style="padding:1rem;">
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-lg font-semibold">Function Tests</h3>
      <div class="join">
        <button type="button" class="btn btn-sm join-item" data-action="add-row">+ Add</button>
        <button type="button" class="btn btn-sm btn-error join-item" data-action="clear-all">Clear</button>
      </div>
    </div>
    <div class="overflow-x-auto">
      <table class="table table-zebra w-full">
        <thead>
          <tr>
            <th style="width:12rem;">Name</th>
            <th>Args</th>
            <th style="width:16rem;">Outcome</th>
            <th style="width:7rem;">Actions</th>
          </tr>
        </thead>
        <tbody data-rows></tbody>
      </table>
    </div>
  </div>
</div>

<script>
(function() {{
  const root = document.currentScript.previousElementSibling;
  const hidden = root.querySelector("input[type=hidden]");
  const rowsEl = root.querySelector("[data-rows]");

  function readHidden() {{
    try {{ return JSON.parse(hidden.value || "[]"); }} catch {{ return []; }}
  }}
  function writeHidden() {{
    const rows = Array.from(rowsEl.querySelectorAll("[data-row]")).map(tr => {{
      const argNames = JSON.parse(tr.getAttribute("data-arg-names") || "[]");
      const args = {{}};
      argNames.forEach(an => {{
        const el = tr.querySelector(`[data-arg="${{an}}"]`);
        args[an] = el ? el.value : "";
      }});
      const outcome = tr.querySelector('[data-field="outcome"]').value;
      const out = {{
        name: tr.querySelector('[data-field="name"]').value.trim() || "case",
        args, outcome
      }};
      if (outcome === "expected") {{
        out.expected = tr.querySelector('[data-field="expected"]').value;
      }} else {{
        out.exception_type = tr.querySelector('[data-field="exception_type"]').value.trim() || "Exception";
        out.exception_message = tr.querySelector('[data-field="exception_message"]').value;
      }}
      return out;
    }});
    hidden.value = JSON.stringify(rows);
  }}

  function getArgNames() {{
    // 1) prefer data-arg-names passed from Django
    let names = [];
    try {{
      names = JSON.parse(hidden.getAttribute("data-arg-names") || "[]");
    }} catch {{ names = []; }}

    // 2) fallback: infer from first row's args mapping, preserving insertion order
    if (!names || names.length === 0) {{
      const rows = readHidden();
      const first = rows[0] || {{}};
      const args = first.args || {{}};
      names = Object.keys(args);
    }}
    return names;
  }}

  function rowTemplate(t, argNames) {{
    const esc = s => s==null ? "" : String(s);
    // Ensure row has all arg keys so inputs render with current values
    const args = Object.assign(Object.fromEntries(argNames.map(a => [a, ""])), t.args || {{}});
    const argsInputs = argNames.map(an => `
      <label class="label"><span class="label-text mr-2">${{an}}</span></label>
      <input class="input input-bordered w-full mb-2" data-arg="${{an}}" value="${{esc(args[an])}}" />
    `).join("");

    const isExpected = (t.outcome||"expected") === "expected";
    return `
      <tr data-row data-arg-names='${{JSON.stringify(argNames)}}'>
        <td>
          <input class="input input-bordered w-full" data-field="name" value="${{esc(t.name)}}" />
        </td>
        <td>
          <div>${{argsInputs}}</div>
        </td>
        <td>
          <select class="select select-bordered w-full mb-2" data-field="outcome">
            <option value="expected" ${{isExpected ? "selected":""}}>Expected value</option>
            <option value="exception" ${{!isExpected ? "selected":""}}>Raises exception</option>
          </select>
          <div data-expected ${{isExpected ? "":"style='display:none'"}}>
            <input class="input input-bordered w-full" placeholder="expected (e.g., 120)" data-field="expected" value="${{esc(t.expected)}}" />
          </div>
          <div data-exception ${{isExpected ? "style='display:none'":""}}>
            <input class="input input-bordered w-full mb-2" placeholder="Exception type (e.g., ValueError)" data-field="exception_type" value="${{esc(t.exception_type)}}" />
            <input class="input input-bordered w-full" placeholder="Optional message" data-field="exception_message" value="${{esc(t.exception_message)}}" />
          </div>
        </td>
        <td class="text-right">
          <button type="button" class="btn btn-xs btn-outline" data-action="dup">Duplicate</button>
          <button type="button" class="btn btn-xs btn-error" data-action="del">Delete</button>
        </td>
      </tr>
    `;
  }}

  function render() {{
    const rows = readHidden();
    const argNames = getArgNames();
    rowsEl.innerHTML = rows.map(r => rowTemplate(r, argNames)).join("");
  }}

  function addRow(prefill) {{
    const rows = readHidden();
    const argNames = getArgNames();
    const blankArgs = Object.fromEntries(argNames.map(a => [a, ""]));
    rows.push(prefill || {{
      name: "case" + (rows.length + 1),
      args: blankArgs,
      outcome: "expected",
      expected: ""
    }});
    hidden.value = JSON.stringify(rows);
    render();
  }}

  root.addEventListener("click", (e) => {{
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.getAttribute("data-action");
    const rows = readHidden();
    if (action === "add-row") {{
      addRow();
    }} else if (action === "clear-all") {{
      hidden.value = "[]"; addRow();
    }} else {{
      const tr = btn.closest("[data-row]");
      const idx = Array.from(rowsEl.children).indexOf(tr);
      if (action === "del") {{
        rows.splice(idx, 1);
        if (rows.length === 0) addRow();
        else {{ hidden.value = JSON.stringify(rows); render(); }}
      }} else if (action === "dup") {{
        const copy = JSON.parse(JSON.stringify(rows[idx] || {{}}));
        copy.name = (copy.name || "case") + "_copy";
        rows.splice(idx + 1, 0, copy);
        hidden.value = JSON.stringify(rows); render();
      }}
    }}
  }});

  root.addEventListener("input", (e) => {{
    const sel = e.target.closest('[data-field="outcome"]');
    if (sel) {{
      const tr = sel.closest("[data-row]");
      const isExpected = sel.value === "expected";
      tr.querySelector("[data-expected]").style.display = isExpected ? "" : "none";
      tr.querySelector("[data-exception]").style.display = isExpected ? "none" : "";
    }}
    if (e.target.matches("[data-field], [data-arg]")) writeHidden();
  }});

  // Initial render
  render();
}})();
</script>
""")



#### OOP ####
# codequestions/widgets.py (add this class)
from django.forms.widgets import Widget
from django.utils.safestring import mark_safe
import json
import html

class OopTestsWidget(Widget):
    """
    OOP tests editor.
    Each row captures:
      - name: str
      - setup: JSON array (e.g., [{"op":"create","class":"ShoppingCart","as":"cart"}])
      - steps: JSON array (e.g., [{"op":"call","on":"cart","method":"add","args":["apple",1.5],"expected":...}])

    Value stored in the hidden input is a JSON list of these rows.
    """
    def render(self, name, value, attrs=None, renderer=None):
        rows = []
        if value:
            try:
                rows = json.loads(value)
                if not isinstance(rows, list):
                    rows = []
            except Exception:
                rows = []
        if not rows:
            rows = [dict(name="case1", setup='[{"op":"create","class":"MyClass","as":"obj"}]', steps='[]')]

        # Normalize rows: ensure setup/steps are strings in the UI
        norm = []
        for r in rows:
            setup_val = r.get("setup", [])
            steps_val = r.get("steps", [])
            # If caller passed dict/list, pretty-print; if string, keep as-is
            if not isinstance(setup_val, str):
                try:
                    setup_val = json.dumps(setup_val, indent=2, ensure_ascii=False)
                except Exception:
                    setup_val = "[]"
            if not isinstance(steps_val, str):
                try:
                    steps_val = json.dumps(steps_val, indent=2, ensure_ascii=False)
                except Exception:
                    steps_val = "[]"
            norm.append({
                "name": r.get("name", "case"),
                "setup": setup_val,
                "steps": steps_val,
            })

        input_id = (attrs or {}).get("id", f"id_{name}")
        data_json = html.escape(json.dumps(norm), quote=True)

        return mark_safe(f"""
<div class="oop-tests-editor">
  <input type="hidden" name="{name}" id="{input_id}" value='{data_json}' />
  <div class="card bg-base-200" style="padding:1rem;">
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-lg font-semibold">OOP Tests</h3>
      <div class="join">
        <button type="button" class="btn btn-sm join-item" data-action="add-row">+ Add</button>
        <button type="button" class="btn btn-sm btn-error join-item" data-action="clear-all">Clear</button>
      </div>
    </div>

    <div class="overflow-x-auto">
      <table class="table table-zebra w-full">
        <thead>
          <tr>
            <th style="width:12rem;">Name</th>
            <th>Setup (JSON array)</th>
            <th>Steps (JSON array)</th>
            <th style="width:7rem;">Actions</th>
          </tr>
        </thead>
        <tbody data-rows></tbody>
      </table>
    </div>

    <div class="mt-2 text-sm opacity-70">
      Tip: Setup examples: <code>[{{"op":"create","class":"ShoppingCart","as":"cart"}}]</code><br/>
      Steps examples: <code>[{{"op":"call","on":"cart","method":"add","args":["apple",1.5]}}, {{"op":"call","on":"cart","method":"total","expected":3.5}}]</code>
    </div>
  </div>
</div>

<script>
(function() {{
  const root = document.currentScript.previousElementSibling;
  const hidden = root.querySelector("input[type=hidden]");
  const rowsEl = root.querySelector("[data-rows]");

  function readHidden() {{
    try {{ return JSON.parse(hidden.value || "[]"); }} catch {{ return []; }}
  }}
  function writeHidden() {{
    const rows = Array.from(rowsEl.querySelectorAll("[data-row]")).map(tr => {{
      return {{
        name: tr.querySelector('[data-field="name"]').value.trim() || "case",
        setup: tr.querySelector('[data-field="setup"]').value,
        steps: tr.querySelector('[data-field="steps"]').value,
      }};
    }});
    hidden.value = JSON.stringify(rows);
  }}

  function rowTemplate(t) {{
    const esc = s => s==null ? "" : String(s);
    return `
      <tr data-row>
        <td>
          <input class="input input-bordered w-full" data-field="name" value="${{esc(t.name)}}" />
        </td>
        <td>
          <textarea class="textarea textarea-bordered w-full" rows="8" data-field="setup">${{esc(t.setup)}}</textarea>
        </td>
        <td>
          <textarea class="textarea textarea-bordered w-full" rows="8" data-field="steps">${{esc(t.steps)}}</textarea>
        </td>
        <td class="text-right">
          <button type="button" class="btn btn-xs btn-outline" data-action="dup">Duplicate</button>
          <button type="button" class="btn btn-xs btn-error" data-action="del">Delete</button>
        </td>
      </tr>
    `;
  }}

  function render() {{
    const rows = readHidden();
    rowsEl.innerHTML = rows.map(rowTemplate).join("");
  }}

  function addRow(prefill) {{
    const rows = readHidden();
    rows.push(prefill || {{
      name: "case" + (rows.length + 1),
      setup: '[{{"op":"create","class":"MyClass","as":"obj"}}]',
      steps: "[]"
    }});
    hidden.value = JSON.stringify(rows);
    render();
  }}

  root.addEventListener("click", (e) => {{
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.getAttribute("data-action");
    const rows = readHidden();
    if (action === "add-row") {{
      addRow();
    }} else if (action === "clear-all") {{
      hidden.value = "[]"; addRow();
    }} else {{
      const tr = btn.closest("[data-row]");
      const idx = Array.from(rowsEl.children).indexOf(tr);
      if (action === "del") {{
        rows.splice(idx, 1);
        if (rows.length === 0) addRow();
        else {{ hidden.value = JSON.stringify(rows); render(); }}
      }} else if (action === "dup") {{
        const copy = JSON.parse(JSON.stringify(rows[idx] || {{}}));
        copy.name = (copy.name || "case") + "_copy";
        rows.splice(idx + 1, 0, copy);
        hidden.value = JSON.stringify(rows); render();
      }}
    }}
  }});

  root.addEventListener("input", (e) => {{
    if (e.target.matches("[data-field]")) writeHidden();
  }});

  render();
}})();
</script>
""")
