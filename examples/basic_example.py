"""
Basic Example - Simple agent coordination demonstration.

This is a minimal example showing the core features of Agent Coordinator.
"""

import asyncio
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_coordinator import (
    AgentCoordinator,
    AgentRole,
    Task,
    create_task,
    AgentMessage,
    MessageType,
    create_message,
)


async def basic_example():
    """Run a basic agent coordination example."""

    print("="*60)
    print("Agent Coordinator - Basic Example")
    print("="*60)

    # Create coordinator
    from agent_coordinator import CoordinatorConfig
    coordinator = AgentCoordinator(config=CoordinatorConfig(name="basic-example"))
    await coordinator.start()

    print("\n1. Registering roles...")

    # Define roles
    producer_role = AgentRole(
        name="producer",
        capabilities=["generate", "create"],
        max_concurrent_tasks=2,
    )

    consumer_role = AgentRole(
        name="consumer",
        capabilities=["process", "analyze"],
        max_concurrent_tasks=2,
    )

    await coordinator.register_role(producer_role)
    await coordinator.register_role(consumer_role)

    print("   Registered roles: producer, consumer")

    print("\n2. Spawning agents...")

    # Define task handlers
    async def producer_handler(task):
        data = task.payload.get("data", "default-data")
        await asyncio.sleep(0.5)  # Simulate work
        return {
            "status": "produced",
            "data": f"processed-{data}",
            "agent": "producer",
        }

    async def consumer_handler(task):
        data = task.payload.get("data", "")
        await asyncio.sleep(0.3)  # Simulate work
        return {
            "status": "consumed",
            "result": f"analyzed-{data}",
            "agent": "consumer",
        }

    # Spawn agents
    producer1 = await coordinator.spawn_agent(
        "producer-1",
        role="producer",
        task_handler=producer_handler,
    )

    producer2 = await coordinator.spawn_agent(
        "producer-2",
        role="producer",
        task_handler=producer_handler,
    )

    consumer1 = await coordinator.spawn_agent(
        "consumer-1",
        role="consumer",
        task_handler=consumer_handler,
    )

    print(f"   Spawned agents: {producer1.id}, {producer2.id}, {consumer1.id}")

    print("\n3. Submitting tasks...")

    # Create and submit tasks
    tasks = [
        create_task(
            description="Generate data A",
            capabilities=["generate"],
            payload={"data": "A"},
        ),
        create_task(
            description="Generate data B",
            capabilities=["create"],
            payload={"data": "B"},
        ),
        create_task(
            description="Process data",
            capabilities=["process"],
            payload={"data": "input"},
        ),
    ]

    results = await coordinator.submit_tasks(tasks, wait_for_all=True)

    print(f"   Submitted {len(tasks)} tasks")
    print("\n4. Task results:")
    for i, result in enumerate(results, 1):
        if result and result.success:
            print(f"   Task {i}: {result.result}")
        else:
            print(f"   Task {i}: Failed - {result.error if result else 'Unknown error'}")

    print("\n5. Getting coordinator status...")

    status = await coordinator.get_status()
    print(f"   Running: {status['running']}")
    print(f"   Total agents: {status['agents']['total_agents']}")
    print(f"   Available agents: {status['agents']['available']}")
    print(f"   Completed tasks: {status['tasks']['completed']}")

    print("\n6. Shutting down...")
    await coordinator.shutdown()

    print("\n" + "="*60)
    print("Example complete!")
    print("="*60)


async def message_passing_example():
    """Demonstrate message passing between agents."""

    print("\n" + "="*60)
    print("Message Passing Example")
    print("="*60)

    from agent_coordinator import CoordinatorConfig
    coordinator = AgentCoordinator(config=CoordinatorConfig(name="messaging-example"))
    await coordinator.start()

    # Register a simple role
    role = AgentRole(name="worker", capabilities=["work"])
    await coordinator.register_role(role)

    # Track received messages
    received_messages = []

    def message_handler(msg):
        received_messages.append(msg)
        print(f"   Agent {msg.to_agent} received: {msg.content}")

    # Spawn two agents
    await coordinator.spawn_agent(
        "agent-a",
        role="worker",
        message_handler=message_handler,
    )

    await coordinator.spawn_agent(
        "agent-b",
        role="worker",
        message_handler=message_handler,
    )

    print("\n1. Sending messages...")

    # Send direct message
    msg1 = create_message(
        from_agent="agent-a",
        to_agent="agent-b",
        message_type=MessageType.REQUEST,
        content={"action": "greet", "message": "Hello from Agent A!"},
    )

    await coordinator.message_bus.send(msg1)

    # Send reply
    msg2 = create_message(
        from_agent="agent-b",
        to_agent="agent-a",
        message_type=MessageType.RESPONSE,
        content={"action": "reply", "message": "Hi back from Agent B!"},
        reply_to=msg1.correlation_id,
    )

    await coordinator.message_bus.send(msg2)

    await asyncio.sleep(0.5)  # Wait for message processing

    print(f"\n2. Messages delivered: {len(received_messages)}")

    await coordinator.shutdown()

    print("\n" + "="*60)


async def main():
    """Run all examples."""
    await basic_example()
    await message_passing_example()


if __name__ == "__main__":
    asyncio.run(main())
