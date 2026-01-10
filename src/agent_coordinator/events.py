"""
Events - Event system for coordinator notifications.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events in the system."""

    # Agent lifecycle
    AGENT_REGISTERED = "agent_registered"
    AGENT_UNREGISTERED = "agent_unregistered"
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    AGENT_STATE_CHANGED = "agent_state_changed"

    # Task lifecycle
    TASK_QUEUED = "task_queued"
    TASK_ASSIGNED = "task_assigned"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"

    # Communication
    MESSAGE_SENT = "message_sent"
    MESSAGE_DELIVERED = "message_delivered"
    MESSAGE_FAILED = "message_failed"

    # Health/Monitoring
    AGENT_HEALTH_CHANGED = "agent_health_changed"
    AGENT_OFFLINE = "agent_offline"
    AGENT_RECOVERED = "agent_recovered"
    FAILURE_DETECTED = "failure_detected"

    # System
    SYSTEM_STARTING = "system_starting"
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPING = "system_stopping"
    SYSTEM_STOPPED = "system_stopped"
    SYSTEM_ERROR = "system_error"


@dataclass
class Event:
    """Represents a system event."""
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "correlation_id": self.correlation_id,
        }


@dataclass
class EventSubscription:
    """A subscription to events."""
    event_types: List[EventType]
    handler: Callable[[Event], None]
    filter_func: Optional[Callable[[Event], bool]] = None
    once: bool = False  # Unsubscribe after first match
    id: str = ""

    def matches(self, event: Event) -> bool:
        """Check if this subscription matches an event."""
        if event.type not in self.event_types and EventType("*") not in self.event_types:
            return False
        if self.filter_func and not self.filter_func(event):
            return False
        return True


class EventBus:
    """
    Central event bus for system-wide event notifications.

    Features:
    - Type-based subscriptions
    - Event filtering
    - Async event delivery
    - Wildcard subscriptions
    - One-time subscriptions
    """

    def __init__(self):
        self._subscriptions: List[EventSubscription] = []
        self._event_history: List[Event] = []
        self._history_max_size = 1000
        self._subscription_counter = 0
        self._lock = asyncio.Lock()

    async def emit(self, event: Event) -> None:
        """
        Emit an event to all matching subscribers.

        Args:
            event: The event to emit
        """
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._history_max_size:
            self._event_history.pop(0)

        # Find matching subscriptions
        to_remove = []
        async with self._lock:
            for sub in self._subscriptions:
                if sub.matches(event):
                    try:
                        if asyncio.iscoroutinefunction(sub.handler):
                            asyncio.create_task(sub.handler(event))
                        else:
                            sub.handler(event)

                        if sub.once:
                            to_remove.append(sub)
                    except Exception as e:
                        logger.error(f"Event handler error: {e}")

            # Remove one-time subscriptions
            for sub in to_remove:
                self._subscriptions.remove(sub)

    def subscribe(
        self,
        event_types: List[EventType],
        handler: Callable[[Event], None],
        filter_func: Optional[Callable[[Event], bool]] = None,
        once: bool = False,
    ) -> str:
        """
        Subscribe to events.

        Args:
            event_types: List of event types to subscribe to
            handler: Handler function for events
            filter_func: Optional filter function
            once: If True, unsubscribe after first event

        Returns:
            Subscription ID
        """
        self._subscription_counter += 1
        sub_id = f"sub_{self._subscription_counter}"

        subscription = EventSubscription(
            event_types=event_types,
            handler=handler,
            filter_func=filter_func,
            once=once,
            id=sub_id,
        )

        self._subscriptions.append(subscription)
        logger.debug(f"Created subscription {sub_id} for {[t.value for t in event_types]}")

        return sub_id

    def subscribe_once(
        self,
        event_types: List[EventType],
        handler: Callable[[Event], None],
        filter_func: Optional[Callable[[Event], bool]] = None,
    ) -> str:
        """Subscribe to events that will fire only once."""
        return self.subscribe(event_types, handler, filter_func, once=True)

    def unsubscribe(self, sub_id: str) -> bool:
        """
        Unsubscribe by subscription ID.

        Args:
            sub_id: Subscription ID from subscribe()

        Returns:
            True if subscription was removed
        """
        for i, sub in enumerate(self._subscriptions):
            if sub.id == sub_id:
                self._subscriptions.pop(i)
                logger.debug(f"Removed subscription {sub_id}")
                return True
        return False

    def unsubscribe_all(self, handler: Callable[[Event], None]) -> int:
        """
        Unsubscribe all subscriptions for a handler.

        Returns:
            Number of subscriptions removed
        """
        count = 0
        to_remove = []
        for sub in self._subscriptions:
            if sub.handler == handler:
                to_remove.append(sub)

        for sub in to_remove:
            self._subscriptions.remove(sub)
            count += 1

        return count

    def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 100,
    ) -> List[Event]:
        """
        Get event history.

        Args:
            event_type: Filter by event type
            limit: Maximum number of events to return

        Returns:
            List of events
        """
        events = self._event_history

        if event_type:
            events = [e for e in events if e.type == event_type]

        return events[-limit:]

    def get_event_count(self, event_type: Optional[EventType] = None) -> int:
        """Get count of events by type."""
        if event_type:
            return sum(1 for e in self._event_history if e.type == event_type)
        return len(self._event_history)

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()


# Global event bus instance
_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


def emit_event(event_type: EventType, data: Dict[str, Any], source: str = "") -> None:
    """Emit an event to the global event bus."""
    bus = get_event_bus()
    event = Event(type=event_type, data=data, source=source)
    asyncio.create_task(bus.emit(event))


def subscribe(
    event_types: List[EventType],
    handler: Callable[[Event], None],
    filter_func: Optional[Callable[[Event], bool]] = None,
) -> str:
    """Subscribe to events on the global event bus."""
    bus = get_event_bus()
    return bus.subscribe(event_types, handler, filter_func)


def unsubscribe(sub_id: str) -> bool:
    """Unsubscribe from events on the global event bus."""
    bus = get_event_bus()
    return bus.unsubscribe(sub_id)
