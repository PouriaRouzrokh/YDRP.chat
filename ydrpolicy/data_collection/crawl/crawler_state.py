"""
Module for managing crawler state to enable resume functionality.
"""

import json
import logging
import os
import pickle
from typing import Any, Dict, List, Set, Tuple

# Initialize logger
logger = logging.getLogger(__name__)


class CrawlerState:
    """Class for managing the crawler state to enable resuming from where it left off."""

    def __init__(self, state_dir: str):
        """
        Initialize the crawler state manager.

        Args:
            state_dir: Directory to save state files
        """
        self.state_dir = state_dir
        self.state_file = os.path.join(state_dir, "crawler_state.json")
        self.queue_file = os.path.join(state_dir, "priority_queue.pkl")
        self.logger = logging.getLogger(__name__)

        # Create the state directory if it doesn't exist
        os.makedirs(state_dir, exist_ok=True)

    def save_state(
        self,
        visited_urls: Set[str],
        priority_queue: List[Tuple[float, str, int]],
        current_url: str,
        current_depth: int,
    ) -> bool:
        """
        Save the current crawler state to disk.

        Args:
            visited_urls: Set of URLs that have been visited
            priority_queue: Current priority queue
            current_url: Last URL being processed
            current_depth: Current crawl depth

        Returns:
            True if state was saved successfully, False otherwise
        """
        try:
            # Create state JSON
            state = {
                "current_url": current_url,
                "current_depth": current_depth,
                "visited_count": len(visited_urls),
                "queue_count": len(priority_queue),
                "visited_urls": list(visited_urls),
            }

            # Save state JSON
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)

            # Save priority queue using pickle (as heapq structure is not JSON serializable)
            with open(self.queue_file, "wb") as f:
                pickle.dump(priority_queue, f)

            self.logger.info(
                f"Crawler state saved: {len(visited_urls)} URLs visited, {len(priority_queue)} URLs in queue"
            )
            self.logger.info(f"Last URL: {current_url} (depth: {current_depth})")
            return True

        except Exception as e:
            self.logger.error(f"Error saving crawler state: {str(e)}")
            return False

    def load_state(self) -> Dict[str, Any]:
        """
        Load crawler state from disk.

        Returns:
            Dictionary containing state information or empty dict if no state exists
        """
        # Check if state files exist
        if not (os.path.exists(self.state_file) and os.path.exists(self.queue_file)):
            self.logger.info("No previous crawler state found")
            return {}

        try:
            # Load state JSON
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            # Load priority queue
            with open(self.queue_file, "rb") as f:
                priority_queue = pickle.load(f)

            # Add priority queue to state
            state["priority_queue"] = priority_queue
            state["visited_urls"] = set(state["visited_urls"])

            self.logger.info(
                f"Loaded crawler state: {len(state['visited_urls'])} URLs visited, {len(priority_queue)} URLs in queue"
            )
            self.logger.info(
                f"Last URL: {state['current_url']} (depth: {state['current_depth']})"
            )

            return state

        except Exception as e:
            self.logger.error(f"Error loading crawler state: {str(e)}")
            return {}

    def clear_state(self) -> bool:
        """
        Clear the saved state files.

        Returns:
            True if files were cleared successfully or didn't exist, False otherwise
        """
        try:
            # Remove state files if they exist
            if os.path.exists(self.state_file):
                os.remove(self.state_file)

            if os.path.exists(self.queue_file):
                os.remove(self.queue_file)

            self.logger.info("Crawler state cleared")
            return True

        except Exception as e:
            self.logger.error(f"Error clearing crawler state: {str(e)}")
            return False

    def state_exists(self) -> bool:
        """
        Check if saved state exists.

        Returns:
            True if state exists, False otherwise
        """
        return os.path.exists(self.state_file) and os.path.exists(self.queue_file)
