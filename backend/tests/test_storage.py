from ragforge.models import Chunk, Document
from ragforge.storage import SQLiteStore


def test_documents_and_chunks_survive_restart(tmp_path):
    path = tmp_path / "data.db"
    d = Document("d1", "Guide", "hello world", {"source": "test"})
    c = Chunk("c1", "d1", "hello world", 0, 0, 11)
    SQLiteStore(path).put_document(d, [c])
    reopened = SQLiteStore(path)
    assert reopened.get_document("d1").text == "hello world"
    assert reopened.get_chunks()[0].id == "c1"


def test_delete_is_atomic_with_cascade(tmp_path):
    store = SQLiteStore(tmp_path / "data.db")
    store.put_document(Document("d1", "x", "x"), [Chunk("c1", "d1", "x", 0, 0, 1)])
    assert store.delete_document("d1")
    assert store.get_chunks() == []
