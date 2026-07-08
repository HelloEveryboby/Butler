import re
import logging
from typing import Dict, List, Optional
from butler.core.algorithms import text_cosine_similarity
from butler.core.skill_manager import SkillManager

logger = logging.getLogger("HybridRouter")

class HybridRouter:
    """
    Two-stage routing for Butler:
    Stage 1: Static Matcher (Regex/Exact) - O(1) or O(N_regex)
    Stage 2: Semantic Matcher (TF-IDF + Cosine Similarity) - Lightweight & Zero-dependency
    """
    def __init__(self, skill_manager: SkillManager):
        self.skill_manager = skill_manager
        self.static_routes: Dict[str, str] = {} # regex -> skill_id
        self.update_routes()

    def update_routes(self):
        """Update routing table from skill manifests."""
        self.static_routes = {}
        for s_id, meta in self.skill_manager.manifests.items():
            triggers = meta.get("triggers", [])
            if isinstance(triggers, str):
                triggers = [triggers]

            for trigger in triggers:
                # Compile simple regex for static matching
                try:
                    pattern = re.compile(f"^{trigger}$", re.IGNORECASE)
                    self.static_routes[trigger] = s_id
                except re.error:
                    continue

    def route(self, text: str, threshold: float = 0.75) -> Optional[str]:
        text = text.strip()
        if not text:
            return None

        # --- Stage 1: Static Matching ---
        # Direct lookup for exact match
        for trigger, s_id in self.static_routes.items():
            if re.match(f"^{trigger}$", text, re.IGNORECASE):
                logger.info(f"Stage 1 Match (Static): '{text}' -> {s_id}")
                return s_id

        # --- Stage 2: Lightweight Semantic Matching ---
        best_skill = None
        max_similarity = 0.0

        for s_id, meta in self.skill_manager.manifests.items():
            # Match against name, description, and triggers
            content_to_match = [
                meta.get("name", ""),
                meta.get("description", ""),
                " ".join(meta.get("triggers", []) if isinstance(meta.get("triggers", []), list) else [meta.get("triggers", "")])
            ]
            combined_content = " ".join(content_to_match).lower()

            similarity = text_cosine_similarity(text.lower(), combined_content)
            if similarity > max_similarity:
                max_similarity = similarity
                best_skill = s_id

        if max_similarity >= threshold:
            logger.info(f"Stage 2 Match (Semantic): '{text}' -> {best_skill} (Score: {max_similarity:.2f})")
            return best_skill

        logger.info(f"No match found for '{text}'. Best score: {max_similarity:.2f}")
        return None

# Singleton instance placeholder (usually initialized in Butler app)
router = None
