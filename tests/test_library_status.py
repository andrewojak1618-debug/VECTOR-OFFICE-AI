"""Tests for the count-only local knowledge library status tool."""

import unittest
from unittest.mock import MagicMock

from memory.models import DocumentIndexStatus, KnowledgeDocument
from tools.library_status import LibraryInventory, register_local_library_status_tool
from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry, ToolResultStatus


def _status(
    document_id: int,
    chunks: int,
    current: int,
    stale: int,
) -> DocumentIndexStatus:
    document = KnowledgeDocument(
        document_id,
        f"C:/private/secret-{document_id}.md",
        f"Private title {document_id}",
        "a" * 64,
        "2026-08-21 10:00:00",
    )
    return DocumentIndexStatus(
        document,
        1,
        chunks,
        "embeddinggemma",
        "version-one",
        768,
        current,
        stale,
    )


class LocalLibraryStatusToolTests(unittest.TestCase):
    def setUp(self):
        self.reader = MagicMock(return_value=(
            _status(1, 3, 2, 1),
            _status(2, 2, 2, 0),
        ))
        self.registry = ToolRegistry()
        register_local_library_status_tool(self.registry, self.reader)

    def test_definition_is_argument_free_and_read_only(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("knowledge.library_status", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_status_returns_only_aggregate_counts(self):
        result = self.registry.execute("knowledge.library_status", {})

        self.assertTrue(result.succeeded)
        self.assertEqual(
            {
                "documents": 2,
                "chunks": 5,
                "current_vectors": 4,
                "stale_vectors": 1,
                "spoken_text": (
                    "Die lokale Wissensbibliothek enthält 2 Dokumente mit "
                    "5 Abschnitten. 4 Vektoren sind aktuell. 1 Vektor ist veraltet."
                ),
            },
            dict(result.output),
        )
        self.assertNotIn("private", str(result.output).casefold())
        self.assertNotIn("embeddinggemma", str(result.output))

    def test_empty_library_is_spoken_without_metadata(self):
        self.reader.return_value = ()

        result = self.registry.execute("knowledge.library_status", {})

        self.assertEqual(0, result.output["documents"])
        self.assertEqual(
            "Die lokale Wissensbibliothek ist leer.",
            result.output["spoken_text"],
        )

    def test_parameters_are_rejected_before_database_access(self):
        result = self.registry.execute(
            "knowledge.library_status",
            {"path": "C:/private"},
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.reader.assert_not_called()

    def test_invalid_reader_result_is_sanitized_by_registry(self):
        self.reader.return_value = ("private document",)

        result = self.registry.execute("knowledge.library_status", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    def test_inventory_rejects_unbounded_or_non_integer_counts(self):
        with self.assertRaises(ValueError):
            LibraryInventory(-1, 0, 0, 0)
        with self.assertRaises(TypeError):
            LibraryInventory(1, 1.5, 0, 0)


if __name__ == "__main__":
    unittest.main()
