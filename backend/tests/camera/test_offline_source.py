from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from yyt1771_af.camera.offline import EndOfOfflineStreamError, OfflineFolderCameraSource
from yyt1771_af.services.camera_service import CameraService


def _write_frame(path: Path, value: int, *, shape: tuple[int, int] = (8, 10)) -> None:
    np.save(path, np.full(shape, value, dtype=np.uint8))


def test_offline_source_reads_zero_padded_npy_files_in_natural_order(tmp_path: Path) -> None:
    _write_frame(tmp_path / "frame_000010.npy", 10)
    _write_frame(tmp_path / "frame_000002.npy", 2)
    _write_frame(tmp_path / "frame_000001.npy", 1)

    source = OfflineFolderCameraSource(tmp_path)
    source.open()

    frames = [source.get_latest_frame() for _ in range(3)]

    assert [frame.frame_name for frame in frames] == [
        "frame_000001.npy",
        "frame_000002.npy",
        "frame_000010.npy",
    ]
    assert [int(frame.image[0, 0]) for frame in frames] == [1, 2, 10]


def test_offline_source_reads_non_padded_npy_files_in_natural_order(tmp_path: Path) -> None:
    _write_frame(tmp_path / "frame_10.npy", 10)
    _write_frame(tmp_path / "frame_2.npy", 2)
    _write_frame(tmp_path / "frame_1.npy", 1)

    source = OfflineFolderCameraSource(tmp_path)
    source.open()

    frames = [source.get_latest_frame() for _ in range(3)]

    assert [frame.frame_name for frame in frames] == [
        "frame_1.npy",
        "frame_2.npy",
        "frame_10.npy",
    ]


def test_offline_source_uses_allow_pickle_false_for_npy(monkeypatch, tmp_path: Path) -> None:
    _write_frame(tmp_path / "frame_1.npy", 1)
    load_calls: list[dict[str, object]] = []
    original_load = np.load

    def spy_load(*args: object, **kwargs: object) -> object:
        load_calls.append(dict(kwargs))
        return original_load(*args, **kwargs)

    monkeypatch.setattr(np, "load", spy_load)
    source = OfflineFolderCameraSource(tmp_path)
    source.open()

    source.get_latest_frame()

    assert load_calls[-1]["allow_pickle"] is False


def test_offline_source_reads_frame_by_index_without_advancing_stream(tmp_path: Path) -> None:
    for index in [10, 2, 1]:
        _write_frame(tmp_path / f"frame_{index}.npy", index)
    source = OfflineFolderCameraSource(tmp_path)
    source.open()

    indexed = source.read_frame(2)
    first = source.get_latest_frame()

    assert indexed.frame_index == 2
    assert indexed.frame_name == "frame_10.npy"
    assert int(indexed.image[0, 0]) == 10
    assert first.frame_index == 0
    assert first.frame_name == "frame_1.npy"


def test_offline_source_read_frame_rejects_invalid_index(tmp_path: Path) -> None:
    _write_frame(tmp_path / "frame_1.npy", 1)
    source = OfflineFolderCameraSource(tmp_path)
    source.open()

    with pytest.raises(IndexError, match="outside available frames"):
        source.read_frame(1)


def test_offline_source_does_not_preload_image_arrays(tmp_path: Path) -> None:
    for index in range(5):
        _write_frame(tmp_path / f"frame_{index + 1}.npy", index + 1)

    source = OfflineFolderCameraSource(tmp_path)
    source.open()

    assert source.frame_count == 5
    assert source.cached_image_count == 0

    source.get_latest_frame()

    assert source.cached_image_count == 0


def test_offline_source_stops_at_end_unless_loop_is_enabled(tmp_path: Path) -> None:
    _write_frame(tmp_path / "frame_1.npy", 1)
    source = OfflineFolderCameraSource(tmp_path, loop=False)
    source.open()

    assert source.get_latest_frame().frame_name == "frame_1.npy"
    with pytest.raises(EndOfOfflineStreamError):
        source.get_latest_frame()

    loop_source = OfflineFolderCameraSource(tmp_path, loop=True)
    loop_source.open()
    assert loop_source.get_latest_frame().frame_name == "frame_1.npy"
    assert loop_source.get_latest_frame().frame_name == "frame_1.npy"


def test_offline_source_rejects_3d_npy_frames_explicitly(tmp_path: Path) -> None:
    np.save(tmp_path / "frame_1.npy", np.zeros((4, 5, 3), dtype=np.uint8))
    source = OfflineFolderCameraSource(tmp_path)
    source.open()

    with pytest.raises(ValueError, match="2D grayscale"):
        source.get_latest_frame()


def test_camera_service_cache_is_bounded_for_many_offline_frames(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for index in range(20):
        _write_frame(frames_dir / f"frame_{index + 1}.npy", index + 1)

    monkeypatch.setenv("YYT1771_AF_OFFLINE_DIR", str(frames_dir))
    service = CameraService(max_cached_frames=3)

    service.open("dev_offline")
    for _ in range(12):
        service.get_latest_frame()

    assert service.cached_frame_count <= 3


def test_camera_service_opens_offline_folder_from_yaml_profile(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    _write_frame(frames_dir / "frame_1.npy", 1, shape=(5, 7))
    profile_path = tmp_path / "dev_offline.local.yaml"
    profile_path.write_text(
        f"""
profile_name: dev_offline_local
camera:
  type: offline_folder
  image_folder: "{frames_dir}"
  loop: false
""",
        encoding="utf-8",
    )
    service = CameraService()

    result = service.open(str(profile_path))
    status = service.status()

    assert result.source_type == "offline"
    assert status.frame_width == 7
    assert status.frame_height == 5
