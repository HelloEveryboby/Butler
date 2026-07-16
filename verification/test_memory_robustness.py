import os
import shutil
import sqlite3
import pytest
import unittest.mock
from butler.core.memory.memory_engine import SQLiteLongMemory, LongMemoryItem

@pytest.fixture
def temp_db_dir(tmp_path):
    db_dir = tmp_path / "system_data"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir

def test_memory_write(temp_db_dir):
    db_path = str(temp_db_dir / "long_memory.db")
    memory = SQLiteLongMemory(collection_name="test_collection_write")

    with unittest.mock.patch("os.path.normpath", return_value=db_path):
        memory.init()
        item = LongMemoryItem.new(content="Hello Butler Memory", id="test_1", metadata={"ts": 123456})
        memory.save([item])

        # Verify it exists
        items = memory.get_recent_history(5)
        assert len(items) == 1
        assert items[0].content == "Hello Butler Memory"
        assert items[0].id == "test_1"

def test_memory_read(temp_db_dir):
    db_path = str(temp_db_dir / "long_memory.db")
    memory = SQLiteLongMemory(collection_name="test_collection_read")

    with unittest.mock.patch("os.path.normpath", return_value=db_path):
        memory.init()
        # Save an item
        item = LongMemoryItem.new(content="Hello world", id="test_read_1", metadata={"ts": 123456})
        memory.save([item])

        # Test searching memory
        results = memory.search("world", 10)
        assert len(results) >= 1
        assert results[0].content == "Hello world"

def test_memory_recovery(temp_db_dir):
    db_path = str(temp_db_dir / "long_memory.db")

    # 1. Corrupt the database by writing gibberish to the db file
    with open(db_path, "w") as f:
        f.write("Totally corrupted sqlite format gibberish")

    memory = SQLiteLongMemory(collection_name="test_collection_rec")

    with unittest.mock.patch("os.path.normpath", return_value=db_path):
        # 2. Re-initialize memory engine (should auto-recover, backup corrupt and start fresh)
        memory.init()

        # Verify that it initialized a clean working SQLite database instead of crashing
        item = LongMemoryItem.new(content="Recovered content", id="test_rec_1", metadata={})
        memory.save([item])

        results = memory.get_recent_history(5)
        assert len(results) == 1
        assert results[0].content == "Recovered content"

        # Check that corrupt backup exists
        files = os.listdir(str(temp_db_dir))
        assert any("corrupt" in f for f in files)
