#!/usr/bin/env python3
"""Static release gates for the repository's invoice addon."""

import argparse
import ast
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
passed = 0
failed = 0


def check(name, fn):
    global passed, failed
    print(f"  {name:42s} ... ", end="", flush=True)
    try:
        result = bool(fn())
    except (OSError, SyntaxError, ET.ParseError, ValueError) as error:
        print(f"ERROR ({error})")
        failed += 1
        return False
    print("PASS" if result else "FAIL")
    if result:
        passed += 1
    else:
        failed += 1
    return result


def module_path(module):
    return os.path.join(BASE, "addons", module)


def files_under(root, suffixes):
    for current, directories, filenames in os.walk(root):
        directories[:] = [item for item in directories if item != "__pycache__"]
        for filename in filenames:
            if filename.endswith(suffixes):
                yield os.path.join(current, filename)


def source(module):
    root = module_path(module)
    return "\n".join(
        open(path, encoding="utf-8").read()
        for path in files_under(root, (".py", ".xml", ".js", ".csv"))
    )


def python_compile(module):
    for path in files_under(module_path(module), (".py",)):
        compile(open(path, encoding="utf-8").read(), path, "exec")
    return True


def xml_parse(module):
    for path in files_under(module_path(module), (".xml",)):
        ET.parse(path)
    return True


def no_tabs_or_bad_first_line(module):
    for path in files_under(module_path(module), (".py", ".xml", ".js", ".csv")):
        with open(path, encoding="utf-8") as stream:
            first_line = stream.readline()
            if len(first_line) - len(first_line.lstrip(" ")) > 1:
                return False
            if any("\t" in line for line in stream):
                return False
    return True


def ai_manifest(module):
    manifest = source(module)
    return '"account_invoice_import"' not in manifest


def bill_creator_does_not_read(field_name):
    path = os.path.join(module_path("ai_vendor_invoice"), "services", "bill_creator.py")
    text = open(path, encoding="utf-8").read()
    return field_name not in text


def worker_has_no_commit():
    worker = open(
        os.path.join(module_path("ai_vendor_invoice"), "services", "parse_service.py"),
        encoding="utf-8",
    ).read()
    model_entry = open(
        os.path.join(
            module_path("ai_vendor_invoice"), "models", "import_parse_attempt.py"
        ),
        encoding="utf-8",
    ).read()
    return "cr.commit(" not in worker and "cr.commit(" not in model_entry


def parse_attempt_unique_constraint():
    path = os.path.join(
        module_path("ai_vendor_invoice"), "models", "import_parse_attempt.py"
    )
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    return "task_sequence_unique" in ast.unparse(tree) and "unique(task_id, sequence)" in ast.unparse(tree)


def bill_creator_guards():
    path = os.path.join(module_path("ai_vendor_invoice"), "services", "bill_creator.py")
    text = open(path, encoding="utf-8").read()
    required = (
        'task.state != "awaiting_review"',
        "not task.human_reviewed",
        "not review_result",
        "task.vendor_bill_id",
    )
    return all(item in text for item in required)


def stale_worker_guard():
    path = os.path.join(module_path("ai_vendor_invoice"), "services", "parse_service.py")
    text = open(path, encoding="utf-8").read()
    start = text.index("def run_parse_attempt")
    worker = text[start:]
    guard = worker.index('attempt.write({\n            "status": "superseded"')
    before_guard = worker[:guard]
    return (
        "task.current_parse_attempt_id == attempt" in before_guard
        and 'attempt.status in ("queued", "running")' in before_guard
        and "task.write(" not in worker[:guard]
    )


def provider_secret_protection():
    config = open(
        os.path.join(module_path("ai_vendor_invoice"), "models", "ai_provider_config.py"),
        encoding="utf-8",
    ).read()
    if (
        'groups="ai_vendor_invoice.group_config_manager"' not in config
        or 'groups="wd_ai_vendor_invoice.group_config_manager"' in config
    ):
        return False
    for path in files_under(module_path("ai_vendor_invoice"), (".py",)):
        for line in open(path, encoding="utf-8"):
            if "api_key" in line and any(
                marker in line
                for marker in ("_logger", "error_message", "snapshot_delta", "print(")
            ):
                return False
    return True


def company_contract():
    task = open(
        os.path.join(module_path("ai_vendor_invoice"), "models", "import_task.py"),
        encoding="utf-8",
    ).read()
    worker = open(
        os.path.join(module_path("ai_vendor_invoice"), "services", "parse_service.py"),
        encoding="utf-8",
    ).read()
    return "company_id = fields.Many2one" in task and "with_company(task.company_id)" in worker


def concurrency_test_exists():
    tests = source("ai_vendor_invoice")
    return (
        "Thread(" in tests
        and "account.move" in tests
        and "test_concurrent_bill_creation_has_one_winner" in tests
    )


def queue_entry_contract():
    model = open(
        os.path.join(
            module_path("ai_vendor_invoice"), "models", "import_parse_attempt.py"
        ),
        encoding="utf-8",
    ).read()
    service_text = "\n".join(
        open(path, encoding="utf-8").read()
        for path in files_under(
            os.path.join(module_path("ai_vendor_invoice"), "services"), (".py",)
        )
    )
    return ".with_delay(" in model and ".with_delay(" not in service_text


def bill_create_call():
    path = os.path.join(module_path("ai_vendor_invoice"), "services", "bill_creator.py")
    text = open(path, encoding="utf-8").read()
    return 'env["account.move"].create(' in text and "account_invoice_import" not in text


def company_immutable():
    path = os.path.join(module_path("ai_vendor_invoice"), "models", "import_task.py")
    text = open(path, encoding="utf-8").read()
    return '"company_id" in vals' in text and "cannot be changed" in text


def unified_review_entry():
    task = open(
        os.path.join(module_path("ai_vendor_invoice"), "models", "import_task.py"),
        encoding="utf-8",
    ).read()
    creator = open(
        os.path.join(module_path("ai_vendor_invoice"), "services", "bill_creator.py"),
        encoding="utf-8",
    ).read()
    return (
        "action_confirm_review_and_create_bill" in task
        and "confirm_review_and_create_bill" in creator
    )


def no_http_inside_lock():
    parse_path = os.path.join(
        module_path("ai_vendor_invoice"), "services", "parse_service.py"
    )
    parse = open(parse_path, encoding="utf-8").read()
    worker = parse[parse.index("def run_parse_attempt") :]
    adapters = "\n".join(
        open(path, encoding="utf-8").read()
        for path in files_under(
            os.path.join(module_path("ai_vendor_invoice"), "adapters"), (".py",)
        )
    )
    return "lock_task(" not in worker and "lock_attempt(" not in worker and "requests.post(" not in worker and "requests.post(" in adapters


def ai_gates():
    checks = [
        ("GATE-01 manifest excludes account_invoice_import", lambda: ai_manifest("ai_vendor_invoice")),
        ("GATE-02 bill creator excludes canonical_result", lambda: bill_creator_does_not_read("canonical_result")),
        ("GATE-03 bill creator excludes mapping_result", lambda: bill_creator_does_not_read("mapping_result")),
        ("GATE-04 worker excludes cr.commit()", worker_has_no_commit),
        ("GATE-05 ParseAttempt unique(task_id, sequence)", parse_attempt_unique_constraint),
        ("GATE-06 bill creator preconditions", bill_creator_guards),
        ("GATE-07 stale worker guard", stale_worker_guard),
        ("GATE-08 provider secret protection", provider_secret_protection),
        ("GATE-09 company contract", company_contract),
        ("GATE-10 concurrency test exists", concurrency_test_exists),
        ("GATE-11 model-only queue entry", queue_entry_contract),
        ("GATE-12 account.move.create only", bill_create_call),
        ("GATE-13 immutable task company", company_immutable),
        ("GATE-14 unified review entry", unified_review_entry),
        ("GATE-15 HTTP outside row locks", no_http_inside_lock),
    ]
    results = [check(name, fn) for name, fn in checks]
    return all(results)


def legacy_odoo18_views():
    patterns = (
        "<tree",
        "decoration-bf",
        "decoration-it",
        "state_selection",
        "colors=",
        "fonts=",
        "attrs=",
        "states=",
    )
    for path in files_under(os.path.join(module_path("wd_tlms"), "views"), (".xml",)):
        text = open(path, encoding="utf-8").read()
        if any(pattern in text for pattern in patterns):
            return False
        if re.search(r'view_mode\s*=\s*"[^"]*\btree\b[^"]*"', text):
            return False
    return True


def legacy_view_model_fields():
    checker = os.path.join(BASE, "docs", "context", "governance", "check_view_fields.py")
    if not os.path.isfile(checker):
        return False
    result = subprocess.run([sys.executable, checker], capture_output=True, text=True)
    return result.returncode == 0


def legacy_menu_order():
    errors = []
    for path in files_under(os.path.join(module_path("wd_tlms"), "views"), (".xml",)):
        defined = {}
        referenced = []
        for line_number, line in enumerate(
            open(path, encoding="utf-8"), start=1
        ):
            menu_id = re.search(r'\bid="(\w+)"', line)
            parent = re.search(r'\bparent="(\w+)"', line)
            if menu_id:
                defined[menu_id.group(1)] = line_number
            if parent:
                referenced.append((parent.group(1), line_number))
        for parent, line_number in referenced:
            if parent not in defined or defined[parent] > line_number:
                errors.append(path)
    return not errors


def legacy_wd_tlms():
    root = module_path("wd_tlms")
    views = os.path.join(root, "views")
    if not os.path.isdir(views):
        print(f"  missing legacy path: {views}")
        return False
    checks = [
        ("Python compile", lambda: python_compile("wd_tlms")),
        ("XML structure", lambda: xml_parse("wd_tlms")),
        ("No leading tabs", lambda: no_tabs_or_bad_first_line("wd_tlms")),
        ("Module name consistency", lambda: "transport_logistics_management" not in source("wd_tlms")),
        ("Odoo 18 view compatibility", legacy_odoo18_views),
        ("View-model fields", legacy_view_model_fields),
        ("Menu ordering", legacy_menu_order),
    ]
    return all(check(name, fn) for name, fn in checks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--module",
        default="ai_vendor_invoice",
        help="addon module to verify (default: ai_vendor_invoice)",
    )
    args = parser.parse_args()

    if not os.path.isdir(module_path(args.module)):
        print(f"module path does not exist: {module_path(args.module)}")
        return 1

    print(f"\n========== Verification: {args.module} ==========")
    if args.module == "ai_vendor_invoice":
        ok = all(
            (
                check("Python compile", lambda: python_compile(args.module)),
                check("XML structure", lambda: xml_parse(args.module)),
                check("No leading tabs", lambda: no_tabs_or_bad_first_line(args.module)),
                check("GATE-01..GATE-15", ai_gates),
            )
        )
    else:
        ok = all(
            (
                check("Python compile", lambda: python_compile(args.module)),
                check("XML structure", lambda: xml_parse(args.module)),
                check("No leading tabs", lambda: no_tabs_or_bad_first_line(args.module)),
            )
        )

    print(f"\n========== Result: {passed} pass, {failed} fail ==========")
    print("  ALL CHECKS PASSED" if ok and failed == 0 else "  CHECKS FAILED")
    return 0 if ok and failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
