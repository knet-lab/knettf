"""
Cilium / Hubble feedback interface.

Flow:
  1. policy_for_result() — pure logic, decides action from DetectionResult
  2. apply_action()      — STUB, sends action to Cilium (wire up when strategy is set)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from vigil.detection.base import DetectionResult

logger = logging.getLogger(__name__)

ACTIONS = {
    "drop":       "Block all traffic from source IP via CiliumNetworkPolicy",
    "rate_limit": "Apply per-IP rate limiting via CiliumNetworkPolicy",
    "alert":      "Log and alert only — no enforcement",
    "ignore":     "No action (normal traffic or low confidence)",
}

_ATTACK_TYPE_POLICY: dict[str, str] = {
    "syn_flood":  "drop",
    "flood":      "rate_limit",
    "port_scan":  "alert",
    "anomaly":    "alert",
}

_CONFIDENCE_THRESHOLD = 0.6


@dataclass
class CiliumAction:
    action: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    reason: str


def policy_for_result(result: DetectionResult, flow_meta: dict) -> CiliumAction:
    if not result.is_attack or result.confidence < _CONFIDENCE_THRESHOLD:
        action = "ignore"
    else:
        action = _ATTACK_TYPE_POLICY.get(result.attack_type or "anomaly", "alert")

    return CiliumAction(
        action=action,
        src_ip=flow_meta.get("src_ip", ""),
        dst_ip=flow_meta.get("dst_ip", ""),
        src_port=int(flow_meta.get("src_port", 0)),
        dst_port=int(flow_meta.get("dst_port", 0)),
        protocol=flow_meta.get("protocol", ""),
        reason=result.explanation or result.attack_type or "normal",
    )


def apply_action(action: CiliumAction) -> bool:
    """
    STUB — send enforcement action to Cilium.

    TODO: implement one of:
      A) kubectl apply a generated CiliumNetworkPolicy YAML
      B) Cilium/Hubble REST API call
      C) Write to a policy queue consumed by a sidecar
    """
    if action.action == "ignore":
        return True

    logger.info(
        "[CILIUM STUB] action=%s src=%s:%s proto=%s reason=%s",
        action.action, action.src_ip, action.src_port, action.protocol, action.reason,
    )
    # ── TODO ─────────────────────────────────────────────────────────────────
    # import subprocess, yaml, tempfile, os
    # policy = _build_cnp_yaml(action)
    # with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
    #     yaml.dump(policy, f); fname = f.name
    # rc = subprocess.run(["kubectl", "apply", "-f", fname], capture_output=True)
    # os.unlink(fname)
    # return rc.returncode == 0
    # ─────────────────────────────────────────────────────────────────────────
    return True


def _build_cnp_yaml(action: CiliumAction) -> dict:
    return {
        "apiVersion": "cilium.io/v2",
        "kind": "CiliumNetworkPolicy",
        "metadata": {"name": f"vigil-block-{action.src_ip.replace('.', '-')}"},
        "spec": {
            "endpointSelector": {},
            "ingressDeny": [{"fromCIDRSet": [{"cidr": f"{action.src_ip}/32"}]}],
        },
    }
