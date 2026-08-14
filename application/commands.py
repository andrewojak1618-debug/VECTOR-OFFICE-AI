"""Console command routing for conversation sessions."""

from enum import Enum, auto

from brain.agent import Agent


class CommandResult(Enum):
    """Describe how the conversation loop should continue after a command."""

    NOT_HANDLED = auto()
    HANDLED = auto()
    EXIT = auto()


class ConsoleCommandHandler:
    """Handle explicit memory, document, and session commands."""

    def __init__(self, agent: Agent):
        self.agent = agent

    def handle(self, user_text: str) -> CommandResult:
        """Execute a recognized command and return its loop action."""
        command = user_text.casefold()
        exact_result = self._handle_exact_command(command)
        if exact_result is not CommandResult.NOT_HANDLED:
            return exact_result
        return self._handle_value_command(command, user_text)

    def _handle_exact_command(self, command: str) -> CommandResult:
        handlers = {
            "/exit": self._exit,
            "/clear": self._clear,
            "/memories": self._list_memories,
            "/documents": self._list_documents,
        }
        handler = handlers.get(command)
        return handler() if handler else CommandResult.NOT_HANDLED

    def _handle_value_command(
        self,
        command: str,
        user_text: str,
    ) -> CommandResult:
        handlers = (
            ("/remember ", self._remember),
            ("/forget ", self._forget_memory),
            ("/learn ", self._learn_document),
            ("/reindex ", self._reindex_document),
            ("/forget-document ", self._forget_document),
        )
        for prefix, handler in handlers:
            if command.startswith(prefix):
                handler(user_text[len(prefix):])
                return CommandResult.HANDLED
        return CommandResult.NOT_HANDLED

    @staticmethod
    def _exit() -> CommandResult:
        print("Conversation ended.")
        return CommandResult.EXIT

    def _clear(self) -> CommandResult:
        self.agent.context.clear()
        print("Conversation context cleared.")
        return CommandResult.HANDLED

    def _remember(self, content: str) -> None:
        store = self.agent.memory_store
        if store is None:
            print("Long-term memory is unavailable.")
            return
        memory = store.remember(content)
        print(f"Memory {memory.id} saved.")

    def _list_memories(self) -> CommandResult:
        store = self.agent.memory_store
        if store is None:
            print("Long-term memory is unavailable.")
            return CommandResult.HANDLED
        self._print_memories(store.list_memories())
        return CommandResult.HANDLED

    @staticmethod
    def _print_memories(memories) -> None:
        if not memories:
            print("No long-term memories saved.")
            return
        for memory in memories:
            print(f"[{memory.id}] {memory.content}")

    def _forget_memory(self, value: str) -> None:
        store = self.agent.memory_store
        if store is None:
            print("Long-term memory is unavailable.")
            return
        memory_id = self._parse_id(value, "/forget")
        if memory_id is not None:
            self._print_delete_result(store.forget(memory_id), "Memory", memory_id)

    def _learn_document(self, source_path: str) -> None:
        library = self.agent.knowledge_library
        if library is None:
            print("Document library is unavailable.")
            return
        try:
            result = library.import_document(source_path)
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"Document import failed: {exc}")
            return
        state = "imported" if result.changed else "already current"
        print(
            f"Document {result.document.id} {state} "
            f"({result.chunk_count} sections): {result.document.title}"
        )
        indexing = getattr(library, "last_indexing_result", None)
        if indexing is not None:
            self._print_indexing_result(indexing)

    def _reindex_document(self, value: str) -> None:
        library = self.agent.knowledge_library
        if library is None:
            print("Document library is unavailable.")
            return
        document_id = self._parse_id(value, "/reindex")
        if document_id is None:
            return
        try:
            result = library.reindex_document(document_id)
        except (RuntimeError, ValueError) as exc:
            print(f"Document reindex failed: {exc}")
            return
        self._print_indexing_result(result)

    @staticmethod
    def _print_indexing_result(result) -> None:
        mode = "full" if result.forced else "incremental"
        model_note = ", model change detected" if result.model_changed else ""
        print(
            f"Semantic index {mode}: {result.indexed_chunks} indexed, "
            f"{result.skipped_chunks} current{model_note}."
        )

    def _list_documents(self) -> CommandResult:
        library = self.agent.knowledge_library
        if library is None:
            print("Document library is unavailable.")
            return CommandResult.HANDLED
        self._print_documents(library.list_documents())
        return CommandResult.HANDLED

    @staticmethod
    def _print_documents(documents) -> None:
        if not documents:
            print("No documents imported.")
            return
        for document in documents:
            print(f"[{document.id}] {document.title} ({document.source_path})")

    def _forget_document(self, value: str) -> None:
        library = self.agent.knowledge_library
        if library is None:
            print("Document library is unavailable.")
            return
        document_id = self._parse_id(value, "/forget-document")
        if document_id is not None:
            deleted = library.forget_document(document_id)
            self._print_delete_result(deleted, "Document", document_id)

    @staticmethod
    def _parse_id(value: str, command: str) -> int | None:
        try:
            return int(value.strip())
        except ValueError:
            print(f"Usage: {command} ID")
            return None

    @staticmethod
    def _print_delete_result(deleted: bool, item: str, item_id: int) -> None:
        if deleted:
            print(f"{item} {item_id} deleted.")
            return
        print(f"{item} {item_id} was not found.")
