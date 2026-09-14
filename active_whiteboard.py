#!/usr/bin/env python3
"""
active_whiteboard.py — Active Whiteboard (AW) Context Ledger & State Manager
================================================================================
Manages conversational history, problem-solving paths, and state routing for EQ V2.0:
- Stack-based conversation ledger and path management.
- Handles forks, returns, loops, branches, and resets.
- Provides historical context for EnQuerant's deterministic review.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class WhiteboardNode:
    """Represents a single entry point or state branch on the Active Whiteboard."""
    node_id: int
    query: str
    response_summary: str
    f0_output: float
    nest_depth: float
    branch_tag: str = "main"


class ActiveWhiteboard:
    """
    Context ledger managing conversation path routing, forks, returns, loops,
    and history for the EnQuerant static logic crystal.
    """

    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self.nodes: List[WhiteboardNode] = []
        self.current_node_id = 0
        self.active_branch = "main"
        self.branch_checkpoints: Dict[str, int] = {"main": 0}
        # Pagination & Batch state management
        self.active_batch_options: List[Any] = []
        self.all_matched_records: List[Any] = []
        self.current_batch_index: int = 0
        self.batch_history: List[int] = []

    def push_state(self, query: str, response_summary: str, f0_output: float, nest_depth: float, branch: Optional[str] = None) -> WhiteboardNode:
        """Pushes a new deterministic state node onto the active whiteboard ledger."""
        self.current_node_id += 1
        target_branch = branch or self.active_branch
        
        node = WhiteboardNode(
            node_id=self.current_node_id,
            query=query,
            response_summary=response_summary,
            f0_output=f0_output,
            nest_depth=nest_depth,
            branch_tag=target_branch
        )
        
        self.nodes.append(node)
        if len(self.nodes) > self.max_history:
            self.nodes.pop(0)
            
        return node

    def fork_branch(self, branch_name: str) -> bool:
        """Forks a new conversational or problem-solving branch from current state."""
        clean_name = branch_name.strip()
        if not clean_name:
            return False
        self.active_branch = clean_name
        self.branch_checkpoints[clean_name] = self.current_node_id
        return True

    def create_branch(self, branch_name: str) -> bool:
        """Alias for fork_branch to support navigational control codes."""
        return self.fork_branch(branch_name)

    def return_to_branch(self, branch_name: str) -> bool:
        """Returns focus back to a previously established branch checkpoint."""
        if branch_name in self.branch_checkpoints:
            self.active_branch = branch_name
            return True
        return False

    def reset_board(self) -> None:
        """Resets the whiteboard ledger back to initial state zero."""
        self.nodes.clear()
        self.current_node_id = 0
        self.active_branch = "main"
        self.branch_checkpoints = {"main": 0}
        self.active_batch_options = []
        self.all_matched_records = []
        self.current_batch_index = 0
        self.batch_history = []

    def get_recent_history(self, limit: int = 5) -> List[WhiteboardNode]:
        """Retrieves recent nodes for contextual review."""
        return self.nodes[-limit:] if self.nodes else []
        
    def set_matched_records(self, records: List[Any]) -> None:
        """Sets all matched records and resets pagination batch indexing to the beginning."""
        self.all_matched_records = records
        self.current_batch_index = 0
        self.batch_history = []
        self._update_current_batch()

    def _update_current_batch(self) -> None:
        """Updates active batch options based on the current batch index (8 items per slice)."""
        start = self.current_batch_index * 8
        end = start + 8
        self.active_batch_options = self.all_matched_records[start:end]

    def next_batch(self) -> bool:
        """Advances to the next batch of 8 options if available."""
        if (self.current_batch_index + 1) * 8 < len(self.all_matched_records):
            self.batch_history.append(self.current_batch_index)
            self.current_batch_index += 1
            self._update_current_batch()
            return True
        return False

    def previous_batch(self) -> bool:
        """Returns to the previous batch slice using batch history stack."""
        if self.batch_history:
            self.current_batch_index = self.batch_history.pop()
            self._update_current_batch()
            return True
        elif self.current_batch_index > 0:
            self.current_batch_index -= 1
            self._update_current_batch()
            return True
        return False

    def get_latest_query(self) -> Optional[str]:
        """Retrieves the query string of the most recent whiteboard node."""
        return self.nodes[-1].query if self.nodes else None

    def get_ledger_summary(self) -> str:
        """Returns a string summary of the current active branch and node count."""
        return f"BRANCH:{self.active_branch} | NODES:{len(self.nodes)} | CURRENT_ID:{self.current_node_id}"


# Standalone Verification Test
if __name__ == "__main__":
    print("=" * 78)
    print("        ACTIVE WHITEBOARD (AW) LEDGER ENGINE TEST")
    print("=" * 78)

    aw = ActiveWhiteboard()
    aw.push_state("What is entropy?", "Analyzed thermodynamic dissipation.", 1.234, 1.0)
    aw.push_state("How does SPFS solve it?", "Applied polarity rebalancing.", 0.987, 2.1)
    
    aw.fork_branch("experimental_nest")
    aw.push_state("Test nested scaling", "Evaluated s -> infinity limit.", 0.543, 6.0, branch="experimental_nest")

    print(f"Ledger Summary : {aw.get_ledger_summary()}")
    print(f"Active Branch  : {aw.active_branch}")
    print(f"Total Nodes    : {len(aw.nodes)}")
    print("=" * 78)
