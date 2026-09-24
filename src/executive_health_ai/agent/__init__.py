"""Bounded, approval-aware, long-running HealthOps orchestration."""

__all__ = ["HealthOpsAgentSupervisor"]


def __getattr__(name):
    if name == 'HealthOpsAgentSupervisor':
        from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
        return HealthOpsAgentSupervisor
    raise AttributeError(name)
