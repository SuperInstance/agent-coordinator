"""
Visualization - Network visualization and dashboard support.
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import asyncio

from agent_coordinator.coordinator import AgentCoordinator
from agent_coordinator.agent import Agent, AgentState
from agent_coordinator.task import Task, TaskStatus

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import networkx as nx
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


@dataclass
class NodeStyle:
    """Style for a node in the network graph."""
    color: str = "#4a9eff"
    size: int = 500
    shape: str = "o"
    label: str = ""


@dataclass
class EdgeStyle:
    """Style for an edge in the network graph."""
    color: str = "#999999"
    width: float = 1.0
    style: str = "solid"


class NetworkVisualizer:
    """
    Visualizes agent networks and communication patterns.

    Requires matplotlib and networkx to be installed.
    """

    def __init__(self, coordinator: AgentCoordinator):
        self.coordinator = coordinator
        self._node_styles: Dict[str, NodeStyle] = {}
        self._edge_styles: Dict[Tuple[str, str], EdgeStyle] = {}

        # Color schemes
        self._state_colors = {
            AgentState.IDLE: "#4CAF50",
            AgentState.BUSY: "#FF9800",
            AgentState.FAILED: "#F44336",
            AgentState.TERMINATED: "#9E9E9E",
            AgentState.INITIALIZING: "#2196F3",
            AgentState.SUSPENDED: "#FFC107",
        }

    def set_node_style(self, agent_id: str, style: NodeStyle) -> None:
        """Set custom style for a node."""
        self._node_styles[agent_id] = style

    def set_edge_style(self, from_agent: str, to_agent: str, style: EdgeStyle) -> None:
        """Set custom style for an edge."""
        self._edge_styles[(from_agent, to_agent)] = style

    def build_network_graph(self) -> Optional["nx.Graph"]:
        """Build a NetworkX graph from the coordinator state."""
        if not MATPLOTLIB_AVAILABLE:
            return None

        G = nx.Graph()

        # Add nodes (agents)
        for agent_id, agent in self.coordinator._registry._agents.items():
            G.add_node(
                agent_id,
                role=agent.role.name,
                state=agent.state.value,
                capabilities=", ".join(agent.capabilities),
                color=self._state_colors.get(agent.state, "#4a9eff"),
            )

        # Add edges based on message history
        conversations = self.coordinator._message_bus._conversations
        for conv in conversations.values():
            participants = list(conv.participants)
            for i, p1 in enumerate(participants):
                for p2 in participants[i + 1:]:
                    if G.has_node(p1) and G.has_node(p2):
                        if G.has_edge(p1, p2):
                            G[p1][p2]["messages"] = G[p1][p2].get("messages", 0) + conv.message_count
                        else:
                            G.add_edge(p1, p2, messages=conv.message_count)

        return G

    def render_network(
        self,
        output: str = "network.png",
        figsize: Tuple[int, int] = (12, 8),
        layout: str = "spring",
        show_labels: bool = True,
        show_legend: bool = True,
    ) -> Optional[str]:
        """
        Render the agent network graph.

        Args:
            output: Output file path
            figsize: Figure size
            layout: Layout algorithm ("spring", "circular", "random", "shell")
            show_labels: Show node labels
            show_legend: Show legend

        Returns:
            Path to the rendered image or None if matplotlib not available
        """
        if not MATPLOTLIB_AVAILABLE:
            print("Visualization requires matplotlib and networkx. Install with: pip install agent-coordinator[viz]")
            return None

        G = self.build_network_graph()
        if G is None or G.number_of_nodes() == 0:
            print("No agents to visualize")
            return None

        fig, ax = plt.subplots(figsize=figsize)

        # Choose layout
        if layout == "circular":
            pos = nx.circular_layout(G)
        elif layout == "random":
            pos = nx.random_layout(G)
        elif layout == "shell":
            pos = nx.shell_layout(G)
        else:
            pos = nx.spring_layout(G, seed=42)

        # Get node colors
        node_colors = [G.nodes[n].get("color", "#4a9eff") for n in G.nodes()]

        # Draw edges
        nx.draw_networkx_edges(
            G,
            pos,
            alpha=0.3,
            width=1,
            edge_color="#999999",
            ax=ax,
        )

        # Draw nodes
        nx.draw_networkx_nodes(
            G,
            pos,
            node_color=node_colors,
            node_size=500,
            ax=ax,
        )

        # Draw labels
        if show_labels:
            labels = {n: G.nodes[n].get("role", n) for n in G.nodes()}
            nx.draw_networkx_labels(
                G,
                pos,
                labels,
                font_size=8,
                ax=ax,
            )

        # Legend
        if show_legend:
            legend_patches = [
                mpatches.Patch(color=color, label=state.value.title())
                for state, color in self._state_colors.items()
            ]
            ax.legend(
                handles=legend_patches,
                loc="upper right",
                title="Agent States",
            )

        ax.set_title(f"Agent Network - {self.coordinator.name}")
        ax.axis("off")

        plt.tight_layout()
        plt.savefig(output, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"Network graph saved to: {output}")
        return output

    def show_dashboard(self) -> None:
        """Show an interactive dashboard (requires display)."""
        if not MATPLOTLIB_AVAILABLE:
            print("Dashboard requires matplotlib and networkx")
            return

        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f"Agent Coordinator Dashboard - {self.coordinator.name}", fontsize=16)

        # 1. Agent status pie chart
        ax1 = axes[0, 0]
        status_counts = {}
        for agent in self.coordinator._registry._agents.values():
            state = agent.state.value
            status_counts[state] = status_counts.get(state, 0) + 1

        if status_counts:
            colors = [self._state_colors.get(AgentState(s), "#999") for s in status_counts.keys()]
            ax1.pie(
                status_counts.values(),
                labels=status_counts.keys(),
                autopct="%1.1f%%",
                colors=colors,
            )
        ax1.set_title("Agent Status Distribution")

        # 2. Role distribution bar chart
        ax2 = axes[0, 1]
        role_counts = {}
        for agent in self.coordinator._registry._agents.values():
            role = agent.role.name
            role_counts[role] = role_counts.get(role, 0) + 1

        if role_counts:
            ax2.bar(role_counts.keys(), role_counts.values(), color="#4a9eff")
        ax2.set_title("Agents by Role")
        ax2.set_xlabel("Role")
        ax2.set_ylabel("Count")
        ax2.tick_params(axis="x", rotation=45)

        # 3. Task queue statistics
        ax3 = axes[1, 0]
        stats = self.coordinator._task_queue.get_statistics()
        stat_names = ["Queue", "Pending", "Assigned", "Completed"]
        stat_values = [
            stats["queue_size"],
            stats["pending"],
            stats["assigned"],
            stats["completed"],
        ]
        ax3.barh(stat_names, stat_values, color=["#FF9800", "#FFC107", "#2196F3", "#4CAF50"])
        ax3.set_title("Task Queue Statistics")
        ax3.set_xlabel("Count")

        # 4. System metrics text display
        ax4 = axes[1, 1]
        ax4.axis("off")

        sys_metrics = self.coordinator._metrics.get_system_metrics()
        health = self.coordinator._monitor.get_system_health()

        metrics_text = f"""
        System Metrics

        Total Agents: {sys_metrics.total_agents}
        Active Agents: {sys_metrics.active_agents}
        Total Tasks: {sys_metrics.total_tasks}
        Completed: {sys_metrics.completed_tasks}
        Failed: {sys_metrics.failed_tasks}
        Avg Execution Time: {sys_metrics.avg_execution_time:.3f}s
        Tasks/min: {sys_metrics.tasks_per_minute:.1f}

        System Health: {health.status.value.upper()}
        Health %: {health.health_percentage:.1f}%
        """

        ax4.text(0.1, 0.5, metrics_text, fontsize=10, verticalalignment="center", fontfamily="monospace")

        plt.tight_layout()
        plt.show()

    def get_network_data(self) -> Dict[str, Any]:
        """Get network data as a dictionary for custom visualization."""
        agents = {}
        for agent_id, agent in self.coordinator._registry._agents.items():
            agents[agent_id] = {
                "id": agent_id,
                "role": agent.role.name,
                "state": agent.state.value,
                "capabilities": agent.capabilities,
                "current_tasks": agent.current_task_count,
            }

        connections = []
        for conv in self.coordinator._message_bus._conversations.values():
            participants = list(conv.participants)
            for i, p1 in enumerate(participants):
                for p2 in participants[i + 1:]:
                    connections.append({
                        "from": p1,
                        "to": p2,
                        "messages": conv.message_count,
                    })

        return {
            "agents": agents,
            "connections": connections,
            "total_agents": len(agents),
            "total_connections": len(connections),
        }


class ConsoleDashboard:
    """Console-based dashboard for monitoring."""

    def __init__(self, coordinator: AgentCoordinator):
        self.coordinator = coordinator
        self._running = False

    async def start(self, refresh_interval: float = 1.0) -> None:
        """Start the console dashboard."""
        self._running = True

        try:
            from rich.console import Console
            from rich.table import Table
            from rich.live import Live
            from rich.layout import Layout
            from rich.panel import Panel
            from rich.text import Text
            RICH_AVAILABLE = True
        except ImportError:
            RICH_AVAILABLE = False
            print("Console dashboard requires 'rich'. Install with: pip install rich")
            return

        if not RICH_AVAILABLE:
            return

        console = Console()

        def generate_display():
            layout = Layout()

            # Header
            header = Panel(
                f"[bold cyan]Agent Coordinator Dashboard[/bold cyan] - {self.coordinator.name}",
                style="on #234"
            )
            layout.split_column(
                Layout(header, size=3),
                Layout(name="body"),
            )

            # Body
            body_parts = []

            # Agents table
            agents_table = Table(title="Agents", show_header=True, header_style="bold magenta")
            agents_table.add_column("ID", style="cyan")
            agents_table.add_column("Role", style="green")
            agents_table.add_column("State", style="yellow")
            agents_table.add_column("Tasks", style="blue")
            agents_table.add_column("Capabilities", style="dim")

            for agent in self.coordinator._registry._agents.values():
                state_style = {
                    AgentState.IDLE: "green",
                    AgentState.BUSY: "yellow",
                    AgentState.FAILED: "red",
                    AgentState.TERMINATED: "dim",
                }.get(agent.state, "white")

                agents_table.add_row(
                    agent.id,
                    agent.role.name,
                    f"[{state_style}]{agent.state.value}[/{state_style}]",
                    str(agent.current_task_count),
                    ", ".join(agent.capabilities[:3]) + ("..." if len(agent.capabilities) > 3 else ""),
                )

            body_parts.append(agents_table)

            # Tasks summary
            stats = self.coordinator._task_queue.get_statistics()
            tasks_text = Text()
            tasks_text.append(f"Queue: {stats['queue_size']}", style="yellow")
            tasks_text.append(" | ")
            tasks_text.append(f"Pending: {stats['pending']}", style="orange")
            tasks_text.append(" | ")
            tasks_text.append(f"Assigned: {stats['assigned']}", style="blue")
            tasks_text.append(" | ")
            tasks_text.append(f"Completed: {stats['completed']}", style="green")

            body_parts.append(Panel(tasks_text, title="Task Queue"))

            # System metrics
            sys_metrics = self.coordinator._metrics.get_system_metrics()
            metrics_text = Text()
            metrics_text.append(f"Agents: {sys_metrics.total_agents}/{sys_metrics.active_agents} active\n")
            metrics_text.append(f"Tasks: {sys_metrics.completed_tasks} completed, {sys_metrics.failed_tasks} failed\n")
            metrics_text.append(f"Avg time: {sys_metrics.avg_execution_time:.3f}s  ")
            metrics_text.append(f"Rate: {sys_metrics.tasks_per_minute:.1f} tasks/min")

            body_parts.append(Panel(metrics_text, title="System Metrics"))

            # Combine body parts
            layout["body"].split_column(*[Layout(p) for p in body_parts])

            return layout

        with Live(generate_display(), console=console, refresh_per_second=1 / refresh_interval) as live:
            while self._running:
                await asyncio.sleep(refresh_interval)
                live.update(generate_display())

    def stop(self) -> None:
        """Stop the console dashboard."""
        self._running = False


def create_visualizer(coordinator: AgentCoordinator) -> NetworkVisualizer:
    """Create a visualizer for the coordinator."""
    return NetworkVisualizer(coordinator)


def create_console_dashboard(coordinator: AgentCoordinator) -> ConsoleDashboard:
    """Create a console dashboard for the coordinator."""
    return ConsoleDashboard(coordinator)
