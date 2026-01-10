"""
Network Monitor - Tracks agent health and connectivity.
"""

import asyncio
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

from agent_coordinator.agent import Agent, AgentState

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status for agents."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    OFFLINE = "offline"


@dataclass
class AgentHealth:
    """Health information for an agent."""
    agent_id: str
    status: HealthStatus
    last_heartbeat: Optional[datetime] = None
    last_state_change: Optional[datetime] = None
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)

    @property
    def heartbeat_age_seconds(self) -> Optional[float]:
        if self.last_heartbeat is None:
            return None
        return (datetime.now() - self.last_heartbeat).total_seconds()

    @property
    def is_stale(self, timeout: float = 60.0) -> bool:
        """Check if heartbeat is stale."""
        if self.last_heartbeat is None:
            return True
        return self.heartbeat_age_seconds > timeout


@dataclass
class SystemHealth:
    """Overall system health."""
    status: HealthStatus
    total_agents: int
    healthy_agents: int
    degraded_agents: int
    unhealthy_agents: int
    offline_agents: int
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def health_percentage(self) -> float:
        if self.total_agents == 0:
            return 100.0
        return (self.healthy_agents / self.total_agents) * 100


class NetworkMonitor:
    """
    Monitors the health and connectivity of agents.

    Features:
    - Heartbeat tracking
    - Health status calculation
    - Failure detection
    - Auto-recovery triggers
    - Health metrics collection
    """

    def __init__(
        self,
        heartbeat_timeout: float = 60.0,
        health_check_interval: float = 30.0,
    ):
        self._heartbeat_timeout = heartbeat_timeout
        self._health_check_interval = health_check_interval

        # Health tracking
        self._agent_health: Dict[str, AgentHealth] = {}

        # Monitoring state
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False

        # Event callbacks
        self._on_health_change: List[Callable[[str, HealthStatus], None]] = []
        self._on_agent_offline: List[Callable[[str], None]] = []
        self._on_agent_recovered: List[Callable[[str], None]] = []
        self._on_failure_detected: List[Callable[[str, str], None]] = []

    @property
    def is_monitoring(self) -> bool:
        return self._is_monitoring

    def add_health_change_callback(self, callback: Callable[[str, HealthStatus], None]) -> None:
        self._on_health_change.append(callback)

    def add_offline_callback(self, callback: Callable[[str], None]) -> None:
        self._on_agent_offline.append(callback)

    def add_recovery_callback(self, callback: Callable[[str], None]) -> None:
        self._on_agent_recovered.append(callback)

    def add_failure_callback(self, callback: Callable[[str, str], None]) -> None:
        self._on_failure_detected.append(callback)

    async def start(self) -> None:
        """Start the health monitor."""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("Network monitor started")

    async def stop(self) -> None:
        """Stop the health monitor."""
        self._is_monitoring = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Network monitor stopped")

    def register_agent(self, agent_id: str) -> None:
        """Register an agent for monitoring."""
        if agent_id not in self._agent_health:
            self._agent_health[agent_id] = AgentHealth(
                agent_id=agent_id,
                status=HealthStatus.UNKNOWN,
                last_heartbeat=datetime.now(),
            )
            logger.debug(f"Agent {agent_id} registered for monitoring")

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from monitoring."""
        self._agent_health.pop(agent_id, None)
        logger.debug(f"Agent {agent_id} unregistered from monitoring")

    def record_heartbeat(self, agent_id: str) -> None:
        """Record a heartbeat from an agent."""
        if agent_id not in self._agent_health:
            self.register_agent(agent_id)

        health = self._agent_health[agent_id]
        was_stale = health.is_stale(self._heartbeat_timeout)

        health.last_heartbeat = datetime.now()

        # If agent was stale, it might have recovered
        if was_stale:
            self._update_health_status(agent_id, HealthStatus.HEALTHY)
            self._notify_recovery(agent_id)

    def record_state_change(self, agent_id: str, new_state: AgentState) -> None:
        """Record a state change for an agent."""
        if agent_id not in self._agent_health:
            self.register_agent(agent_id)

        health = self._agent_health[agent_id]
        health.last_state_change = datetime.now()

        # Update health based on state
        if new_state == AgentState.FAILED:
            self._record_failure(agent_id, "Agent state: FAILED")
            self._update_health_status(agent_id, HealthStatus.UNHEALTHY)
        elif new_state == AgentState.IDLE:
            self._update_health_status(agent_id, HealthStatus.HEALTHY)
        elif new_state == AgentState.BUSY:
            self._update_health_status(agent_id, HealthStatus.HEALTHY)
        elif new_state == AgentState.TERMINATED:
            self._update_health_status(agent_id, HealthStatus.OFFLINE)

    def record_failure(self, agent_id: str, error: str) -> None:
        """Record a failure for an agent."""
        self._record_failure(agent_id, error)

        # Update health
        health = self._agent_health.get(agent_id)
        if health:
            health.consecutive_failures += 1
            health.last_error = error

            if health.consecutive_failures >= 3:
                self._update_health_status(agent_id, HealthStatus.UNHEALTHY)
            else:
                self._update_health_status(agent_id, HealthStatus.DEGRADED)

    def get_health(self, agent_id: str) -> Optional[AgentHealth]:
        """Get health information for an agent."""
        return self._agent_health.get(agent_id)

    def get_system_health(self) -> SystemHealth:
        """Get overall system health."""
        total = len(self._agent_health)
        healthy = sum(1 for h in self._agent_health.values() if h.status == HealthStatus.HEALTHY)
        degraded = sum(1 for h in self._agent_health.values() if h.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for h in self._agent_health.values() if h.status == HealthStatus.UNHEALTHY)
        offline = sum(1 for h in self._agent_health.values() if h.status == HealthStatus.OFFLINE)

        # Determine overall status
        if total == 0:
            status = HealthStatus.UNKNOWN
        elif offline > 0:
            status = HealthStatus.DEGRADED
        elif unhealthy > total / 2:
            status = HealthStatus.UNHEALTHY
        elif degraded > total / 2:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        return SystemHealth(
            status=status,
            total_agents=total,
            healthy_agents=healthy,
            degraded_agents=degraded,
            unhealthy_agents=unhealthy,
            offline_agents=offline,
        )

    def get_unhealthy_agents(self) -> List[str]:
        """Get list of unhealthy agent IDs."""
        return [
            aid for aid, health in self._agent_health.items()
            if health.status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)
        ]

    def get_offline_agents(self) -> List[str]:
        """Get list of offline agent IDs."""
        return [
            aid for aid, health in self._agent_health.items()
            if health.status == HealthStatus.OFFLINE or health.is_stale(self._heartbeat_timeout)
        ]

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while self._is_monitoring:
                await asyncio.sleep(self._health_check_interval)
                await self._health_check()

        except asyncio.CancelledError:
            logger.debug("Network monitor loop cancelled")
        except Exception as e:
            logger.error(f"Network monitor loop error: {e}")

    async def _health_check(self) -> None:
        """Perform health check on all agents."""
        now = datetime.now()

        for agent_id, health in self._agent_health.items():
            # Check for stale heartbeats
            if health.is_stale(self._heartbeat_timeout):
                if health.status != HealthStatus.OFFLINE:
                    self._update_health_status(agent_id, HealthStatus.OFFLINE)
                    self._notify_offline(agent_id)

    def _update_health_status(self, agent_id: str, status: HealthStatus) -> None:
        """Update health status and notify callbacks."""
        health = self._agent_health.get(agent_id)
        if health is None:
            return

        old_status = health.status
        health.status = status

        if old_status != status:
            logger.debug(f"Agent {agent_id} health: {old_status.value} -> {status.value}")

            for callback in self._on_health_change:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(agent_id, status))
                    else:
                        callback(agent_id, status)
                except Exception as e:
                    logger.error(f"Health change callback error: {e}")

    def _record_failure(self, agent_id: str, error: str) -> None:
        """Record a failure and notify callbacks."""
        for callback in self._on_failure_detected:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(agent_id, error))
                else:
                    callback(agent_id, error)
            except Exception as e:
                logger.error(f"Failure callback error: {e}")

    def _notify_offline(self, agent_id: str) -> None:
        """Notify callbacks that an agent went offline."""
        logger.warning(f"Agent {agent_id} is offline")

        for callback in self._on_agent_offline:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(agent_id))
                else:
                    callback(agent_id)
            except Exception as e:
                logger.error(f"Offline callback error: {e}")

    def _notify_recovery(self, agent_id: str) -> None:
        """Notify callbacks that an agent recovered."""
        logger.info(f"Agent {agent_id} has recovered")

        # Reset failure count
        health = self._agent_health.get(agent_id)
        if health:
            health.consecutive_failures = 0

        for callback in self._on_agent_recovered:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(agent_id))
                else:
                    callback(agent_id)
            except Exception as e:
                logger.error(f"Recovery callback error: {e}")
