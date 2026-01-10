"""
Agent Registry - Tracks all agents and their capabilities.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import logging

from agent_coordinator.agent import Agent, AgentState, AgentRole
from agent_coordinator.events import Event, EventType

logger = logging.getLogger(__name__)


@dataclass
class AgentInfo:
    """Information about a registered agent."""
    agent_id: str
    role: str
    capabilities: List[str]
    state: AgentState
    registered_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: Optional[datetime] = None
    metadata: Dict[str, None] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return (datetime.now() - self.registered_at).total_seconds()

    @property
    def heartbeat_age_seconds(self) -> Optional[float]:
        if self.last_heartbeat is None:
            return None
        return (datetime.now() - self.last_heartbeat).total_seconds()


class AgentRegistry:
    """
    Registry for tracking all agents in the system.

    The registry maintains:
    - All registered agents
    - Agent roles and capabilities
    - Agent states and health
    - Lookup by various criteria
    """

    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._roles: Dict[str, AgentRole] = {}
        self._agent_info: Dict[str, AgentInfo] = {}
        self._lock = asyncio.Lock()

        # Indexes
        self._by_role: Dict[str, Set[str]] = {}
        self._by_capability: Dict[str, Set[str]] = {}
        self._by_state: Dict[AgentState, Set[str]] = {state: set() for state in AgentState}

        # Event callbacks
        self._on_agent_registered: List[callable] = []
        self._on_agent_unregistered: List[callable] = []
        self._on_agent_state_changed: List[callable] = []

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    @property
    def role_count(self) -> int:
        return len(self._roles)

    @property
    def agent_ids(self) -> List[str]:
        return list(self._agents.keys())

    def add_registration_callback(self, callback: callable) -> None:
        """Add callback for agent registration events."""
        self._on_agent_registered.append(callback)

    def add_unregistration_callback(self, callback: callable) -> None:
        """Add callback for agent unregistration events."""
        self._on_agent_unregistered.append(callback)

    def add_state_change_callback(self, callback: callable) -> None:
        """Add callback for agent state change events."""
        self._on_agent_state_changed.append(callback)

    async def register_role(self, role: AgentRole) -> None:
        """Register a new agent role."""
        async with self._lock:
            if role.name in self._roles:
                logger.warning(f"Role {role.name} already registered, updating")
            self._roles[role.name] = role
            logger.info(f"Registered role: {role.name}")

    def get_role(self, role_name: str) -> Optional[AgentRole]:
        """Get a role by name."""
        return self._roles.get(role_name)

    def get_all_roles(self) -> List[AgentRole]:
        """Get all registered roles."""
        return list(self._roles.values())

    async def register(self, agent: Agent) -> None:
        """Register an agent."""
        async with self._lock:
            agent_id = agent.id

            if agent_id in self._agents:
                logger.warning(f"Agent {agent_id} already registered")
                return

            self._agents[agent_id] = agent

            # Create agent info
            self._agent_info[agent_id] = AgentInfo(
                agent_id=agent_id,
                role=agent.role.name,
                capabilities=agent.capabilities,
                state=agent.state,
            )

            # Update indexes
            self._update_indexes(agent_id, agent, added=True)

            # Add state change callback
            agent.add_state_change_callback(
                lambda state: asyncio.create_task(self._on_state_change(agent_id, state))
            )

            # Notify callbacks
            for callback in self._on_agent_registered:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(agent)
                    else:
                        callback(agent)
                except Exception as e:
                    logger.error(f"Registration callback error: {e}")

            logger.info(f"Registered agent: {agent_id} (role: {agent.role.name})")

    async def unregister(self, agent_id: str) -> Optional[Agent]:
        """Unregister an agent."""
        async with self._lock:
            agent = self._agents.pop(agent_id, None)

            if agent is None:
                logger.warning(f"Agent {agent_id} not found for unregistration")
                return None

            # Update indexes
            self._update_indexes(agent_id, agent, added=False)

            # Remove agent info
            self._agent_info.pop(agent_id, None)

            # Notify callbacks
            for callback in self._on_agent_unregistered:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(agent)
                    else:
                        callback(agent)
                except Exception as e:
                    logger.error(f"Unregistration callback error: {e}")

            logger.info(f"Unregistered agent: {agent_id}")
            return agent

    def get(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_info(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent info by ID."""
        return self._agent_info.get(agent_id)

    def get_by_role(self, role: str) -> List[Agent]:
        """Get all agents with a specific role."""
        agent_ids = self._by_role.get(role, set())
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get_by_capability(self, capability: str) -> List[Agent]:
        """Get all agents with a specific capability."""
        agent_ids = self._by_capability.get(capability, set())
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get_by_state(self, state: AgentState) -> List[Agent]:
        """Get all agents in a specific state."""
        agent_ids = self._by_state.get(state, set())
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get_available(self) -> List[Agent]:
        """Get all available (idle) agents."""
        return self.get_by_state(AgentState.IDLE)

    def get_by_capabilities(self, required_capabilities: List[str]) -> List[Agent]:
        """Get agents that have all the required capabilities."""
        agents = []
        for agent in self._agents.values():
            if all(cap in agent.capabilities for cap in required_capabilities):
                agents.append(agent)
        return agents

    def find_best_agent(
        self,
        required_capabilities: List[str] = None,
        preferred_role: str = None,
        exclude: List[str] = None,
    ) -> Optional[Agent]:
        """
        Find the best available agent for a task.

        Args:
            required_capabilities: Required agent capabilities
            preferred_role: Preferred agent role
            exclude: Agent IDs to exclude

        Returns:
            The best available agent or None
        """
        exclude = exclude or []
        required_capabilities = required_capabilities or []

        # Filter by state (must be idle)
        candidates = self.get_available()

        # Filter by exclusion list
        candidates = [a for a in candidates if a.id not in exclude]

        # Filter by capabilities
        if required_capabilities:
            candidates = [
                a for a in candidates
                if all(cap in a.capabilities for cap in required_capabilities)
            ]

        # Filter by role if specified
        if preferred_role:
            role_candidates = [a for a in candidates if a.role.name == preferred_role]
            if role_candidates:
                candidates = role_candidates

        if not candidates:
            return None

        # Prefer agents with fewer current tasks
        return min(candidates, key=lambda a: a.current_task_count)

    def exists(self, agent_id: str) -> bool:
        """Check if an agent is registered."""
        return agent_id in self._agents

    def role_exists(self, role_name: str) -> bool:
        """Check if a role is registered."""
        return role_name in self._roles

    async def _on_state_change(self, agent_id: str, new_state: AgentState) -> None:
        """Handle agent state change."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return

        async with self._lock:
            # Update state indexes
            for state in AgentState:
                if agent_id in self._by_state[state]:
                    self._by_state[state].discard(agent_id)

            self._by_state[new_state].add(agent_id)

            # Update agent info
            info = self._agent_info.get(agent_id)
            if info:
                info.state = new_state

            # Notify callbacks
            for callback in self._on_agent_state_changed:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(agent_id, new_state)
                    else:
                        callback(agent_id, new_state)
                except Exception as e:
                    logger.error(f"State change callback error: {e}")

    def _update_indexes(self, agent_id: str, agent: Agent, added: bool) -> None:
        """Update internal indexes when an agent is added or removed."""
        role_name = agent.role.name

        if added:
            # Role index
            if role_name not in self._by_role:
                self._by_role[role_name] = set()
            self._by_role[role_name].add(agent_id)

            # Capability index
            for cap in agent.capabilities:
                if cap not in self._by_capability:
                    self._by_capability[cap] = set()
                self._by_capability[cap].add(agent_id)

            # State index
            self._by_state[agent.state].add(agent_id)
        else:
            # Remove from all indexes
            self._by_role.get(role_name, set()).discard(agent_id)
            for cap in agent.capabilities:
                self._by_capability.get(cap, set()).discard(agent_id)
            self._by_state[agent.state].discard(agent_id)

    def get_status_summary(self) -> Dict[str, any]:
        """Get a summary of registry status."""
        return {
            "total_agents": self.agent_count,
            "total_roles": self.role_count,
            "by_state": {
                state.value: len(self._by_state[state])
                for state in AgentState
            },
            "by_role": {
                role: len(agents)
                for role, agents in self._by_role.items()
            },
            "available": len(self.get_available()),
        }
