"""内容寻址存储与版本库单测。"""

from butler.core.artifact_store import ArtifactStore
from butler.core.version_store import VersionStore


def test_artifact_put_and_dedupe(tmp_path):
    store = ArtifactStore(tmp_path / "artifacts")
    sha1 = store.put_bytes(b"hello")
    sha2 = store.put_bytes(b"hello")
    assert sha1 == sha2
    assert store.read_bytes(sha1) == b"hello"
    assert store.total_size() == 5


def test_text_snapshot_diff_restore(tmp_path):
    store = ArtifactStore(tmp_path / "artifacts")
    versioning = VersionStore(
        db_path=tmp_path / "versions.db",
        shadow_repo=tmp_path / "shadow",
        artifact=store,
    )
    doc = tmp_path / "note.md"
    doc.write_text("第一版\n", encoding="utf-8")
    first = versioning.snapshot(doc, "v1")
    doc.write_text("第二版\n新增\n", encoding="utf-8")
    second = versioning.snapshot(doc, "v2")

    assert first["backend"] == "shadow"
    assert len(versioning.list_versions(doc)) == 2
    diff_text = versioning.diff(doc)
    assert "+新增" in diff_text

    versioning.restore(doc, first["ref"])
    assert doc.read_text(encoding="utf-8") == "第一版\n"
    assert second["kind"] == "text"


def test_media_snapshot(tmp_path):
    store = ArtifactStore(tmp_path / "artifacts")
    versioning = VersionStore(
        db_path=tmp_path / "versions.db",
        shadow_repo=tmp_path / "shadow",
        artifact=store,
    )
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake-video-bytes")
    record = versioning.snapshot(media, "media")
    assert record["backend"] == "artifact"
    assert record["kind"] == "video"
    assert store.exists(record["ref"])
