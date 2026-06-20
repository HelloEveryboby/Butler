import collections
import logging
import threading

logger = logging.getLogger(__name__)

class EventBus:
    """A simple internal pub/sub system for decoupling Jarvis components."""
    def __init__(self):
        self._subscribers = collections.defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type, callback):
        """Subscribe a callback to a specific event type."""
        with self._lock:
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
                logger.debug(f"Subscribed {callback} to {event_type}")

    def unsubscribe(self, event_type, callback):
        """Unsubscribe a callback from a specific event type."""
        with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed {callback} from {event_type}")

    def emit(self, event_type, *args, **kwargs):
        """Emit an event to all subscribers."""
        logger.debug(f"Emitting event {event_type} with args={args}, kwargs={kwargs}")
        with self._lock:
            callbacks = self._subscribers[event_type][:]

        for callback in callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in callback {callback} for event {event_type}: {e}")

# Global instance
event_bus = EventBus()
