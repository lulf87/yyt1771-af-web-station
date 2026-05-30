from __future__ import annotations

import ctypes
import importlib
import os
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from yyt1771_af.core.models import Frame
from yyt1771_af.core.statuses import CoordinateSpace


class HikMvsError(RuntimeError):
    pass


class HikMvsSdkUnavailableError(HikMvsError):
    pass


class HikMvsDeviceNotFoundError(HikMvsError):
    pass


class HikMvsFrameError(HikMvsError):
    pass


class HikMvsUnsupportedPixelFormatError(HikMvsFrameError):
    pass


@dataclass(frozen=True, slots=True)
class _DeviceCandidate:
    raw_info: Any
    serial_number: str | None
    device_ip: str | None
    user_defined_name: str | None
    model_name: str | None


class HikMvsCameraSource:
    source_type = "hik_mvs"

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._config = dict(config or {})
        self._sdk: Any | None = None
        self._camera: Any | None = None
        self._opened = False
        self._grabbing = False
        self._frame_counter = 0

    def open(self) -> None:
        self.close()
        self._sdk = self._load_sdk()
        candidate = self._select_device()
        camera = self._sdk.MvCamera()

        try:
            self._check_ret(
                "MV_CC_CreateHandle",
                camera.MV_CC_CreateHandle(candidate.raw_info),
            )
            self._check_ret(
                "MV_CC_OpenDevice",
                camera.MV_CC_OpenDevice(int(self._sdk.MV_ACCESS_Exclusive), 0),
            )
            self._camera = camera
            self._opened = True
            self._configure_camera()
            self._check_ret("MV_CC_StartGrabbing", camera.MV_CC_StartGrabbing())
            self._grabbing = True
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        camera = self._camera
        if camera is not None:
            if self._grabbing:
                _call_ignore(camera, "MV_CC_StopGrabbing")
            if self._opened:
                _call_ignore(camera, "MV_CC_CloseDevice")
            _call_ignore(camera, "MV_CC_DestroyHandle")
        self._camera = None
        self._sdk = None
        self._opened = False
        self._grabbing = False

    def get_latest_frame(self) -> Frame:
        if self._camera is None or self._sdk is None or not self._opened:
            raise RuntimeError("Hik MVS camera source is not opened")
        frame_out = self._sdk.MV_FRAME_OUT()
        timeout_ms = _int_config(self._config, "grab_timeout_ms", default=1000)
        acquired = False
        try:
            ret = _call_with_optional_byref(
                self._camera.MV_CC_GetImageBuffer,
                frame_out,
                timeout_ms,
            )
            self._check_ret("MV_CC_GetImageBuffer", ret)
            acquired = True
            image = self._mono8_image_from_frame(frame_out)
        finally:
            if acquired:
                self._check_ret(
                    "MV_CC_FreeImageBuffer",
                    _call_with_optional_byref(self._camera.MV_CC_FreeImageBuffer, frame_out),
                )

        self._frame_counter += 1
        return Frame(
            frame_id=self._frame_counter,
            timestamp_ms=time.time_ns() // 1_000_000,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            coordinate_space=CoordinateSpace.ACQUISITION,
            image=image,
            frame_name=f"hik_mvs_{self._frame_counter:06d}",
            frame_index=self._frame_counter - 1,
            dtype=str(image.dtype),
        )

    def _load_sdk(self) -> Any:
        sdk_path = _optional_text(
            os.environ.get("YYT1771_AF_HIK_MVS_SDK_PATH") or self._config.get("sdk_path")
        )
        if sdk_path is not None:
            search_path = Path(sdk_path)
            if search_path.is_file():
                search_path = search_path.parent
            if str(search_path) not in sys.path:
                sys.path.insert(0, str(search_path))

        configured_module = _optional_text(
            os.environ.get("YYT1771_AF_HIK_MVS_MODULE") or self._config.get("sdk_module")
        )
        module_names = [configured_module or "MvCameraControl_class"]
        if configured_module is None:
            module_names.append("MvImport.MvCameraControl_class")

        errors: list[str] = []
        for module_name in module_names:
            try:
                return importlib.import_module(module_name)
            except ImportError as exc:
                errors.append(f"{module_name}: {exc}")

        raise HikMvsSdkUnavailableError(
            "Hik MVS Python SDK module could not be imported. "
            "Set YYT1771_AF_HIK_MVS_MODULE or YYT1771_AF_HIK_MVS_SDK_PATH, "
            f"or configure camera.sdk_module/sdk_path. Tried: {'; '.join(errors)}"
        )

    def _select_device(self) -> _DeviceCandidate:
        if self._sdk is None:
            raise HikMvsSdkUnavailableError("Hik MVS SDK is not loaded")
        device_list = self._sdk.MV_CC_DEVICE_INFO_LIST()
        self._check_ret(
            "MV_CC_EnumDevices",
            self._sdk.MvCamera.MV_CC_EnumDevices(self._transport_layer_type(), device_list),
        )
        candidates = [
            self._candidate_from_raw_info(device_list.pDeviceInfo[index])
            for index in range(int(device_list.nDeviceNum))
        ]
        if not candidates:
            raise HikMvsDeviceNotFoundError("No Hik MVS GigE camera was discovered on the LAN")

        serial_number = _optional_text(
            os.environ.get("YYT1771_AF_HIK_MVS_SERIAL") or self._config.get("serial_number")
        )
        device_ip = _optional_text(
            os.environ.get("YYT1771_AF_HIK_MVS_DEVICE_IP") or self._config.get("device_ip")
        )
        user_defined_name = _optional_text(self._config.get("user_defined_name"))

        for candidate in candidates:
            if serial_number is not None and candidate.serial_number != serial_number:
                continue
            if device_ip is not None and candidate.device_ip != device_ip:
                continue
            if user_defined_name is not None and candidate.user_defined_name != user_defined_name:
                continue
            return candidate

        selectors = {
            "serial_number": serial_number,
            "device_ip": device_ip,
            "user_defined_name": user_defined_name,
        }
        requested = ", ".join(f"{key}={value}" for key, value in selectors.items() if value)
        discovered = "; ".join(_candidate_summary(candidate) for candidate in candidates)
        raise HikMvsDeviceNotFoundError(
            f"No Hik MVS camera matched {requested or 'the default selector'}. "
            f"Discovered: {discovered}"
        )

    def _candidate_from_raw_info(self, raw_info: Any) -> _DeviceCandidate:
        info = _dereference_device_info(self._sdk, raw_info)
        gige_info = _nested_attr(info, "SpecialInfo", "stGigEInfo")
        usb_info = _nested_attr(info, "SpecialInfo", "stUsb3VInfo")
        device_info = gige_info or usb_info
        return _DeviceCandidate(
            raw_info=raw_info,
            serial_number=_decode_sdk_string(getattr(device_info, "chSerialNumber", None)),
            device_ip=_ip_from_mvs_int(getattr(gige_info, "nCurrentIp", None)),
            user_defined_name=_decode_sdk_string(getattr(device_info, "chUserDefinedName", None)),
            model_name=_decode_sdk_string(getattr(device_info, "chModelName", None)),
        )

    def _transport_layer_type(self) -> int:
        transport_layer = str(self._config.get("transport_layer", "gige")).strip().lower()
        gige = int(self._sdk.MV_GIGE_DEVICE)
        usb = int(getattr(self._sdk, "MV_USB_DEVICE", 0))
        if transport_layer in {"all", "any"}:
            return gige | usb
        if transport_layer in {"usb", "usb3", "usb3v"}:
            return usb
        return gige

    def _configure_camera(self) -> None:
        if self._camera is None or self._sdk is None:
            raise RuntimeError("Hik MVS camera source is not opened")

        self._set_enum("TriggerMode", getattr(self._sdk, "MV_TRIGGER_MODE_OFF", 0))
        pixel_format = str(self._config.get("pixel_format", "mono8")).strip().lower()
        if pixel_format == "mono8":
            mono8_value = getattr(self._sdk, "PixelType_Gvsp_Mono8", None)
            if mono8_value is not None:
                self._set_enum("PixelFormat", int(mono8_value))
        else:
            raise HikMvsUnsupportedPixelFormatError(
                f"unsupported Hik MVS pixel_format {pixel_format!r}; only mono8 is supported"
            )

        frame_rate_hz = _float_config(self._config, "frame_rate_hz")
        if frame_rate_hz is not None:
            self._set_bool("AcquisitionFrameRateEnable", True)
            self._set_float("AcquisitionFrameRate", frame_rate_hz)

        exposure_us = _float_config(self._config, "exposure_us")
        if exposure_us is not None:
            self._set_float("ExposureTime", exposure_us)

        gain = _float_config(self._config, "gain")
        if gain is not None:
            self._set_float("Gain", gain)

        roi = self._config.get("device_roi")
        roi_config = roi if isinstance(roi, Mapping) else {}
        offset_x = _int_config(roi_config, "x")
        offset_y = _int_config(roi_config, "y")
        width = _int_config(roi_config, "width") or _int_config(self._config, "frame_width")
        height = _int_config(roi_config, "height") or _int_config(self._config, "frame_height")
        if offset_x is not None:
            self._set_int("OffsetX", offset_x)
        if offset_y is not None:
            self._set_int("OffsetY", offset_y)
        if width is not None:
            self._set_int("Width", width)
        if height is not None:
            self._set_int("Height", height)

    def _mono8_image_from_frame(self, frame_out: Any) -> np.ndarray:
        frame_info = frame_out.stFrameInfo
        width = int(frame_info.nWidth)
        height = int(frame_info.nHeight)
        frame_len = int(getattr(frame_info, "nFrameLen", width * height))
        pixel_type = int(getattr(frame_info, "enPixelType", 0))
        mono8_values = {
            int(value)
            for value in (
                getattr(self._sdk, "PixelType_Gvsp_Mono8", None),
                0x01080001,
            )
            if value is not None
        }
        if pixel_type != 0 and pixel_type not in mono8_values:
            raise HikMvsUnsupportedPixelFormatError(
                f"unsupported Hik MVS pixel type 0x{pixel_type:x}; "
                "configure camera pixel_format=mono8"
            )
        if width <= 0 or height <= 0:
            raise HikMvsFrameError("Hik MVS frame has invalid dimensions")

        address = _buffer_address(frame_out.pBufAddr)
        expected_len = width * height
        if frame_len < expected_len:
            raise HikMvsFrameError(
                f"Hik MVS frame buffer is shorter than dimensions require: "
                f"{frame_len} < {expected_len}"
            )
        data = ctypes.string_at(address, frame_len)
        return np.frombuffer(data, dtype=np.uint8, count=expected_len).reshape(height, width).copy()

    def _set_enum(self, name: str, value: int) -> None:
        method = getattr(self._camera, "MV_CC_SetEnumValue", None)
        if callable(method):
            self._check_ret(f"MV_CC_SetEnumValue({name})", method(name, int(value)))

    def _set_bool(self, name: str, value: bool) -> None:
        method = getattr(self._camera, "MV_CC_SetBoolValue", None)
        if callable(method):
            self._check_ret(f"MV_CC_SetBoolValue({name})", method(name, bool(value)))

    def _set_float(self, name: str, value: float) -> None:
        method = getattr(self._camera, "MV_CC_SetFloatValue", None)
        if callable(method):
            self._check_ret(f"MV_CC_SetFloatValue({name})", method(name, float(value)))

    def _set_int(self, name: str, value: int) -> None:
        method = getattr(self._camera, "MV_CC_SetIntValue", None)
        if callable(method):
            self._check_ret(f"MV_CC_SetIntValue({name})", method(name, int(value)))

    def _check_ret(self, operation: str, ret: int | None) -> None:
        ok = int(getattr(self._sdk, "MV_OK", 0)) if self._sdk is not None else 0
        if ret is not None and int(ret) != ok:
            raise HikMvsError(f"{operation} failed with Hik MVS error code 0x{int(ret):x}")


def _call_with_optional_byref(method: Any, *args: Any) -> Any:
    try:
        return method(*args)
    except TypeError:
        first, *rest = args
        return method(ctypes.byref(first), *rest)


def _call_ignore(target: Any, method_name: str) -> None:
    method = getattr(target, method_name, None)
    if callable(method):
        try:
            method()
        except Exception:
            return


def _dereference_device_info(sdk: Any, raw_info: Any) -> Any:
    device_type = getattr(sdk, "MV_CC_DEVICE_INFO", None)
    if device_type is not None:
        try:
            return ctypes.cast(raw_info, ctypes.POINTER(device_type)).contents
        except (TypeError, ValueError):
            pass
    contents = getattr(raw_info, "contents", None)
    return contents if contents is not None else raw_info


def _nested_attr(value: Any, *names: str) -> Any | None:
    current = value
    for name in names:
        current = getattr(current, name, None)
        if current is None:
            return None
    return current


def _decode_sdk_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value
    else:
        try:
            text = bytes(value).split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
        except TypeError:
            text = str(value)
    return _optional_text(text)


def _ip_from_mvs_int(value: Any) -> str | None:
    if value is None:
        return None
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    return ".".join(str((numeric >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def _buffer_address(value: Any) -> int:
    if isinstance(value, int):
        address = value
    elif isinstance(value, ctypes.c_void_p):
        address = int(value.value or 0)
    else:
        address = int(ctypes.cast(value, ctypes.c_void_p).value or 0)
    if address <= 0:
        raise HikMvsFrameError("Hik MVS frame buffer address is empty")
    return address


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null"}:
        return None
    if text.startswith("REPLACE_WITH_"):
        return None
    return text


def _int_config(config: Mapping[str, Any], name: str, *, default: int | None = None) -> int | None:
    value = config.get(name, default)
    if value is None:
        return None
    return int(value)


def _float_config(config: Mapping[str, Any], name: str) -> float | None:
    value = config.get(name)
    if value is None:
        return None
    return float(value)


def _candidate_summary(candidate: _DeviceCandidate) -> str:
    parts = [
        f"serial={candidate.serial_number or 'unknown'}",
        f"ip={candidate.device_ip or 'unknown'}",
        f"name={candidate.user_defined_name or 'unknown'}",
        f"model={candidate.model_name or 'unknown'}",
    ]
    return "{" + ", ".join(parts) + "}"
