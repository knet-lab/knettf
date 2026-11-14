"""检测结果 → 处置动作（封禁 / 限速 / 告警）。目前 apply_action 是占位实现，只写日志。"""

from .cilium import ACTIONS, CiliumAction, apply_action, policy_for_result

__all__ = ["policy_for_result", "apply_action", "CiliumAction", "ACTIONS"]
