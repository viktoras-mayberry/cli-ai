import copy


class Conversation:
    """Maintains conversation history in OpenAI message format.

    Supports named branches — each branch is an independent copy of the
    message list forked from a specific point. The active branch is tracked
    via self._active_branch. 'main' is always the default branch name.
    """

    def __init__(self, system_prompt: str = "Be precise and concise.") -> None:
        self._system_prompt = system_prompt
        self._branches: dict[str, list[dict]] = {"main": []}
        self._active_branch: str = "main"

    # ------------------------------------------------------------------ #
    # Active branch access                                                 #
    # ------------------------------------------------------------------ #

    @property
    def _messages(self) -> list[dict]:
        return self._branches[self._active_branch]

    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> list[dict]:
        return list(self._messages)

    def clear(self) -> None:
        self._branches = {"main": []}
        self._active_branch = "main"

    def is_empty(self) -> bool:
        return len(self._messages) == 0

    def __len__(self) -> int:
        return len(self._messages)

    # ------------------------------------------------------------------ #
    # Branching                                                            #
    # ------------------------------------------------------------------ #

    @property
    def active_branch(self) -> str:
        return self._active_branch

    def branch_names(self) -> list[str]:
        return list(self._branches.keys())

    def branch(self, name: str) -> bool:
        """Fork the current branch into a new branch named `name`.
        Returns False if the name already exists."""
        if name in self._branches:
            return False
        self._branches[name] = copy.deepcopy(self._messages)
        self._active_branch = name
        return True

    def checkout(self, name: str) -> bool:
        """Switch the active branch. Returns False if branch doesn't exist."""
        if name not in self._branches:
            return False
        self._active_branch = name
        return True

    def delete_branch(self, name: str) -> bool:
        """Delete a branch. Cannot delete the active branch or 'main'."""
        if name == self._active_branch or name == "main":
            return False
        if name not in self._branches:
            return False
        del self._branches[name]
        return True

    def branch_info(self) -> list[dict]:
        """Return metadata for all branches."""
        return [
            {
                "name": name,
                "messages": len(msgs),
                "active": name == self._active_branch,
            }
            for name, msgs in self._branches.items()
        ]
