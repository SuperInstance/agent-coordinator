"""
Metrics Collector - Collects and aggregates performance data.
"""

import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import statistics
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentMetrics:
    """Metrics for a single agent."""
    agent_id: str

    # Task metrics
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_total: int = 0

    # Timing metrics (in seconds)
    total_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    min_execution_time: float = float('inf')
    max_execution_time: float = 0.0

    # Heartbeat
    last_heartbeat: Optional[datetime] = None
    heartbeat_count: int = 0

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: Optional[datetime] = None

    # Recent execution times for percentile calculation
    _recent_times: deque = field(default_factory=lambda: deque(maxlen=100))

    def record_heartbeat(self) -> None:
        """Record a heartbeat."""
        self.last_heartbeat = datetime.now()
        self.heartbeat_count += 1

    def task_started(self) -> None:
        """Record that a task was started."""
        self.tasks_total += 1
        self.last_activity = datetime.now()

    def task_completed(self, execution_time: float, success: bool) -> None:
        """
        Record that a task was completed.

        Args:
            execution_time: Time taken to complete the task
            success: Whether the task succeeded
        """
        self.last_activity = datetime.now()

        if success:
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1

        # Update timing metrics
        self.total_execution_time += execution_time
        self._recent_times.append(execution_time)

        if self.tasks_completed > 0:
            self.avg_execution_time = self.total_execution_time / self.tasks_completed

        self.min_execution_time = min(self.min_execution_time, execution_time)
        self.max_execution_time = max(self.max_execution_time, execution_time)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.tasks_total == 0:
            return 100.0
        return (self.tasks_completed / self.tasks_total) * 100

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as percentage."""
        if self.tasks_total == 0:
            return 0.0
        return (self.tasks_failed / self.tasks_total) * 100

    @property
    def p50_execution_time(self) -> Optional[float]:
        """Get median (p50) execution time."""
        if not self._recent_times:
            return None
        return statistics.median(self._recent_times)

    @property
    def p95_execution_time(self) -> Optional[float]:
        """Get p95 execution time."""
        if not self._recent_times:
            return None
        times = sorted(self._recent_times)
        index = int(len(times) * 0.95)
        return times[min(index, len(times) - 1)]

    @property
    def p99_execution_time(self) -> Optional[float]:
        """Get p99 execution time."""
        if not self._recent_times:
            return None
        times = sorted(self._recent_times)
        index = int(len(times) * 0.99)
        return times[min(index, len(times) - 1)]

    @property
    def tasks_per_minute(self) -> float:
        """Calculate tasks per minute rate."""
        if self.created_at == self.last_activity or self.last_activity is None:
            return 0.0

        duration = (self.last_activity - self.created_at).total_seconds()
        if duration == 0:
            return 0.0

        return (self.tasks_total / duration) * 60

    def to_dict(self) -> Dict[str, any]:
        """Convert metrics to dictionary."""
        return {
            "agent_id": self.agent_id,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tasks_total": self.tasks_total,
            "success_rate": round(self.success_rate, 2),
            "failure_rate": round(self.failure_rate, 2),
            "avg_execution_time": round(self.avg_execution_time, 3),
            "min_execution_time": round(self.min_execution_time, 3) if self.min_execution_time != float('inf') else 0,
            "max_execution_time": round(self.max_execution_time, 3),
            "p50_execution_time": round(self.p50_execution_time, 3) if self.p50_execution_time else None,
            "p95_execution_time": round(self.p95_execution_time, 3) if self.p95_execution_time else None,
            "p99_execution_time": round(self.p99_execution_time, 3) if self.p99_execution_time else None,
            "tasks_per_minute": round(self.tasks_per_minute, 2),
            "heartbeat_count": self.heartbeat_count,
            "uptime_seconds": (datetime.now() - self.created_at).total_seconds(),
        }


@dataclass
class SystemMetrics:
    """Aggregate metrics for the entire system."""
    total_agents: int = 0
    active_agents: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    # Aggregate timing
    avg_execution_time: float = 0.0

    # Throughput
    tasks_per_minute: float = 0.0

    # Timestamps
    timestamp: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """
    Collects and aggregates metrics from all agents.

    Features:
    - Per-agent metrics tracking
    - System-wide aggregation
    - Time-series data
    - Performance percentiles
    - Export to various formats
    """

    def __init__(self, retention_minutes: int = 60):
        self._retention_minutes = retention_minutes
        self._metrics: Dict[str, AgentMetrics] = {}
        self._history: deque = deque(maxlen=1000)  # System metrics snapshots

        # Callbacks
        self._on_metrics_updated: List[Callable[[str, AgentMetrics], None]] = []

    @property
    def agent_count(self) -> int:
        return len(self._metrics)

    def register_agent(self, agent_id: str) -> None:
        """Register an agent for metrics collection."""
        if agent_id not in self._metrics:
            self._metrics[agent_id] = AgentMetrics(agent_id=agent_id)
            logger.debug(f"Agent {agent_id} registered for metrics collection")

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from metrics collection."""
        self._metrics.pop(agent_id, None)
        logger.debug(f"Agent {agent_id} unregistered from metrics collection")

    def record_heartbeat(self, agent_id: str) -> None:
        """Record a heartbeat for an agent."""
        metrics = self._metrics.get(agent_id)
        if metrics:
            metrics.record_heartbeat()

    def record_task_start(self, agent_id: str) -> None:
        """Record that an agent started a task."""
        metrics = self._metrics.get(agent_id)
        if metrics:
            metrics.task_started()

    def record_task_complete(
        self,
        agent_id: str,
        execution_time: float,
        success: bool,
    ) -> None:
        """Record that an agent completed a task."""
        metrics = self._metrics.get(agent_id)
        if metrics:
            metrics.task_completed(execution_time, success)
            self._notify_updated(agent_id, metrics)

    def get_agent_metrics(self, agent_id: str) -> Optional[AgentMetrics]:
        """Get metrics for a specific agent."""
        return self._metrics.get(agent_id)

    def get_system_metrics(self) -> SystemMetrics:
        """Get aggregate system metrics."""
        if not self._metrics:
            return SystemMetrics()

        total_tasks = sum(m.tasks_total for m in self._metrics.values())
        completed_tasks = sum(m.tasks_completed for m in self._metrics.values())
        failed_tasks = sum(m.tasks_failed for m in self._metrics.values())

        # Average execution time across all agents
        total_exec_time = sum(m.total_execution_time for m in self._metrics.values())
        total_completed = sum(m.tasks_completed for m in self._metrics.values())
        avg_exec_time = total_exec_time / total_completed if total_completed > 0 else 0.0

        # Tasks per minute
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        recent_tasks = sum(
            m.tasks_total for m in self._metrics.values()
            if m.last_activity and m.last_activity >= one_minute_ago
        )

        return SystemMetrics(
            total_agents=len(self._metrics),
            active_agents=sum(
                1 for m in self._metrics.values()
                if m.last_activity and m.last_activity >= one_minute_ago
            ),
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            avg_execution_time=avg_exec_time,
            tasks_per_minute=recent_tasks,
        )

    def snapshot(self) -> Dict[str, any]:
        """Take a snapshot of all metrics."""
        return {
            "timestamp": datetime.now().isoformat(),
            "system": self.get_system_metrics(),
            "agents": {
                agent_id: metrics.to_dict()
                for agent_id, metrics in self._metrics.items()
            },
        }

    def take_snapshot(self) -> None:
        """Store a metrics snapshot in history."""
        snapshot = {
            "timestamp": datetime.now(),
            "metrics": self.get_system_metrics(),
        }
        self._history.append(snapshot)

    def get_history(self, minutes: int = 5) -> List[Dict[str, any]]:
        """Get historical metrics snapshots."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [
            {
                "timestamp": s["timestamp"].isoformat(),
                "metrics": s["metrics"].__dict__,
            }
            for s in self._history
            if s["timestamp"] >= cutoff
        ]

    def get_top_performers(self, n: int = 5) -> List[tuple[str, AgentMetrics]]:
        """Get top performing agents by task completion."""
        sorted_agents = sorted(
            self._metrics.items(),
            key=lambda x: x[1].tasks_completed,
            reverse=True,
        )
        return sorted_agents[:n]

    def get_slowest_agents(self, n: int = 5) -> List[tuple[str, AgentMetrics]]:
        """Get slowest agents by average execution time."""
        with_tasks = [
            (aid, m) for aid, m in self._metrics.items()
            if m.tasks_completed > 0
        ]
        sorted_agents = sorted(
            with_tasks,
            key=lambda x: x[1].avg_execution_time,
            reverse=True,
        )
        return sorted_agents[:n]

    def get_least_successful(self, n: int = 5) -> List[tuple[str, AgentMetrics]]:
        """Get agents with lowest success rate."""
        with_tasks = [
            (aid, m) for aid, m in self._metrics.items()
            if m.tasks_total > 0
        ]
        sorted_agents = sorted(
            with_tasks,
            key=lambda x: x[1].success_rate,
        )
        return sorted_agents[:n]

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        for agent_id, metrics in self._metrics.items():
            agent_id_safe = agent_id.replace("-", "_").replace(".", "_")

            lines.append(f'agent_tasks_total{{agent="{agent_id}"}} {metrics.tasks_total}')
            lines.append(f'agent_tasks_completed{{agent="{agent_id}"}} {metrics.tasks_completed}')
            lines.append(f'agent_tasks_failed{{agent="{agent_id}"}} {metrics.tasks_failed}')
            lines.append(f'agent_success_rate{{agent="{agent_id}"}} {metrics.success_rate:.2f}')
            lines.append(f'agent_avg_execution_time{{agent="{agent_id}"}} {metrics.avg_execution_time:.3f}')

        return "\n".join(lines)

    def export_json(self) -> Dict[str, any]:
        """Export metrics as JSON."""
        return self.snapshot()

    def reset_agent_metrics(self, agent_id: str) -> None:
        """Reset metrics for a specific agent."""
        if agent_id in self._metrics:
            old_created = self._metrics[agent_id].created_at
            self._metrics[agent_id] = AgentMetrics(agent_id=agent_id)
            self._metrics[agent_id].created_at = old_created

    def reset_all_metrics(self) -> None:
        """Reset all metrics."""
        old_agents = {
            aid: (m.created_at, m.agent_id)
            for aid, m in self._metrics.items()
        }
        self._metrics.clear()
        for aid, (created, agent_id) in old_agents.items():
            self._metrics[aid] = AgentMetrics(agent_id=agent_id)
            self._metrics[aid].created_at = created

    def add_updated_callback(self, callback: Callable[[str, AgentMetrics], None]) -> None:
        """Add callback for metrics updates."""
        self._on_metrics_updated.append(callback)

    def _notify_updated(self, agent_id: str, metrics: AgentMetrics) -> None:
        """Notify callbacks that metrics were updated."""
        for callback in self._on_metrics_updated:
            try:
                callback(agent_id, metrics)
            except Exception as e:
                logger.error(f"Metrics updated callback error: {e}")
