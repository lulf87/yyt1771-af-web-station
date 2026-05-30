from __future__ import annotations

import ctypes
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from yyt1771_af.camera.hik_mvs import HikMvsCameraSource
from yyt1771_af.services.camera_service import CameraService


class _FakeGigEInfo:
    def __init__(
        self,
        *,
        serial_number: str,
        device_ip: str,
        model_name: str = "MV-FAKE",
        user_defined_name: str = "lab-camera",
    ) -> None:
        self.chSerialNumber = serial_number.encode("ascii")
        self.chModelName = model_name.encode("ascii")
        self.chUserDefinedName = user_defined_name.encode("ascii")
        self.nCurrentIp = _ip_to_mvs_int(device_ip)


class _FakeDeviceInfo:
    def __init__(self, sdk: ModuleType, *, serial_number: str, device_ip: str) -> None:
        self.nTLayerType = sdk.MV_GIGE_DEVICE
        self.SpecialInfo = SimpleNamespace(
            stGigEInfo=_FakeGigEInfo(serial_number=serial_number, device_ip=device_ip)
        )


def _install_fake_hik_sdk(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    sdk = ModuleType("fake_hik_mvs_sdk")
    sdk.MV_OK = 0
    sdk.MV_GIGE_DEVICE = 1
    sdk.MV_USB_DEVICE = 2
    sdk.MV_ACCESS_Exclusive = 3
    sdk.MV_TRIGGER_MODE_OFF = 0
    sdk.PixelType_Gvsp_Mono8 = 0x01080001

    class MV_CC_DEVICE_INFO_LIST:
        def __init__(self) -> None:
            self.nDeviceNum = 0
            self.pDeviceInfo: list[_FakeDeviceInfo] = []

    class MV_FRAME_OUT:
        def __init__(self) -> None:
            self.stFrameInfo = SimpleNamespace(
                nWidth=0,
                nHeight=0,
                nFrameLen=0,
                enPixelType=0,
            )
            self.pBufAddr: int | None = None

    class MvCamera:
        def __init__(self) -> None:
            self.created_handle_for: _FakeDeviceInfo | None = None
            self.opened = False
            self.grabbing = False
            self.destroyed = False
            self.enum_values: list[tuple[str, int]] = []
            self.float_values: list[tuple[str, float]] = []
            self.int_values: list[tuple[str, int]] = []
            self.bool_values: list[tuple[str, bool]] = []
            self.frame_buffers_freed = 0
            self._last_buffer: ctypes.Array[ctypes.c_ubyte] | None = None
            sdk.created_cameras.append(self)

        @staticmethod
        def MV_CC_EnumDevices(tlayer_type: int, device_list: MV_CC_DEVICE_INFO_LIST) -> int:
            sdk.last_enum_tlayer_type = tlayer_type
            device_list.nDeviceNum = len(sdk.devices)
            device_list.pDeviceInfo = list(sdk.devices)
            return sdk.MV_OK

        def MV_CC_CreateHandle(self, device_info: _FakeDeviceInfo) -> int:
            self.created_handle_for = device_info
            return sdk.MV_OK

        def MV_CC_OpenDevice(self, access_mode: int, switchover_key: int) -> int:
            assert access_mode == sdk.MV_ACCESS_Exclusive
            assert switchover_key == 0
            self.opened = True
            return sdk.MV_OK

        def MV_CC_SetEnumValue(self, name: str, value: int) -> int:
            self.enum_values.append((name, value))
            return sdk.MV_OK

        def MV_CC_SetFloatValue(self, name: str, value: float) -> int:
            self.float_values.append((name, value))
            return sdk.MV_OK

        def MV_CC_SetIntValue(self, name: str, value: int) -> int:
            self.int_values.append((name, value))
            return sdk.MV_OK

        def MV_CC_SetBoolValue(self, name: str, value: bool) -> int:
            self.bool_values.append((name, value))
            return sdk.MV_OK

        def MV_CC_StartGrabbing(self) -> int:
            self.grabbing = True
            return sdk.MV_OK

        def MV_CC_GetImageBuffer(self, frame_out: MV_FRAME_OUT, timeout_ms: int) -> int:
            assert timeout_ms == 1000
            pixels = [10, 20, 30, 40, 50, 60]
            self._last_buffer = (ctypes.c_ubyte * len(pixels))(*pixels)
            frame_out.stFrameInfo.nWidth = 3
            frame_out.stFrameInfo.nHeight = 2
            frame_out.stFrameInfo.nFrameLen = len(pixels)
            frame_out.stFrameInfo.enPixelType = sdk.PixelType_Gvsp_Mono8
            frame_out.pBufAddr = ctypes.addressof(self._last_buffer)
            return sdk.MV_OK

        def MV_CC_FreeImageBuffer(self, frame_out: MV_FRAME_OUT) -> int:
            assert frame_out.pBufAddr is not None
            self.frame_buffers_freed += 1
            return sdk.MV_OK

        def MV_CC_StopGrabbing(self) -> int:
            self.grabbing = False
            return sdk.MV_OK

        def MV_CC_CloseDevice(self) -> int:
            self.opened = False
            return sdk.MV_OK

        def MV_CC_DestroyHandle(self) -> int:
            self.destroyed = True
            return sdk.MV_OK

    sdk.MV_CC_DEVICE_INFO_LIST = MV_CC_DEVICE_INFO_LIST
    sdk.MV_FRAME_OUT = MV_FRAME_OUT
    sdk.MvCamera = MvCamera
    sdk.created_cameras = []
    sdk.devices = [
        _FakeDeviceInfo(sdk, serial_number="ABC123", device_ip="192.168.1.64"),
    ]
    monkeypatch.setitem(sys.modules, sdk.__name__, sdk)
    return sdk


def test_hik_source_opens_lan_camera_and_returns_mono8_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk = _install_fake_hik_sdk(monkeypatch)
    source = HikMvsCameraSource(
        {
            "sdk_module": sdk.__name__,
            "device_ip": "192.168.1.64",
            "pixel_format": "mono8",
            "frame_rate_hz": 12.5,
            "exposure_us": 4200.0,
            "gain": 1.25,
            "device_roi": {"x": 2, "y": 4, "width": 3, "height": 2},
        }
    )

    source.open()
    frame = source.get_latest_frame()

    camera = sdk.created_cameras[0]
    assert sdk.last_enum_tlayer_type == sdk.MV_GIGE_DEVICE
    assert camera.created_handle_for is sdk.devices[0]
    assert camera.opened is True
    assert camera.grabbing is True
    assert ("TriggerMode", sdk.MV_TRIGGER_MODE_OFF) in camera.enum_values
    assert ("PixelFormat", sdk.PixelType_Gvsp_Mono8) in camera.enum_values
    assert ("AcquisitionFrameRate", 12.5) in camera.float_values
    assert ("ExposureTime", 4200.0) in camera.float_values
    assert ("Gain", 1.25) in camera.float_values
    assert ("Width", 3) in camera.int_values
    assert ("Height", 2) in camera.int_values
    assert frame.frame_id == 1
    assert frame.frame_name == "hik_mvs_000001"
    assert frame.width == 3
    assert frame.height == 2
    assert frame.dtype == "uint8"
    np.testing.assert_array_equal(
        frame.image,
        np.array([[10, 20, 30], [40, 50, 60]], dtype=np.uint8),
    )
    assert camera.frame_buffers_freed == 1

    source.close()
    assert camera.opened is False
    assert camera.grabbing is False
    assert camera.destroyed is True


def test_hik_source_reports_missing_sdk_only_when_opening() -> None:
    source = HikMvsCameraSource({"sdk_module": "missing_hik_mvs_sdk_for_test"})

    with pytest.raises(RuntimeError, match="missing_hik_mvs_sdk_for_test"):
        source.open()


def test_camera_service_opens_dev_lab_profile_with_lazy_hik_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk = _install_fake_hik_sdk(monkeypatch)
    monkeypatch.setenv("YYT1771_AF_HIK_MVS_MODULE", sdk.__name__)
    service = CameraService()

    result = service.open("dev_lab")
    status = service.status()

    assert result.opened is True
    assert result.source_type == "hik_mvs"
    assert status.opened is True
    assert status.source_type == "hik_mvs"
    assert status.frame_width == 3
    assert status.frame_height == 2


def _ip_to_mvs_int(value: str) -> int:
    parts = [int(part) for part in value.split(".")]
    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]
