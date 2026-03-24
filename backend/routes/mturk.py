from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Tuple

from flask import Blueprint, jsonify, request

import routes.session as session_module

try:
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - defensive import fallback
    BotoCoreError = Exception
    ClientError = Exception


mturk_bp = Blueprint("mturk", __name__)


def _find_session_by_identifier(session_identifier: str):
    from urllib.parse import unquote

    identifier = unquote(session_identifier)
    if identifier in session_module.sessions:
        return identifier, session_module.sessions[identifier]
    for sid, session in session_module.sessions.items():
        if session.get("session_name", "").lower() == identifier.lower():
            return sid, session
    return None, None


def _normalize_environment(env: str | None) -> str:
    raw = (env or os.environ.get("MTURK_ENVIRONMENT") or "sandbox").strip().lower()
    return "production" if raw in ("prod", "production", "live") else "sandbox"


def _mturk_endpoint_for_env(environment: str) -> str:
    if environment == "production":
        return "https://mturk-requester.us-east-1.amazonaws.com"
    return "https://mturk-requester-sandbox.us-east-1.amazonaws.com"


def _get_mturk_client(environment: str):
    import boto3

    region = (os.environ.get("AWS_REGION") or "us-east-1").strip()
    endpoint = _mturk_endpoint_for_env(environment)
    return boto3.client("mturk", region_name=region, endpoint_url=endpoint)


def _error_response(prefix: str, exc: Exception, status: int = 500):
    return jsonify({"success": False, "error": f"{prefix}: {exc}"}), status


@mturk_bp.route("/api/mturk/sessions/<path:session_identifier>/associate", methods=["POST"])
def associate_hit(session_identifier):
    try:
        data = request.get_json() or {}
        hit_id = (data.get("hit_id") or "").strip()
        if not hit_id:
            return jsonify({"success": False, "error": "hit_id is required"}), 400

        session_key, found_session = _find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({"success": False, "error": "Session not found"}), 404

        environment = _normalize_environment(data.get("environment"))
        region = (os.environ.get("AWS_REGION") or "us-east-1").strip()
        found_session["mturk"] = {
            "hit_id": hit_id,
            "environment": environment,
            "region": region,
            "associated_at": datetime.now().isoformat(),
        }
        session_module.commit_session(session_key, found_session)
        return jsonify({"success": True, "mturk": found_session["mturk"]}), 200
    except Exception as exc:
        return _error_response("Failed to associate HIT", exc)


@mturk_bp.route("/api/mturk/sessions/<path:session_identifier>/config", methods=["GET"])
def get_mturk_config(session_identifier):
    try:
        _, found_session = _find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({"success": False, "error": "Session not found"}), 404
        return jsonify({"success": True, "mturk": found_session.get("mturk", {})}), 200
    except Exception as exc:
        return _error_response("Failed to fetch MTurk config", exc)


@mturk_bp.route("/api/mturk/sessions/<path:session_identifier>/assignments", methods=["GET"])
def list_assignments(session_identifier):
    try:
        _, found_session = _find_session_by_identifier(session_identifier)
        if not found_session:
            return jsonify({"success": False, "error": "Session not found"}), 404

        mturk_cfg = found_session.get("mturk") or {}
        hit_id = (mturk_cfg.get("hit_id") or "").strip()
        if not hit_id:
            return jsonify({"success": False, "error": "No associated HIT for this session"}), 400

        environment = _normalize_environment(mturk_cfg.get("environment"))
        client = _get_mturk_client(environment)

        assignments = []
        next_token = None
        while True:
            kwargs: Dict = {
                "HITId": hit_id,
                "AssignmentStatuses": ["Submitted", "Approved", "Rejected"],
                "MaxResults": 100,
            }
            if next_token:
                kwargs["NextToken"] = next_token
            resp = client.list_assignments_for_hit(**kwargs)
            for row in resp.get("Assignments", []):
                assignments.append(
                    {
                        "assignment_id": row.get("AssignmentId"),
                        "worker_id": row.get("WorkerId"),
                        "status": row.get("AssignmentStatus"),
                        "submit_time": row.get("SubmitTime").isoformat() if row.get("SubmitTime") else None,
                        "accept_time": row.get("AcceptTime").isoformat() if row.get("AcceptTime") else None,
                        "answer_xml": row.get("Answer"),
                    }
                )
            next_token = resp.get("NextToken")
            if not next_token:
                break

        return jsonify({"success": True, "hit_id": hit_id, "assignments": assignments}), 200
    except (BotoCoreError, ClientError) as exc:
        return _error_response("MTurk API error while listing assignments", exc, 502)
    except Exception as exc:
        return _error_response("Failed to list assignments", exc)


@mturk_bp.route("/api/mturk/assignments/<assignment_id>/approve", methods=["POST"])
def approve_assignment(assignment_id):
    try:
        data = request.get_json(silent=True) or {}
        environment = _normalize_environment(data.get("environment"))
        feedback = (data.get("requester_feedback") or "Approved via Researcher Dashboard").strip()
        client = _get_mturk_client(environment)
        client.approve_assignment(
            AssignmentId=assignment_id,
            RequesterFeedback=feedback,
            OverrideRejection=False,
        )
        return jsonify({"success": True, "assignment_id": assignment_id}), 200
    except (BotoCoreError, ClientError) as exc:
        return _error_response("MTurk API error while approving assignment", exc, 502)
    except Exception as exc:
        return _error_response("Failed to approve assignment", exc)


@mturk_bp.route("/api/mturk/assignments/<assignment_id>/reject", methods=["POST"])
def reject_assignment(assignment_id):
    try:
        data = request.get_json() or {}
        reason = (data.get("reason") or "").strip()
        if not reason:
            return jsonify({"success": False, "error": "reason is required"}), 400

        environment = _normalize_environment(data.get("environment"))
        client = _get_mturk_client(environment)
        client.reject_assignment(
            AssignmentId=assignment_id,
            RequesterFeedback=reason,
        )
        return jsonify({"success": True, "assignment_id": assignment_id}), 200
    except (BotoCoreError, ClientError) as exc:
        return _error_response("MTurk API error while rejecting assignment", exc, 502)
    except Exception as exc:
        return _error_response("Failed to reject assignment", exc)
