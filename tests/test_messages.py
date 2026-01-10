"""Tests for messaging system."""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_coordinator import (
    Agent,
    AgentMessage,
    MessageType,
    MessagePriority,
    create_message,
    broadcast_message,
    MessageBus,
    AgentRole,
    AgentConfig,
)


def test_message_creation():
    """Test creating a message."""
    msg = AgentMessage(
        from_agent="agent-1",
        to_agent="agent-2",
        message_type=MessageType.DIRECT,
        content={"data": "hello"},
    )

    assert msg.from_agent == "agent-1"
    assert msg.to_agent == "agent-2"
    assert msg.message_type == MessageType.DIRECT
    assert msg.content["data"] == "hello"


def test_message_factory():
    """Test the create_message factory function."""
    msg = create_message(
        "agent-1",
        "agent-2",
        MessageType.REQUEST,
        {"action": "help"},
    )

    assert msg.from_agent == "agent-1"
    assert msg.to_agent == "agent-2"
    assert msg.message_type == MessageType.REQUEST


def test_broadcast_message():
    """Test creating a broadcast message."""
    msg = broadcast_message(
        "leader",
        {"announcement": "Hello everyone"},
    )

    assert msg.from_agent == "leader"
    assert msg.to_agent == "*"
    assert msg.message_type == MessageType.BROADCAST


def test_message_reply():
    """Test creating a reply to a message."""
    original = create_message("a", "b", MessageType.REQUEST)

    reply = original.reply({"status": "done"})

    assert reply.to_agent == original.from_agent
    assert reply.from_agent == original.to_agent
    assert reply.message_type == MessageType.RESPONSE
    assert reply.reply_to == original.correlation_id


def test_message_expiration():
    """Test message TTL and expiration."""
    msg = create_message("a", "b", MessageType.DIRECT)
    msg.ttl = 0.001  # 1ms TTL

    import time
    time.sleep(0.002)

    assert msg.is_expired


@pytest.mark.asyncio
async def test_message_bus_registration():
    """Test registering agents with message bus."""
    bus = MessageBus()
    await bus.start()

    role = AgentRole(name="test", capabilities=["test"])
    config = AgentConfig(agent_id="test-agent", role="test")

    agent = Agent(config, role)
    await agent.start()

    bus.register_agent(agent)
    bus.unregister_agent("test-agent")

    await bus.stop()


@pytest.mark.asyncio
async def test_message_delivery():
    """Test message delivery through the bus."""
    bus = MessageBus()
    await bus.start()

    role = AgentRole(name="test", capabilities=["test"])

    received_messages = []

    async def handler(msg):
        received_messages.append(msg)

    config1 = AgentConfig(agent_id="sender", role="test")
    config2 = AgentConfig(agent_id="receiver", role="test")

    sender = Agent(config1, role)
    receiver = Agent(config2, role, message_handler=handler)

    await receiver.start()

    bus.register_agent(receiver)

    msg = create_message("sender", "receiver", MessageType.DIRECT, {"data": "test"})
    receipts = await bus.send(msg)

    assert len(receipts) == 1
    assert receipts[0].delivered_to == "receiver"

    await asyncio.sleep(0.1)  # Allow message processing

    await bus.stop()


@pytest.mark.asyncio
async def test_conversation_tracking():
    """Test conversation tracking in message bus."""
    bus = MessageBus()
    await bus.start()

    msg1 = create_message("a", "b", MessageType.DIRECT)
    msg2 = create_message("b", "a", MessageType.RESPONSE, reply_to=msg1.correlation_id)

    await bus.send(msg1)
    await bus.send(msg2)

    conv = bus.get_conversation(msg1.correlation_id)

    assert conv is not None
    assert len(conv.participants) >= 2
    assert conv.message_count >= 2

    await bus.stop()
