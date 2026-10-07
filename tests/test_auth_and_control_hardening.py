"""
Unit and Integration Tests for API Authentication, RBAC, SCADA Command Allowlist,
Query Bounds, and Path Traversal Hardening.
"""

import os
import sys
import pytest
from starlette.testclient import TestClient

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import config
from backend.main import app, SUPPORTED_SCADA_COMMANDS


@pytest.fixture(autouse=True)
def reset_config_state():
    """Ensure config is cleanly reset around tests."""
    orig_auth_enabled = config.API_AUTH_ENABLED
    orig_admin_key = config.API_ADMIN_KEY
    orig_operator_key = config.API_OPERATOR_KEY
    orig_viewer_key = config.API_VIEWER_KEY

    yield

    config.API_AUTH_ENABLED = orig_auth_enabled
    config.API_ADMIN_KEY = orig_admin_key
    config.API_OPERATOR_KEY = orig_operator_key
    config.API_VIEWER_KEY = orig_viewer_key


def test_demo_mode_unrestricted_access():
    """In DEMO MODE (API_AUTH_ENABLED=False), control endpoints are accessible for evaluation."""
    config.API_AUTH_ENABLED = False
    client = TestClient(app)

    # Calling SCADA command without headers succeeds in demo mode
    resp = client.post("/api/command", json={"command": "TEST_ALARM"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert resp.json()["command"] == "TEST_ALARM"

    # Status/monitoring endpoint succeeds
    resp_v = client.get("/api/vehicles")
    assert resp_v.status_code == 200


def test_secure_mode_unauthenticated_request_rejected_401():
    """In SECURE MODE (API_AUTH_ENABLED=True), unauthenticated requests return 401."""
    config.API_AUTH_ENABLED = True
    config.API_ADMIN_KEY = "test_admin_key_999"
    config.API_OPERATOR_KEY = "test_operator_key_888"
    config.API_VIEWER_KEY = "test_viewer_key_777"
    client = TestClient(app)

    resp = client.post("/api/command", json={"command": "EMERGENCY_ALERT"})
    assert resp.status_code == 401
    assert "Authentication credentials required" in resp.json()["detail"]


def test_secure_mode_invalid_token_rejected_401():
    """In SECURE MODE, requests with invalid API key return 401."""
    config.API_AUTH_ENABLED = True
    config.API_ADMIN_KEY = "test_admin_key_999"
    client = TestClient(app)

    resp = client.post(
        "/api/command",
        headers={"X-API-Key": "completely_wrong_key"},
        json={"command": "EMERGENCY_ALERT"}
    )
    assert resp.status_code == 401
    assert "Invalid authentication token" in resp.json()["detail"]


def test_secure_mode_viewer_cannot_call_operator_or_admin_endpoints_403():
    """Viewer role (level 1) can read data but cannot dispatch commands or demo triggers."""
    config.API_AUTH_ENABLED = True
    config.API_ADMIN_KEY = "test_admin_key_999"
    config.API_OPERATOR_KEY = "test_operator_key_888"
    config.API_VIEWER_KEY = "test_viewer_key_777"
    client = TestClient(app)

    headers = {"X-API-Key": "test_viewer_key_777"}

    # Viewer can read vehicles
    resp_read = client.get("/api/vehicles", headers=headers)
    assert resp_read.status_code == 200

    # Viewer cannot dispatch command (requires operator)
    resp_cmd = client.post("/api/command", headers=headers, json={"command": "SLOW_DOWN"})
    assert resp_cmd.status_code == 403
    assert "Requires 'operator' role or higher" in resp_cmd.json()["detail"]

    # Viewer cannot trigger demo (requires admin)
    resp_demo = client.post("/api/demo", headers=headers)
    assert resp_demo.status_code == 403
    assert "Requires 'admin' role or higher" in resp_demo.json()["detail"]


def test_secure_mode_operator_role_permissions():
    """Operator role (level 2) can dispatch commands and generate reports, but cannot trigger demo."""
    config.API_AUTH_ENABLED = True
    config.API_ADMIN_KEY = "test_admin_key_999"
    config.API_OPERATOR_KEY = "test_operator_key_888"
    config.API_VIEWER_KEY = "test_viewer_key_777"
    client = TestClient(app)

    headers = {"Authorization": "Bearer test_operator_key_888"}

    # Operator can send SCADA commands
    resp_cmd = client.post("/api/command", headers=headers, json={"command": "SLOW_DOWN"})
    assert resp_cmd.status_code == 200
    assert resp_cmd.json()["status"] == "success"

    # Operator can generate report
    resp_report = client.post("/api/report", headers=headers)
    assert resp_report.status_code == 200

    # Operator cannot run admin-only spoof test
    resp_spoof = client.post("/api/spoof", headers=headers)
    assert resp_spoof.status_code == 403


def test_secure_mode_admin_role_permissions():
    """Admin role (level 3) has full access across all endpoints."""
    config.API_AUTH_ENABLED = True
    config.API_ADMIN_KEY = "test_admin_key_999"
    client = TestClient(app)

    headers = {"X-API-Key": "test_admin_key_999"}

    # Admin can trigger spoof attack simulation
    resp_spoof = client.post("/api/spoof", headers=headers)
    assert resp_spoof.status_code == 200

    # Admin can issue SCADA command
    resp_cmd = client.post("/api/command", headers=headers, json={"command": "STOP_WARNING"})
    assert resp_cmd.status_code == 200


def test_command_allowlist_validation():
    """Only defined SCADA commands are permitted; arbitrary commands are rejected with 400."""
    config.API_AUTH_ENABLED = False
    client = TestClient(app)

    # Valid commands
    for valid_cmd in ["EMERGENCY_ALERT", "SLOW_DOWN", "STOP_WARNING", "YIELD_TO_EMERGENCY", "TEST_ALARM"]:
        resp = client.post("/api/command", json={"command": valid_cmd})
        assert resp.status_code == 200

    # Command injection attempt
    resp_inj = client.post("/api/command", json={"command": "rm -rf /; reboot"})
    assert resp_inj.status_code == 400
    assert "Unsupported SCADA command" in resp_inj.json()["detail"]

    # Unknown command
    resp_unk = client.post("/api/command", json={"command": "ARBITRARY_UNKNOWN_CMD"})
    assert resp_unk.status_code == 400


def test_download_report_path_traversal_and_filename_hardening():
    """Report download rejects directory traversal and non-PDF file patterns."""
    config.API_AUTH_ENABLED = False
    client = TestClient(app)

    # Non-existent report with valid syntax returns 404
    resp = client.get("/api/download/nonexistent_report_123.pdf")
    assert resp.status_code == 404

    # Traversal attempts return 400
    traversal_payloads = [
        "../.env",
        "..%2f..%2fetc%2fpasswd",
        "nested/path.pdf",
        "malicious.exe",
        "secret.txt",
        "report.pdf.exe",
        "../../../v2v.db",
    ]
    for payload in traversal_payloads:
        resp_t = client.get(f"/api/download/{payload}")
        assert resp_t.status_code in (400, 404)


def test_query_limit_bounds_validation():
    """Verify limit query parameter is bounded between 1 and 500."""
    config.API_AUTH_ENABLED = False
    client = TestClient(app)

    # Out of bounds (< 1)
    resp_low = client.get("/api/incidents?limit=0")
    assert resp_low.status_code == 422

    # Out of bounds (> 500)
    resp_high = client.get("/api/incidents?limit=501")
    assert resp_high.status_code == 422

    # Valid in bounds
    resp_ok = client.get("/api/incidents?limit=50")
    assert resp_ok.status_code == 200
