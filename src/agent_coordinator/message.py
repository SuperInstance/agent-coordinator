"""
Message module - Defines AgentMessage and MessageType classes.
"""

from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


class MessageType(str, Enum):
    """Types of messages that can be sent between agents."""

    # Communication
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"

    # Coordination
    BROADCAST = "broadcast"
    MULTICAST = "multicast"
    DIRECT = "direct"

    # Control
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    SHUTDOWN = "shutdown"

    # Task-related
    TASK_REQUEST = "task_request"
    TASK_UPDATE = "task_update"
    TASK_RESULT = "task_result"

    # Collaboration
    COLLABORATE = "collaborate"
    SYNC = "sync"
    HANDOFF = "handoff"


class MessagePriority(int, Enum):
    """Message priority levels."""
    URGENT = 0
    HIGH = 25
    NORMAL = 50
    LOW = 75


@dataclass
class AgentMessage:
    """
    A message sent between agents.

    Messages support:
    - Direct agent-to-agent communication
    - Broadcasting to multiple agents
    - Request/response patterns
    - Correlation for tracking conversations
    """

    from_agent: str
    to_agent: str
    message_type: MessageType = MessageType.DIRECT
    content: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reply_to: Optional[str] = None
    priority: int = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    ttl: Optional[float] = None  # Time to live in seconds
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        """Get message age in seconds."""
        return (datetime.now() - self.timestamp).total_seconds()

    @property
    def is_expired(self) -> bool:
        """Check if message has expired based on TTL."""
        if self.ttl is None:
            return False
        return self.age_seconds > self.ttl

    def is_response_to(self, message: "AgentMessage") -> bool:
        """Check if this is a response to the given message."""
        return (
            self.reply_to == message.correlation_id and
            self.to_agent == message.from_agent
        )

    def reply(self, content: Dict[str, Any], success: bool = True) -> "AgentMessage":
        """Create a reply to this message."""
        return AgentMessage(
            from_agent=self.to_agent,
            to_agent=self.from_agent,
            message_type=MessageType.RESPONSE,
            content=content,
            correlation_id=str(uuid.uuid4()),
            reply_to=self.correlation_id,
            priority=self.priority,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type.value,
            "content": self.content,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
            "ttl": self.ttl,
            "metadata": self.metadata,
        }


@dataclass
class MessageReceipt:
    """Receipt confirming delivery of a message."""
    message_id: str
    delivered_to: str
    delivered_at: datetime = field(default_factory=datetime.now)
    acknowledged: bool = True


@dataclass
class Conversation:
    """Tracks a conversation between agents."""
    id: str
    participants: list[str]
    messages: list[AgentMessage] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def last_message(self) -> Optional[AgentMessage]:
        return self.messages[-1] if self.messages else None

    def add_message(self, message: AgentMessage) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)

    def get_messages_from(self, agent_id: str) -> list[AgentMessage]:
        """Get all messages from a specific agent."""
        return [m for m in self.messages if m.from_agent == agent_id]


class MessageBuilder:
    """Builder for creating messages with a fluent API."""

    def __init__(self, from_agent: str, to_agent: str):
        self._message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
        )

    def of_type(self, message_type: MessageType) -> "MessageBuilder":
        """Set message type."""
        self._message.message_type = message_type
        return self

    def with_content(self, content: Dict[str, Any]) -> "MessageBuilder":
        """Set message content."""
        self._message.content = content
        return self

    def with_correlation_id(self, correlation_id: str) -> "MessageBuilder":
        """Set correlation ID."""
        self._message.correlation_id = correlation_id
        return self

    def reply_to(self, message_id: str) -> "MessageBuilder":
        """Set reply-to message ID."""
        self._message.reply_to = message_id
        return self

    def with_priority(self, priority: MessagePriority) -> "MessageBuilder":
        """Set message priority."""
        self._message.priority = priority.value
        return self

    def with_ttl(self, ttl: float) -> "MessageBuilder":
        """Set time-to-live in seconds."""
        self._message.ttl = ttl
        return self

    def with_metadata(self, key: str, value: Any) -> "MessageBuilder":
        """Add metadata."""
        self._message.metadata[key] = value
        return self

    def build(self) -> AgentMessage:
        """Build and return the message."""
        return self._message


def create_message(
    from_agent: str,
    to_agent: str,
    message_type: MessageType = MessageType.DIRECT,
    content: Dict[str, Any] = None,
    **kwargs,
) -> AgentMessage:
    """
    Factory function to create a message.

    Args:
        from_agent: Sender agent ID
        to_agent: Receiver agent ID
        message_type: Type of message
        content: Message content
        **kwargs: Additional message attributes

    Returns:
        A new AgentMessage instance
    """
    return AgentMessage(
        from_agent=from_agent,
        to_agent=to_agent,
        message_type=message_type,
        content=content or {},
        **kwargs,
    )


def broadcast_message(
    from_agent: str,
    content: Dict[str, Any],
    exclude: list[str] = None,
    **kwargs,
) -> AgentMessage:
    """
    Create a broadcast message.

    Args:
        from_agent: Sender agent ID
        content: Message content
        exclude: Agent IDs to exclude from broadcast
        **kwargs: Additional message attributes

    Returns:
        A broadcast message
    """
    return AgentMessage(
        from_agent=from_agent,
        to_agent="*",
        message_type=MessageType.BROADCAST,
        content=content,
        metadata={"exclude": exclude or []},
        **kwargs,
    )
