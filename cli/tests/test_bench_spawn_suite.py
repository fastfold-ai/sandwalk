"""Drive the bench suite runner with a fake session store."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

from agent_server.bench_service import spawn_core as sc

_REAL_MCQ = sc._resolve_mcq_cells
_REAL_CODING = sc._resolve_coding_cells


class _Store:
    def __init__(self):
        self.projects = {}
        self.sessions = {}
        self.deleted = []

    def create_project(self, **kwargs):
        project = SimpleNamespace(id="proj-1", **kwargs)
        self.projects[project.id] = project
        return project

    def get_project(self, pid):
        return self.projects.get(pid)

    def insert_project_copy(self, project):
        self.projects[project.id] = project

    def delete_project(self, pid):
        self.deleted.append(pid)

    def get_session(self, sid):
        return self.sessions.get(sid)


class _Svc:
    def __init__(self, store, workspace, fail=None):
        self.store = store
        self.workspace = workspace
        self.fail = fail
        self.messages = []
        self.interrupts = []

    def create_session(self, **kwargs):
        if self.fail == "create":
            raise RuntimeError(self.fail_message)
        session = SimpleNamespace(id=f"s{len(self.store.sessions)+1}", workspace_path=self.workspace, project_id=kwargs.get("project_id"))
        self.store.sessions[session.id] = session
        return session

    fail_message = "boom"

    def ensure_workspace(self, sid):
        return self.store.sessions[sid]

    def submit_message(self, **kwargs):
        if self.fail == "submit":
            raise RuntimeError(self.fail_message)
        self.messages.append(kwargs)

    def interrupt(self, sid):
        self.interrupts.append(sid)


def _cell(qid="q1"):
    return SimpleNamespace(
        question_id=qid,
        title="T",
        model_id="gemma",
        provider="openai",
        prompt="Answer?",
        question=SimpleNamespace(ideal="A", question="Q", focus="math", id=qid, eval_mode="mcq", source={}),
    )


def _pack():
    return SimpleNamespace(id="mmlu", questions=[], matrices={})


def _deps(tmp_path, fail=None):
    store = _Store()
    svc = _Svc(store, str(tmp_path), fail=fail)
    return SimpleNamespace(
        store=store,
        worker_store=lambda: store,
        worker_service=lambda: svc,
    ), svc


def _patch(monkeypatch, cells, wait="settled", grade=None):
    monkeypatch.setattr(sc, "ensure_sandwalk_bench_importable", lambda: True)
    monkeypatch.setattr(sc, "_resolve_mcq_cells", lambda **kwargs: (cells, _pack(), "mmlu"))
    monkeypatch.setattr(sc.SettingsService, "get", staticmethod(lambda: SimpleNamespace(provider="openai", model="gemma", openai_profile_id=None)))
    monkeypatch.setattr(sc, "resolve_bench_provider", lambda provider, profile_id=None: provider)
    monkeypatch.setattr(sc, "capture_bench_environment", lambda *a, **k: {"runtime": {}})
    monkeypatch.setattr(sc, "save_checkpoint", lambda payload: None)
    monkeypatch.setattr(sc, "save_result", lambda result: None)
    monkeypatch.setattr(sc, "get_result", lambda run_id: None)
    monkeypatch.setattr(sc, "delete_checkpoint", lambda run_id: None)
    monkeypatch.setattr(sc, "rollup_suite_usage", lambda **k: None)
    monkeypatch.setattr(sc, "delete_bench_project_data", lambda *a, **k: None)
    spawn = types.ModuleType("sandwalk_bench.spawn")
    spawn.copy_cell_inputs = lambda *a, **k: None
    spawn.bench_kickoff_message = lambda **k: "go"

    class _Obj:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    schema = types.ModuleType("sandwalk_bench.schema")
    schema.Question = _Obj
    schema.MatrixCell = _Obj
    schema.Pack = _Obj
    monkeypatch.setitem(sys.modules, "sandwalk_bench.schema", schema)
    spawn.default_project_name = lambda *a, **k: "Bench"
    spawn.build_project_description = lambda **k: "desc"
    pkg = types.ModuleType("sandwalk_bench")
    pkg.__path__ = []
    monkeypatch.setitem(sys.modules, "sandwalk_bench", pkg)
    monkeypatch.setitem(sys.modules, "sandwalk_bench.spawn", spawn)
    monkeypatch.setattr(sc, "_wait_until_settled", lambda *a, **k: wait)
    monkeypatch.setattr(
        sc,
        "_grade_session",
        lambda *a, **k: grade or {"correct": True, "predicted": "A"},
    )
    monkeypatch.setattr("agent_server.bench_service.catalog.pack_display_title", lambda pack_id: "MMLU")
    monkeypatch.setattr("agent_server.bench_service.retry_extra.take_extra_retry", lambda run_id: [])


def test_suite_grades_one_cell_and_can_clean_sessions(monkeypatch, tmp_path):
    deps, svc = _deps(tmp_path)
    _patch(monkeypatch, [_cell()])
    progress = []
    result = sc.run_agent_suite(
        deps=deps,
        suite_id="mmlu",
        pack_id="mmlu",
        matrix=None,
        model_id="gemma",
        provider="openai",
        sample_size=1,
        project_name=None,
        on_progress=progress.append,
        cleanup_sessions=True,
        concurrency=2,
    )
    assert result["status"] == "completed"
    assert result["sessions_cleaned"] is True
    assert svc.messages
    assert progress


def test_suite_cancel_stall_and_errors(monkeypatch, tmp_path):
    deps, _svc = _deps(tmp_path)
    _patch(monkeypatch, [_cell()])
    cancelled = sc.run_agent_suite(
        deps=deps,
        suite_id="mmlu",
        pack_id="mmlu",
        matrix=None,
        model_id="gemma",
        provider=None,
        sample_size=1,
        project_name="Keep",
        stop_check=lambda: "cancel",
    )
    assert cancelled["status"] == "cancelled"

    _patch(monkeypatch, [_cell()], wait="stalled")
    stalled = sc.run_agent_suite(
        deps=deps,
        suite_id="mmlu",
        pack_id="mmlu",
        matrix=None,
        model_id="gemma",
        provider="openai",
        sample_size=1,
        project_name=None,
    )
    assert stalled["status"] == "completed"

    deps, svc = _deps(tmp_path, fail="create")
    svc.fail_message = "event loop is closed"
    _patch(monkeypatch, [_cell()])
    paused = sc.run_agent_suite(
        deps=deps,
        suite_id="mmlu",
        pack_id="mmlu",
        matrix=None,
        model_id="gemma",
        provider="openai",
        sample_size=1,
        project_name=None,
    )
    assert paused["status"] == "paused"

    deps, svc = _deps(tmp_path, fail="create")
    svc.fail_message = "disk full"
    _patch(monkeypatch, [_cell()])
    failed = sc.run_agent_suite(
        deps=deps,
        suite_id="mmlu",
        pack_id="mmlu",
        matrix=None,
        model_id="gemma",
        provider="openai",
        sample_size=1,
        project_name=None,
    )
    assert failed["status"] == "completed"

    monkeypatch.setattr(sc, "_resolve_mcq_cells", lambda **kwargs: ([], _pack(), "mmlu"))
    try:
        sc.run_agent_suite(
            deps=deps,
            suite_id="mmlu",
            pack_id="mmlu",
            matrix=None,
            model_id="gemma",
            provider="openai",
            sample_size=1,
            project_name=None,
        )
        raise AssertionError("expected no cells")
    except RuntimeError as exc:
        assert "No cells" in str(exc)

    _patch(monkeypatch, [_cell(), _cell("q2")], wait="timeout")
    timed = sc.run_agent_suite(
        deps=deps,
        suite_id="mmlu",
        pack_id="mmlu",
        matrix=None,
        model_id="gemma",
        provider="openai",
        sample_size=1,
        project_name=None,
        resume_checkpoint={
            "run_id": "resume-1",
            "completed_question_ids": ["q2"],
            "remaining_question_ids": ["q1"],
            "environment": {"runtime": {}},
            "elapsed_s": 4,
            "name": "Old",
            "force_retry": True,
        },
        run_id="resume-1",
    )
    assert timed["status"] == "completed"

    monkeypatch.setattr(
        "agent_server.bench_service.mcq_suites.load_mcq_items",
        lambda suite_id, n: [{"id": "q", "question": "Q", "answer": "A", "subject": "math"}],
    )
    monkeypatch.setattr(
        "agent_server.bench_service.mcq_suites.format_mcq_prompt",
        lambda suite_id, item: "prompt",
    )
    cells, pack, benchmark = _REAL_MCQ(
        suite_id="mmlu", sample_size=1, model_id="", provider=None
    )
    assert benchmark == "mmlu" and cells and pack.id == "mmlu"

    class _Suite:
        title = "MBPP"
        default_sample_size = 1

    monkeypatch.setattr(
        "agent_server.bench_service.coding_suites.CODING_SUITES",
        {"mbpp": _Suite()},
    )
    monkeypatch.setattr(
        "agent_server.bench_service.coding_suites.load_coding_items",
        lambda suite_id, n: [{"id": "c1", "question": "code", "subject": "py", "title": "Add"}],
    )
    monkeypatch.setattr(
        "agent_server.bench_service.coding_suites.format_coding_prompt",
        lambda suite_id, item: "write code",
    )
    coded, coded_pack, coded_bench = _REAL_CODING(
        suite_id="mbpp", sample_size=1, model_id="gemma", provider="openai"
    )
    assert coded_bench == "mbpp" and coded and coded_pack.questions

    class _Capsule:
        def is_dir(self):
            return True

    capsules = types.ModuleType("sandwalk_bench.capsules")
    capsules.ensure_capsule = lambda folder, token=None: _Capsule()
    monkeypatch.setitem(sys.modules, "sandwalk_bench.capsules", capsules)
    monkeypatch.setattr(
        "agent_server.bench_service.dataset_install.resolve_hf_token",
        lambda: "",
    )
    monkeypatch.setattr(sc.shutil, "copytree", lambda src, dest: None)
    monkeypatch.setattr(sc.shutil, "rmtree", lambda path: None)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    assert sc._copy_bix_capsule({"data_folder": "cap"}, workspace) is True
    capsules.ensure_capsule = lambda folder, token=None: None
    assert sc._copy_bix_capsule({"data_folder": "cap"}, workspace) is False
    assert sc._copy_bix_capsule({}, workspace) is False
