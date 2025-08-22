from django.shortcuts import render
from sandbox.models import Runtime
import json
from django.db import transaction
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_POST
from django.middleware.csrf import get_token
from django.core.exceptions import ValidationError

from sandbox.models import Runtime
from codequestions.models import CodeQuestion, StructuralTest

def structural_builder(request):
    qs = (
        Runtime.objects.select_related("language")
        .order_by("language__name", "name")
        .only("id", "name", "slug", "language__id", "language__name", "language__slug")
    )

    # Serialize to simple dicts (json_script requires JSON-serializable data)
    runtimes = [
        {
            "id": rt.id,
            "name": rt.name,
            "slug": rt.slug,
            "language": {
                "id": rt.language.id,
                "name": rt.language.name,
                "slug": rt.language.slug,
            },
        }
        for rt in qs
    ]

    return render(request, "codequestions/structural_builder.html", {"runtimes": runtimes})


@require_POST
@transaction.atomic
def structural_save(request: HttpRequest) -> JsonResponse:
    """
    Accepts JSON:
    {
      "id": optional int,
      "question_type": "structural",
      "prompt": str,
      "timeout_seconds": int > 0,
      "memory_limit_mb": int > 0,
      "structural_tests": [
        {"runtime_id": int, "test_source": str}, ...
      ]
    }
    """
    # ---- Parse ----
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "errors": {"_": "Invalid JSON payload."}}, status=400)

    errors = {}

    # ---- Validate top-level ----
    if (data.get("question_type") or "").lower() != "structural":
        errors["question_type"] = "question_type must be 'structural'."

    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        errors["prompt"] = "Prompt is required."

    def as_pos_int(val, field):
        try:
            n = int(val)
            if n <= 0:
                raise ValueError
            return n
        except Exception:
            errors[field] = "Enter a positive integer."
            return None

    timeout_seconds = as_pos_int(data.get("timeout_seconds"), "timeout_seconds")
    memory_limit_mb = as_pos_int(data.get("memory_limit_mb"), "memory_limit_mb")

    # ---- Validate structural_tests ----
    tests_in = data.get("structural_tests", [])
    if not isinstance(tests_in, list):
        errors["structural_tests"] = "structural_tests must be a list."
        tests_in = []

    runtime_ids = []
    clean_tests = []
    for idx, t in enumerate(tests_in):
        # runtime_id
        rt_err_key = f"structural_tests[{idx}].runtime_id"
        try:
            rt_id = int(t.get("runtime_id"))
        except Exception:
            rt_id = None
        if not rt_id:
            errors[rt_err_key] = "Select a runtime."

        # test_source
        ts_err_key = f"structural_tests[{idx}].test_source"
        ts = (t.get("test_source") or "").strip()
        if not ts:
            errors[ts_err_key] = "Test source is required."

        clean_tests.append((rt_id, ts))
        if rt_id:
            runtime_ids.append(rt_id)

    # at least one
    if len([x for x in runtime_ids if x]) == 0:
        errors["structural_tests[0].runtime_id"] = "Provide at least one runtime test."

    # no duplicates
    chosen = [x for x in runtime_ids if x]
    if len(set(chosen)) != len(chosen):
        errors["structural_tests"] = "Duplicate runtime detected. Each runtime may appear only once."

    # runtime existence
    existing = set(Runtime.objects.filter(id__in=runtime_ids).values_list("id", flat=True))
    for idx, (rt_id, _ts) in enumerate(clean_tests):
        if rt_id and rt_id not in existing:
            errors[f"structural_tests[{idx}].runtime_id"] = "Runtime not found."

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    # ---- Create/update question ----
    qid = data.get("id")
    if qid:
        try:
            qid = int(qid)
            q = CodeQuestion.objects.select_for_update().get(pk=qid)
            if q.question_type != CodeQuestion.QuestionType.STRUCTURAL:
                return JsonResponse({"ok": False, "errors": {"id": "Not a structural question."}}, status=400)
        except Exception:
            return JsonResponse({"ok": False, "errors": {"id": "Question not found."}}, status=404)
    else:
        q = CodeQuestion(question_type=CodeQuestion.QuestionType.STRUCTURAL)

    q.prompt = prompt
    q.timeout_seconds = timeout_seconds
    q.memory_limit_mb = memory_limit_mb
    q.tests_json = None  # ensure absent for structural

    try:
        q.full_clean()
    except ValidationError as ve:
        return JsonResponse({"ok": False, "errors": ve.message_dict}, status=400)

    q.save()

    # Replace child tests
    StructuralTest.objects.filter(code_question=q).delete()
    for (rt_id, ts) in clean_tests:
        StructuralTest.objects.create(
            code_question=q,
            runtime_id=rt_id,
            test_source=ts,  # .save() runs and computes sha256
        )


    return JsonResponse({"ok": True, "id": q.id})
