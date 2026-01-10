"""
Message Bus - Handles inter-agent communication.
"""

import asyncio
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import logging

from agent_coordinator.message import AgentMessage, MessageType, MessageReceipt
from agent_coordinator.agent import Agent

logger = logging.getLogger(__name__)


@dataclass
class MessageDelivery:
    """Tracks message delivery status."""
    message: AgentMessage
    delivered_to: Set[str] = field(default_factory=set)
    failed_to: Set[str] = field(default_factory=set)
    timestamps: Dict[str, datetime] = field(default_factory=dict)

    @property
    def delivery_count(self) -> int:
        return len(self.delivered_to)

    @property
    def is_fully_delivered(self) -> bool:
        """Check if message was delivered to all intended recipients."""
        # For direct messages, just one recipient
        if self.message.message_type == MessageType.DIRECT:
            return len(self.delivered_to) >= 1
        return False  # Broadcast/other types need custom logic


@dataclass
class Conversation:
    """Tracks a conversation between agents."""
    id: str
    participants: Set[str]
    messages: List[AgentMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def add_message(self, message: AgentMessage) -> None:
        self.messages.append(message)
        self.participants.add(message.from_agent)
        if message.to_agent != "*":
            self.participants.add(message.to_agent)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def get_last_message(self) -> Optional[AgentMessage]:
        return self.messages[-1] if self.messages else None


class MessageBus:
    """
    Facilitates communication between agents.

    Features:
    - Direct agent-to-agent messaging
    - Broadcasting to multiple agents
    - Request/response patterns
    - Conversation tracking
    - Message filtering and routing
    """

    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._message_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._delivery_tracking: Dict[str, MessageDelivery] = {}

        # Conversations (keyed by correlation_id)
        self._conversations: Dict[str, Conversation] = {}

        # Subscriptions (for pub/sub patterns)
        self._subscriptions: Dict[str, Set[str]] = defaultdict(set)  # topic -> agent_ids

        # Message handlers (for filtering)
        self._message_handlers: List[Callable[[AgentMessage], bool]] = []

        # Worker task
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

        # Event callbacks
        self._on_message_sent: List[Callable[[AgentMessage], None]] = []
        self._on_message_delivered: List[Callable[[AgentMessage, str], None]] = []
        self._on_message_failed: List[Callable[[AgentMessage, str, str], None]] = []

    @property
    def is_running(self) -> bool:
        return self._running

    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the message bus."""
        self._agents[agent.id] = agent
        logger.debug(f"Agent {agent.id} registered with message bus")

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from the message bus."""
        self._agents.pop(agent_id, None)
        # Remove from subscriptions
        for topic in self._subscriptions:
            self._subscriptions[topic].discard(agent_id)
        logger.debug(f"Agent {agent_id} unregistered from message bus")

    def subscribe(self, agent_id: str, topic: str) -> None:
        """Subscribe an agent to a topic."""
        self._subscriptions[topic].add(agent_id)
        logger.debug(f"Agent {agent_id} subscribed to topic: {topic}")

    def unsubscribe(self, agent_id: str, topic: str) -> None:
        """Unsubscribe an agent from a topic."""
        self._subscriptions[topic].discard(agent_id)
        logger.debug(f"Agent {agent_id} unsubscribed from topic: {topic}")

    def add_message_handler(self, handler: Callable[[AgentMessage], bool]) -> None:
        """Add a message filter handler. Return False from handler to drop message."""
        self._message_handlers.append(handler)

    def add_sent_callback(self, callback: Callable[[AgentMessage], None]) -> None:
        self._on_message_sent.append(callback)

    def add_delivered_callback(self, callback: Callable[[AgentMessage, str], None]) -> None:
        self._on_message_delivered.append(callback)

    def add_failed_callback(self, callback: Callable[[AgentMessage, str, str], None]) -> None:
        self._on_message_failed.append(callback)

    async def start(self) -> None:
        """Start the message bus worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._process_messages())
        logger.info("Message bus started")

    async def stop(self) -> None:
        """Stop the message bus."""
        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        logger.info("Message bus stopped")

    async def send(self, message: AgentMessage) -> List[MessageReceipt]:
        """
        Send a message to its intended recipients.

        Returns:
            List of delivery receipts
        """
        receipts = []

        # Check expiration
        if message.is_expired:
            logger.warning(f"Message {message.correlation_id} has expired, dropping")
            return receipts

        # Run through message handlers
        for handler in self._message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    keep = await handler(message)
                else:
                    keep = handler(message)

                if not keep:
                    logger.debug(f"Message {message.correlation_id} filtered by handler")
                    return receipts
            except Exception as e:
                logger.error(f"Message handler error: {e}")

        # Track delivery
        self._delivery_tracking[message.correlation_id] = MessageDelivery(message=message)

        # Determine recipients
        recipients = self._get_recipients(message)

        # Deliver to each recipient
        for recipient_id in recipients:
            try:
                agent = self._agents.get(recipient_id)

                if agent is None:
                    await self._record_delivery_failure(message, recipient_id, "Agent not found")
                    continue

                await agent.send_message(message)
                self._record_delivery(message, recipient_id)

                receipts.append(MessageReceipt(
                    message_id=message.correlation_id,
                    delivered_to=recipient_id,
                    delivered_at=datetime.now(),
                ))

                # Notify callbacks
                for callback in self._on_message_delivered:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(message, recipient_id)
                        else:
                            callback(message, recipient_id)
                    except Exception as e:
                        logger.error(f"Delivery callback error: {e}")

            except Exception as e:
                await self._record_delivery_failure(message, recipient_id, str(e))
                logger.error(f"Failed to deliver message to {recipient_id}: {e}")

        # Update conversation tracking
        self._update_conversation(message)

        # Notify sent callbacks
        for callback in self._on_message_sent:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Sent callback error: {e}")

        return receipts

    async def send_and_wait(
        self,
        message: AgentMessage,
        timeout: float = 30.0,
    ) -> Optional[AgentMessage]:
        """
        Send a message and wait for a response.

        Args:
            message: The message to send
            timeout: Maximum time to wait for response

        Returns:
            The response message or None if timeout
        """
        # Register a future for the response
        response_future: asyncio.Future[AgentMessage] = asyncio.Future()

        # Add a temporary handler for responses
        async def response_handler(msg: AgentMessage) -> bool:
            if msg.is_response_to(message):
                if not response_future.done():
                    response_future.set_result(msg)
                return False  # Don't process further
            return True

        self.add_message_handler(response_handler)

        # Send the message
        await self.send(message)

        # Wait for response
        try:
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response to {message.correlation_id}")
            return None
        finally:
            # Remove the temporary handler
            self._message_handlers.remove(response_handler)

    def _get_recipients(self, message: AgentMessage) -> List[str]:
        """Determine the recipient list for a message."""
        if message.message_type == MessageType.BROADCAST:
            # Send to all agents except sender and excluded
            exclude = message.metadata.get("exclude", [])
            exclude.append(message.from_agent)
            return [aid for aid in self._agents if aid not in exclude]

        elif message.message_type == MessageType.MULTICAST:
            # Send to specific list
            recipients = message.metadata.get("recipients", [])
            return [r for r in recipients if r in self._agents]

        else:
            # Direct message
            return [message.to_agent] if message.to_agent in self._agents else []

    def _update_conversation(self, message: AgentMessage) -> None:
        """Update conversation tracking."""
        # Use correlation_id or create a conversation ID
        conv_id = message.correlation_id

        if conv_id not in self._conversations:
            self._conversations[conv_id] = Conversation(
                id=conv_id,
                participants=set(),
            )

        self._conversations[conv_id].add_message(message)

    def _record_delivery(self, message: AgentMessage, recipient_id: str) -> None:
        """Record successful message delivery."""
        if message.correlation_id in self._delivery_tracking:
            delivery = self._delivery_tracking[message.correlation_id]
            delivery.delivered_to.add(recipient_id)
            delivery.timestamps[recipient_id] = datetime.now()

    async def _record_delivery_failure(self, message: AgentMessage, recipient_id: str, reason: str) -> None:
        """Record failed message delivery."""
        if message.correlation_id in self._delivery_tracking:
            delivery = self._delivery_tracking[message.correlation_id]
            delivery.failed_to.add(recipient_id)

        # Notify callbacks
        for callback in self._on_message_failed:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message, recipient_id, reason)
                else:
                    callback(message, recipient_id, reason)
            except Exception as e:
                logger.error(f"Failed delivery callback error: {e}")

    async def _process_messages(self) -> None:
        """Background worker for processing messages."""
        try:
            while self._running:
                # Process any queued internal messages
                try:
                    message = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=0.1,
                    )
                    await self.send(message)
                except asyncio.TimeoutError:
                    continue

        except asyncio.CancelledError:
            logger.debug("Message bus worker cancelled")
        except Exception as e:
            logger.error(f"Message bus worker error: {e}")

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self._conversations.get(conversation_id)

    def get_agent_conversations(self, agent_id: str) -> List[Conversation]:
        """Get all conversations involving an agent."""
        return [
            conv for conv in self._conversations.values()
            if agent_id in conv.participants
        ]

    def get_delivery_status(self, message_id: str) -> Optional[MessageDelivery]:
        """Get the delivery status of a message."""
        return self._delivery_tracking.get(message_id)

    def get_statistics(self) -> Dict[str, any]:
        """Get message bus statistics."""
        return {
            "registered_agents": len(self._agents),
            "active_conversations": len(self._conversations),
            "tracked_messages": len(self._delivery_tracking),
            "subscriptions": {topic: len(agents) for topic, agents in self._subscriptions.items()},
        }
