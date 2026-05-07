"""Multi-agent coordination framework with task distribution and health monitoring."""
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional
from enum import Enum

class AgentState(Enum):
    IDLE = "idle"
    WORKING = "working"
    BLOCKED = "blocked"
    OFFLINE = "offline"

@dataclass
class Agent:
    id: str
    name: str
    state: AgentState = AgentState.IDLE
    tasks_completed: int = 0
    health_score: float = 1.0

@dataclass
class Task:
    id: str
    description: str
    priority: int = 0
    assigned_to: Optional[str] = None
    status: str = "pending"

class Coordinator:
    """Coordinates multiple agents with task distribution and health monitoring."""
    
    def __init__(self):
        self.agents: dict[str, Agent] = {}
        self.tasks: dict[str, Task] = {}
        self.message_log: list[dict] = []
    
    def register(self, name: str) -> str:
        agent_id = str(uuid.uuid4())[:8]
        self.agents[agent_id] = Agent(id=agent_id, name=name)
        self._log("register", f"{name} registered as {agent_id}")
        return agent_id
    
    def send_message(self, from_id: str, to_id: str, message: str):
        self.message_log.append({
            "from": from_id, "to": to_id, "message": message, "time": time.time()
        })
        self._log("message", f"{from_id} -> {to_id}: {message}")
    
    def submit_task(self, description: str, priority: int = 0) -> str:
        task_id = str(uuid.uuid4())[:8]
        self.tasks[task_id] = Task(id=task_id, description=description, priority=priority)
        self._log("task", f"Submitted: {description}")
        return task_id
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        if task_id in self.tasks and agent_id in self.agents:
            self.tasks[task_id].assigned_to = agent_id
            self.agents[agent_id].state = AgentState.WORKING
            self._log("assign", f"Task {task_id} -> {agent_id}")
            return True
        return False
    
    def health_check(self, agent_id: str) -> dict:
        if agent_id not in self.agents:
            return {"error": "Agent not found"}
        agent = self.agents[agent_id]
        return {
            "id": agent_id, "name": agent.name, "state": agent.state.value,
            "tasks_completed": agent.tasks_completed, "health": agent.health_score
        }
    
    def _log(self, event: str, detail: str):
        print(f"[{event.upper()}] {detail}")

if __name__ == "__main__":
    coord = Coordinator()
    
    # Register 3 agents
    a1 = coord.register("CrewAlpha")
    a2 = coord.register("CrewBeta")
    a3 = coord.register("CrewGamma")
    
    # Submit tasks
    t1 = coord.submit_task("Scan horizon", priority=1)
    t2 = coord.submit_task("Check nets", priority=2)
    t3 = coord.submit_task("Log weather", priority=0)
    
    # Assign tasks
    coord.assign_task(t1, a1)
    coord.assign_task(t2, a2)
    
    # Agents exchange messages
    coord.send_message(a1, a2, "Nets look good, moving to assist")
    
    # Health checks
    for aid in [a1, a2, a3]:
        print(coord.health_check(aid))