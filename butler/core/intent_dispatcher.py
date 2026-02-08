# butler/intent_dispatcher.py

import logging
from functools import wraps
from . import algorithms

logger = logging.getLogger(__name__)

class IntentRegistry:
    """A registry for dynamically discovering and dispatching intent handlers."""
    def __init__(self):
        self._intents = {}

    def register(self, intent_name, requires_entities=True):
        """A decorator to register a function as an intent handler."""
        def decorator(func):
            logger.info(f"Registering intent '{intent_name}' to function {func.__name__}")
            self._intents[intent_name] = {
                "function": func,
                "docstring": func.__doc__,
                "requires_entities": requires_entities
            }
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def dispatch(self, intent_name, **kwargs):
        """
        Dispatches a command to the appropriate registered handler.

        Args:
            intent_name (str): The name of the intent to execute.
            **kwargs: A dictionary of arguments to pass to the handler.

        Returns:
            The result of the handler function, or None if the intent is not found.
        """
        intent = self._intents.get(intent_name)
        if not intent:
            logger.warning(f"Intent '{intent_name}' not found in registry.")
            return None

        handler = intent["function"]
        try:
            return handler(**kwargs)
        except Exception as e:
            logger.error(f"Error executing intent '{intent_name}': {e}", exc_info=True)
            return None

    def get_all_intents(self):
        """Returns a dictionary of all registered intents and their docstrings."""
        return {name: data["docstring"] for name, data in self._intents.items()}

    def intent_requires_entities(self, intent_name):
        """Checks if a given intent requires entities."""
        return self._intents.get(intent_name, {}).get("requires_entities", True)

    def match_intent_locally(self, command, threshold=0.7):
        """
        Finds the best matching intent locally using cosine similarity.

        Args:
            command (str): The user's command.
            threshold (float): The minimum similarity score to consider a match.

        Returns:
            str: The name of the best matching intent, or None if no match is found.
        """
        intents = self.get_all_intents()
        if not intents:
            return None

        best_match = None
        highest_similarity = -1.0

        for intent_name, docstring in intents.items():
            if not docstring:
                continue

            similarity = algorithms.text_cosine_similarity(command, docstring)
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = intent_name

        if highest_similarity >= threshold:
            logger.info(f"Local match found for '{command}': '{best_match}' with similarity {highest_similarity:.2f}")
            return best_match
        else:
            logger.info(f"No local match found for '{command}' above threshold {threshold}. Highest similarity was {highest_similarity:.2f} for '{best_match}'.")
            return None

# A single, global instance of the registry
intent_registry = IntentRegistry()

# Make the decorator directly accessible
register_intent = intent_registry.register
