"""Unit and route tests for Automations (Cron & Event Schedules) and Remote-SSH Services."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_server.app import create_app
from agent_server.automations_service import (
    AutomationsService,
    compute_next_run,
    list_automation_templates,
    parse_schedule,
)
from agent_server.models.automations import (
    CreateAutomationRequest,
    CreateSshHostRequest,
    SshConnectRequest,
    UpdateAutomationRequest,
    UpdateSshHostRequest,
)
from agent_server.ssh_service import (
    SshService,
    discover_ssh_config_hosts,
    parse_ssh_target_string,
)
from agent_server.store import AgentStore


def test_schedule_parser_variants() -> None:
    now = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)

    p_once = parse_schedule("in 30m", now=now)
    assert p_once.kind == "once"
    assert p_once.once_at == now + timedelta(minutes=30)

    p_iso = parse_schedule("2026-10-22T09:30:00", now=now)
    assert p_iso.kind == "once"
    assert p_iso.once_at is not None

    p_int = parse_schedule("every 15m", now=now)
    assert p_int.kind == "interval"
    assert p_int.interval_seconds == 900

    p_daily = parse_schedule("daily at 9:15am", now=now)
    assert p_daily.kind == "cron"
    assert p_daily.cron_fields == ("15", "9", "*", "*", "*")
    nxt = compute_next_run("daily at 9:15am", after=now)
    assert nxt is not None
    assert nxt.hour == 9 and nxt.minute == 15

    p_wk = parse_schedule("weekdays at 8:30am", now=now)
    assert p_wk.kind == "cron"
    assert p_wk.cron_fields == ("30", "8", "*", "*", "1-5")

    p_dow = parse_schedule("every monday, wednesday at 2pm", now=now)
    assert p_dow.kind == "cron"
    assert p_dow.cron_fields == ("0", "14", "*", "*", "1,3")

    p_cron = parse_schedule("*/15 * * * *", now=now)
    assert p_cron.kind == "cron"

    p_web = parse_schedule("webhook", now=now)
    assert p_web.kind == "webhook"
    assert compute_next_run("webhook", after=now) is None

    with pytest.raises(ValueError):
        parse_schedule("not a valid schedule")


def test_automations_service_lifecycle_and_modes(tmp_path: Path) -> None:
    store = AgentStore(tmp_path / "test.db")
    ssh_svc = SshService(store)
    svc = AutomationsService(store, ssh_service=ssh_svc)

    # 1. Templates
    tpls = list_automation_templates()
    assert len(tpls) >= 5

    # 2. Create no_agent script automation
    auto1 = svc.create_automation(
        CreateAutomationRequest(
            name="Echo Check",
            command="echo hello-cron",
            schedule_expr="every 15m",
            session_mode="no_agent",
            continuity=True,
            wake_on_change_only=True,
        )
    )
    assert auto1.schedule_kind == "interval"
    assert auto1.enabled is True

    # Run 1 -> executes command and writes output
    run1 = asyncio.run(svc.trigger_automation(auto1.id, wait=True))
    assert run1.status == "succeeded"
    assert "hello-cron" in (run1.output_excerpt or "")
    assert svc.read_latest_output(auto1.id) == "hello-cron"

    # Run 2 with identical stdout + wake_on_change_only=True -> skipped!
    run2 = asyncio.run(svc.trigger_automation(auto1.id, wait=True))
    assert run2.status == "skipped"

    # 3. Create downstream fresh-session automation chaining from auto1
    auto2 = svc.create_automation(
        CreateAutomationRequest(
            name="Downstream Digest",
            prompt="Summarize upstream output.",
            schedule_expr="in 10m",
            session_mode="fresh",
            continuity=True,
            context_from=[auto1.id],
        )
    )
    run3 = asyncio.run(svc.trigger_automation(auto2.id, wait=True))
    assert run3.status == "succeeded"
    assert run3.session_id is not None

    # One-shot schedule should auto-complete after 1 run
    after_auto2 = svc.get_automation(auto2.id)
    assert after_auto2 is not None
    assert after_auto2.last_status == "completed"
    assert after_auto2.enabled is False

    # 4. Continue mode + snooze/unsnooze
    origin_sess = store.create_session(title="Job Watcher Thread", workspace_path=None)
    auto3 = svc.create_automation(
        CreateAutomationRequest(
            template_id="watch-background-job",
            origin_session_id=origin_sess.id,
            session_mode="continue",
            command="",
        )
    )
    store.update_session(origin_sess.id, snoozed=True)
    assert store.get_session(origin_sess.id).snoozed is True  # type: ignore[union-attr]

    run4 = asyncio.run(svc.trigger_automation(auto3.id, wait=True))
    assert run4.session_id == origin_sess.id

    svc.pause_automation(auto3.id)
    assert svc.get_automation(auto3.id).enabled is False  # type: ignore[union-attr]
    svc.resume_automation(auto3.id)
    assert svc.get_automation(auto3.id).enabled is True  # type: ignore[union-attr]
    svc.complete_automation(auto3.id)
    assert store.get_session(origin_sess.id).snoozed is False  # type: ignore[union-attr]

    # 5. tick_once missed-run catch-up
    past_due = svc.create_automation(
        CreateAutomationRequest(
            name="Catchup Job",
            command="echo caught-up",
            session_mode="no_agent",
            schedule_expr="every 1h",
        )
    )
    store.update_automation_fields(
        past_due.id,
        next_run_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    fired = asyncio.run(svc.tick_once(catch_up_missed=True))
    assert any(r.automation_id == past_due.id and r.was_catchup for r in fired)


def test_ssh_config_discovery_and_target_parser(tmp_path: Path) -> None:
    parsed = parse_ssh_target_string(
        "ssh -p 2222 -i ~/.ssh/id_ed25519 -J jump.edu julio@login.hpc.edu"
    )
    assert parsed.user == "julio"
    assert parsed.host == "login.hpc.edu"
    assert parsed.port == 2222
    assert parsed.alias == "login"
    assert parsed.proxy_jump == "jump.edu"

    ssh_cfg = tmp_path / "ssh_config"
    ssh_cfg.write_text(
        """
Host hpc-cluster
    HostName login.rc.university.edu
    User jcesar
    Port 2202
    IdentityFile ~/.ssh/hpc_key

Host *
    ServerAliveInterval 30
""",
        encoding="utf-8",
    )
    hosts = discover_ssh_config_hosts(ssh_cfg)
    assert len(hosts) == 1
    assert hosts[0].alias == "hpc-cluster"
    assert hosts[0].host == "login.rc.university.edu"
    assert hosts[0].user == "jcesar"
    assert hosts[0].port == 2202


def test_ssh_service_probe_exec_slurm_and_bootstrap(tmp_path: Path) -> None:
    store = AgentStore(tmp_path / "ssh.db")
    svc = SshService(store)

    host = svc.create_host(
        CreateSshHostRequest(
            target="julio@192.168.64.10:22",
            alias="ubuntu-sandbox",
            default_workdir="/home/julio/work",
        )
    )
    assert host.alias == "ubuntu-sandbox"
    updated = svc.update_host(
        host.id, UpdateSshHostRequest(default_workdir="/scratch/julio")
    )
    assert updated is not None and updated.default_workdir == "/scratch/julio"

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        cmd_str = " ".join(str(a) for a in args)
        m = MagicMock()
        m.returncode = 0
        m.stderr = ""
        if "HOSTNAME=" in cmd_str:
            m.stdout = (
                "HOSTNAME=ubuntu-hpc\n"
                "UNAME=Linux aarch64\n"
                "PWD=/home/julio\n"
                "GPU=NVIDIA H100\n"
                "SLURM=1\n"
                "SW_BIN=/home/julio/.local/bin/sandwalk\n"
                "SW_VER=0.1.13\n"
                "DAEMON=1\n"
            )
        elif "SLURM_AVAILABLE=1" in cmd_str:
            m.stdout = (
                "SLURM_AVAILABLE=1\n"
                "48291|gpu|boltz-glp1r|julio|RUNNING|01:14:22|2|gpu-node-04\n"
            )
        elif "PERSISTENCE=" in cmd_str:
            m.stdout = (
                "PERSISTENCE=systemd-user\n"
                "WATCHDOG=1\n"
                "HEALTH_OK=1\n"
                "REMOTE_KEY=sw-remote-secret\n"
            )
        else:
            m.stdout = "remote-ok\n"
        return m

    with (
        patch("agent_server.ssh_service.service.subprocess.run", side_effect=fake_run),
        patch.object(SshService, "open_tunnel", return_value=54321),
    ):
        probe = svc.probe_host(host.id)
        assert probe.reachable is True
        assert probe.slurm_available is True
        assert probe.gpu_summary == "NVIDIA H100"

        slurm = svc.get_slurm_status(host.id)
        assert slurm.slurm_available is True
        assert len(slurm.jobs) == 1
        assert slurm.jobs[0].job_id == "48291"

        conn_res = svc.connect_and_bootstrap(
            SshConnectRequest(host_id_or_target=host.id)
        )
        assert conn_res.local_url == "http://127.0.0.1:54321"
        assert conn_res.daemon_persistence == "systemd-user"
        assert conn_res.watchdog_installed is True
        assert conn_res.remote_api_key == "sw-remote-secret"

        sync_res = svc.sync_files(
            host.id,
            local_path=str(tmp_path),
            remote_path="/scratch/julio/out",
            direction="push",
        )
        assert sync_res.exit_code == 0


def test_automations_and_ssh_routes_and_tools(tmp_path: Path) -> None:
    app = create_app(store_path=tmp_path / "routes.db")
    client = TestClient(app)

    # 1. Templates route
    r_tpl = client.get("/v1/automations/templates")
    assert r_tpl.status_code == 200
    assert len(r_tpl.json()["data"]) >= 5

    # 2. Create automation via REST
    r_create = client.post(
        "/v1/automations",
        json={
            "name": "Route Test Job",
            "command": "echo route-ok",
            "scheduleExpr": "every 30m",
            "sessionMode": "no_agent",
        },
    )
    assert r_create.status_code == 201
    created = r_create.json()
    auto_id = created["id"]
    token = created["webhookToken"]

    # 3. Get, update, list runs, trigger manual run & webhook run
    assert client.get(f"/v1/automations/{auto_id}").status_code == 200
    assert (
        client.patch(
            f"/v1/automations/{auto_id}",
            json={"name": "Renamed Route Job", "scheduleExpr": "every 45m"},
        ).status_code
        == 200
    )

    r_run = client.post(f"/v1/automations/{auto_id}/run", json={"wait": True})
    assert r_run.status_code == 200
    assert r_run.json()["status"] == "succeeded"

    assert (
        len(client.get(f"/v1/automations/runs?automation_id={auto_id}").json()["data"])
        >= 1
    )

    r_wh = client.post(
        f"/v1/automations/webhook/{token}", json={"context": "slurm job 99 done"}
    )
    assert r_wh.status_code == 200

    # 4. SSH host routes
    r_ssh = client.post(
        "/v1/ssh/hosts",
        json={"target": "julio@cluster.edu:2222", "alias": "cluster"},
    )
    assert r_ssh.status_code == 201
    hid = r_ssh.json()["id"]

    assert (
        client.patch(
            f"/v1/ssh/hosts/{hid}", json={"defaultWorkdir": "/scratch/julio"}
        ).status_code
        == 200
    )
    r_list = client.get("/v1/ssh/hosts")
    assert r_list.status_code == 200
    assert any(h["id"] == hid for h in r_list.json()["data"])

    with patch("agent_server.ssh_service.service.subprocess.run") as mock_run:
        m = MagicMock()
        m.returncode = 0
        m.stdout = "HOSTNAME=cluster\nUNAME=Linux x86_64\nSLURM=1\n"
        m.stderr = ""
        mock_run.return_value = m
        assert client.post(f"/v1/ssh/hosts/{hid}/probe").status_code == 200
        assert client.get(f"/v1/ssh/hosts/{hid}/slurm").status_code == 200
        assert (
            client.post(
                "/v1/ssh/exec",
                json={"hostIdOrTarget": hid, "command": "uptime"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/ssh/sync",
                json={
                    "hostIdOrTarget": hid,
                    "localPath": str(tmp_path),
                    "remotePath": "/scratch/julio",
                },
            ).status_code
            == 200
        )

    assert client.post(f"/v1/ssh/hosts/{hid}/disconnect").status_code == 200
    assert client.delete(f"/v1/ssh/hosts/{hid}").status_code == 200
    assert client.delete(f"/v1/automations/{auto_id}").status_code == 200


def test_agent_and_capy_automation_and_ssh_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agent import config as agent_config
    from agent_server.capy import bind_capy_deps
    from tools.automations import (
        automation_manage,
        ssh_bootstrap_remote_tool,
        ssh_exec_tool,
        ssh_hosts_tool,
        ssh_slurm_status_tool,
        ssh_sync_tool,
    )
    from tools.capy import capy_automation_manage, capy_ssh_manage

    monkeypatch.setattr(agent_config, "CONFIG_DIR", tmp_path)
    app = create_app(store_path=tmp_path / "agent-server.db")
    bind_capy_deps(app.state.deps)

    # 1. automation.manage tool actions
    tpl_res = automation_manage(action="templates")
    assert tpl_res["ok"] is True

    created_res = automation_manage(
        action="create",
        name="Tool Scheduled Check",
        schedule="every 2h",
        command="echo tool-ok",
        session_mode="no_agent",
        skills="ssh,automate",
        continuity=True,
    )
    assert created_res["ok"] is True
    aid = created_res["automation"]["id"]

    assert automation_manage(action="list")["count"] >= 1
    assert automation_manage(action="get", automation_id=aid)["ok"] is True
    assert (
        automation_manage(
            action="update",
            automation_id=aid,
            name="Updated Tool Check",
            schedule="every 3h",
        )["ok"]
        is True
    )
    assert automation_manage(action="pause", automation_id=aid)["ok"] is True
    assert automation_manage(action="resume", automation_id=aid)["ok"] is True
    assert automation_manage(action="run", automation_id=aid)["ok"] is True
    assert automation_manage(action="complete", automation_id=aid)["ok"] is True

    sess = app.state.deps.store.create_session(title="Snooze Target", workspace_path=None)
    assert automation_manage(action="snooze", session_id=sess.id)["snoozed"] is True
    assert automation_manage(action="unsnooze", session_id=sess.id)["snoozed"] is False
    assert automation_manage(action="remove", automation_id=aid)["ok"] is True

    # 2. Capy wrapper tools
    capy_res = capy_automation_manage(
        action="create",
        name="Capy Cron",
        schedule="daily at 9am",
        prompt="Morning check",
    )
    assert capy_res["ok"] is True

    # 3. SSH tools + Capy SSH tools
    add_res = ssh_hosts_tool(
        action="add",
        target="julio@hpc.edu:22",
        alias="hpc",
        default_workdir="/scratch/julio",
    )
    assert add_res["ok"] is True
    assert ssh_hosts_tool(action="list")["ok"] is True

    with (
        patch("agent_server.ssh_service.service.subprocess.run") as mock_run,
        patch.object(SshService, "open_tunnel", return_value=55111),
    ):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "HOSTNAME=hpc\nUNAME=Linux x86_64\nSLURM=1\nHEALTH_OK=1\n"
        m.stderr = ""
        mock_run.return_value = m

        assert ssh_hosts_tool(action="probe", target="hpc")["ok"] is True
        assert ssh_exec_tool(host="hpc", command="hostname")["ok"] is True
        assert ssh_slurm_status_tool(host="hpc")["ok"] is True
        assert (
            ssh_sync_tool(
                host="hpc", local_path=str(tmp_path), remote_path="/scratch/julio"
            )["ok"]
            is True
        )
        assert ssh_bootstrap_remote_tool(host="hpc")["ok"] is True
        assert capy_ssh_manage(action="list")["ok"] is True
        assert capy_ssh_manage(action="exec", host="hpc", command="uptime")["ok"] is True
        assert capy_ssh_manage(action="slurm", host="hpc")["ok"] is True

    assert ssh_hosts_tool(action="remove", target="hpc")["ok"] is True


def test_cli_cron_and_ssh_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from agent import config as agent_config
    from cli import app

    monkeypatch.setattr(agent_config, "CONFIG_DIR", tmp_path)
    runner = CliRunner()

    assert runner.invoke(app, ["cron", "templates"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "cron",
                "create",
                "every 30m",
                "Check cluster status",
                "--name",
                "CLI Watch",
                "--command",
                "echo cli-cron-ok",
                "--mode",
                "no_agent",
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["cron", "list"]).exit_code == 0
    assert runner.invoke(app, ["cron", "pause", "CLI Watch"]).exit_code == 0
    assert runner.invoke(app, ["cron", "resume", "CLI Watch"]).exit_code == 0
    assert runner.invoke(app, ["cron", "run", "CLI Watch"]).exit_code == 0
    assert runner.invoke(app, ["cron", "tick"]).exit_code == 0
    assert runner.invoke(app, ["cron", "remove", "CLI Watch"]).exit_code == 0

    assert (
        runner.invoke(
            app, ["ssh", "add", "julio@cluster.edu", "--alias", "cli-hpc"]
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["ssh", "list"]).exit_code == 0


def test_ssh_password_config_tunnel_and_edge_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = AgentStore(tmp_path / "ssh-extra.db")
    svc = SshService(store)

    # 1. SSH config file read/update/upsert block
    cfg_file = tmp_path / "ssh_config"
    read_cfg = svc.get_ssh_config_file(cfg_file)
    assert Path(read_cfg.path).exists()
    svc.update_ssh_config_file("# header\n", cfg_file)

    host = svc.create_host(
        CreateSshHostRequest(
            target="ssh -p 2222 -i ~/.ssh/id_test -J jumpbox user1@10.0.0.5",
            alias="custom-box",
            default_workdir="/home/user1",
        )
    )
    svc.upsert_ssh_config_block(host, cfg_file)
    assert "Host custom-box" in cfg_file.read_text(encoding="utf-8")
    # Calling upsert again is idempotent
    svc.upsert_ssh_config_block(host, cfg_file)

    # 2. Password auth helper (_install_ssh_key_with_password) & connect_and_bootstrap with password
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".ssh").mkdir(exist_ok=True)
    (tmp_path / ".ssh" / "id_ed25519.pub").write_text(
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey user@test\n",
        encoding="utf-8",
    )

    def fake_auth_run(args: list[str], **kwargs: object) -> MagicMock:
        cmd_str = " ".join(str(a) for a in args)
        m = MagicMock()
        if "AUTH_OK=1" in cmd_str:
            m.returncode = 0
            m.stdout = "AUTH_OK=1\n"
            m.stderr = ""
        elif "HOSTNAME=" in cmd_str:
            m.returncode = 0
            m.stdout = "HOSTNAME=custom-box\nUNAME=Linux x86_64\nSLURM=0\nHEALTH_OK=1\n"
            m.stderr = ""
        else:
            m.returncode = 0
            m.stdout = "PERSISTENCE=setsid-nohup\nHEALTH_OK=1\n"
            m.stderr = ""
        return m

    with (
        patch(
            "agent_server.ssh_service.service.subprocess.run",
            side_effect=fake_auth_run,
        ),
        patch.object(SshService, "open_tunnel", return_value=56789),
    ):
        res = svc.connect_and_bootstrap(
            SshConnectRequest(
                host_id_or_target=host.id,
                alias="renamed-box",
                password="secret-password",
                save_to_ssh_config=False,
                remote_port=8790,
                default_workdir="/tmp/work",
            )
        )
        assert res.key_installed is True
        assert res.auth_required is False
        assert res.local_url == "http://127.0.0.1:56789"

    # 3. Failed probe (Permission denied -> auth_required=True)
    with patch("agent_server.ssh_service.service.subprocess.run") as mock_fail:
        m_fail = MagicMock()
        m_fail.returncode = 255
        m_fail.stdout = ""
        m_fail.stderr = "Permission denied (publickey,password)."
        mock_fail.return_value = m_fail
        p_fail = svc.probe_host(host.id)
        assert p_fail.reachable is False
        assert p_fail.auth_required is True

        c_fail = svc.connect_and_bootstrap(
            SshConnectRequest(host_id_or_target=host.id, password="wrong")
        )
        assert c_fail.auth_required is True

    # 4. Tunnel open/close lifecycle with mocked Popen
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    with (
        patch("agent_server.ssh_service.service.subprocess.Popen", return_value=fake_proc),
        patch("agent_server.ssh_service.service._is_local_port_listening", return_value=True),
    ):
        lport = svc.open_tunnel(host.id)
        assert lport > 0
        # Second call reuses existing tunnel
        assert svc.open_tunnel(host.id) == lport
        listed = svc.list_hosts(include_ssh_config=False)
        assert any(h.status == "tunnel_active" for h in listed)
        assert svc.close_tunnel(host.id) is True


def test_automations_update_reconcile_and_route_errors(tmp_path: Path) -> None:
    app = create_app(store_path=tmp_path / "err-routes.db")
    client = TestClient(app)

    # Schedule parser additional branches (noon, midnight, PM, hourly, daily, weekly, weekends)
    assert parse_schedule("hourly").interval_seconds == 3600
    assert parse_schedule("daily").kind == "cron"
    assert parse_schedule("weekly").kind == "cron"
    assert parse_schedule("weekends at noon").cron_fields == ("0", "12", "*", "*", "0,6")
    assert parse_schedule("daily at midnight").cron_fields == ("0", "0", "*", "*", "*")
    assert parse_schedule("daily at 12:30am").cron_fields == ("30", "0", "*", "*", "*")
    assert parse_schedule("every 30s").interval_seconds == 30
    assert parse_schedule("every 1w").interval_seconds == 604800

    # Create automation from template & update all optional fields
    r_create = client.post(
        "/v1/automations",
        json={"templateId": "summarize-changes-daily"},
    )
    assert r_create.status_code == 201
    aid = r_create.json()["id"]

    r_patch = client.patch(
        f"/v1/automations/{aid}",
        json={
            "description": "Updated desc",
            "prompt": "New prompt",
            "clearCommand": True,
            "sessionMode": "continue",
            "clearOriginSessionId": True,
            "clearSpecialistId": True,
            "clearProjectId": True,
            "clearWorkdir": True,
            "clearSshHostId": True,
            "clearRemoteWorkdir": True,
            "skillNames": ["automate"],
            "toolNames": ["ops.automation_manage"],
            "mcpServerIds": ["omnigraph"],
            "providerPin": "openrouter",
            "modelPin": "gpt-5",
            "continuity": False,
            "contextFrom": ["up-1"],
            "wakeOnChangeOnly": False,
            "repeatLimit": 5,
            "enabled": False,
        },
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["enabled"] is False

    # Clear model pin & repeat limit, re-enable
    r_patch2 = client.patch(
        f"/v1/automations/{aid}",
        json={
            "clearModelPin": True,
            "clearRepeatLimit": True,
            "enabled": True,
        },
    )
    assert r_patch2.status_code == 200
    assert r_patch2.json()["enabled"] is True

    # Route 400 / 404 / SSH config endpoints
    assert (
        client.post(
            "/v1/automations", json={"scheduleExpr": "bad schedule"}
        ).status_code
        == 400
    )
    assert client.get("/v1/automations/missing-id").status_code == 404
    assert (
        client.patch(
            "/v1/automations/missing-id", json={"name": "x"}
        ).status_code
        == 404
    )
    assert client.delete("/v1/automations/missing-id").status_code == 404
    assert client.post("/v1/automations/missing-id/run").status_code == 404
    assert client.post("/v1/automations/webhook/bad-token").status_code == 404
    assert client.delete("/v1/ssh/hosts/missing-host").status_code == 404
    assert (
        client.patch(
            "/v1/ssh/hosts/missing-host", json={"alias": "x"}
        ).status_code
        == 404
    )
    assert client.get("/v1/ssh/config").status_code == 200

    # Reconcile orphaned runs + scheduler loop start/stop
    store = app.state.deps.store
    auto_svc = AutomationsService(store)
    orphan = store.create_automation_run(automation_id=aid, status="running")
    assert auto_svc.reconcile_orphaned_runs() >= 1
    assert store.list_automation_runs(automation_id=aid)[0].status == "failed"

    async def _run_brief_loop() -> None:
        task = asyncio.create_task(auto_svc.start_scheduler_loop(poll_seconds=0.05))
        await asyncio.sleep(0.08)
        auto_svc.stop_scheduler_loop()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(_run_brief_loop())



