"""spec 0005 2.6, C-4, H-1 (P4-4): **승인자 권한 모델이 없다** 를 구조로 고정합니다.

v1 은 인증된 주체 누구나 승인할 수 있고, 누가 승인했는지는 **기록** 하되 누가 승인할 수 있는지는
**묻지 않습니다**(Phase 8 의 자리). "자기 승인 금지" 같은 그럴듯한 반쪽 규칙이 이 단위의 반려
사유이므로, 승인 경로의 코드가 주체를 판정하는 모양을 갖지 않는다는 것을 AST 로 확인합니다.

검사 대상은 승인 경로의 **api 쪽** 소스입니다. (실행기는 `requested_by` 를 자식 Agent Run 에
물려주려고 읽으므로 이름 검사를 하지 않습니다 - 실행기 쪽은 `Approval` 값 객체에 승인 주체가
없다는 것으로 `packages/workflow/tests/test_advance_approval_node.py` 가 고정합니다.)

1. 승인 유스케이스·승인 도메인에는 주체를 가리키는 이름(`requested_by`·`key_id`·`label`·`role`·
   `permission`…)이 없다 - 유스케이스는 `approved_by` 문자열을 받아 **그대로 적을 뿐** 이다.
2. 승인 라우터는 `Principal` 에서 `key_id` 하나만 읽는다(기록할 주체 id). 그 밖의 필드를 읽지 않고
   403 을 내지 않는다.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_API = REPO_ROOT / "apps" / "api" / "src" / "aether_api"

_USECASE_AND_DOMAIN = [
    _API / "application" / "usecases" / "approve_workflow_node.py",
    _API / "application" / "usecases" / "list_workflow_approvals.py",
    _API / "domain" / "workflow_approval.py",
    _API / "application" / "ports" / "inbound" / "workflow_approvals.py",
    _API / "application" / "ports" / "outbound" / "workflow_approval_store.py",
]
_ROUTER = _API / "adapters" / "inbound" / "http" / "workflow_approvals.py"

_PRINCIPAL_NAMES = {
    "requested_by",
    "key_id",
    "label",
    "role",
    "roles",
    "permission",
    "permissions",
    "approvers",
    "approver_ids",
    "allowed_approvers",
    "authorize",
    "is_authorized",
}


def _identifiers(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
    return names


def test_the_approval_usecases_and_domain_never_name_a_principal_or_a_permission() -> None:
    offenders = {
        str(path.relative_to(REPO_ROOT)): sorted(_identifiers(path) & _PRINCIPAL_NAMES)
        for path in _USECASE_AND_DOMAIN
        if _identifiers(path) & _PRINCIPAL_NAMES
    }

    assert not offenders, (
        "승인 경로에 주체/권한을 가리키는 이름이 생겼습니다 - 승인자 권한 모델은 만들지 않습니다"
        f"(spec C-4): {offenders}"
    )


def test_the_approval_router_reads_only_the_principal_id_to_record_it_and_never_forbids() -> None:
    tree = ast.parse(_ROUTER.read_text(encoding="utf-8"))
    principal_attributes = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "principal"
    }
    status_codes = {
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.keyword)
        and node.arg == "status_code"
        and isinstance(node.value, ast.Constant)
    }
    forbidden_names = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "HTTP_403_FORBIDDEN"
    }

    assert principal_attributes <= {"key_id"}, principal_attributes
    assert 403 not in status_codes, status_codes
    assert not forbidden_names
    assert status_codes <= {400, 404, 201}, status_codes
