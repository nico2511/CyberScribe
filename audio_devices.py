"""PyAudio input device enumeration and name resolution (no CyberScribe import)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

INPUT_DEVICE_NAME_MAX_LEN = 256


@dataclass(frozen=True)
class InputDeviceInfo:
    index: int
    name: str


def sanitize_input_device_name(raw) -> str:
    if raw is None:
        return ""
    return str(raw).strip()[:INPUT_DEVICE_NAME_MAX_LEN]


def enumerate_input_devices(pyaudio_instance: Any) -> List[InputDeviceInfo]:
    out: List[InputDeviceInfo] = []
    try:
        count = int(pyaudio_instance.get_device_count())
    except Exception:
        return out
    for index in range(count):
        try:
            info = pyaudio_instance.get_device_info_by_index(index)
        except Exception:
            continue
        if int(info.get("maxInputChannels") or 0) < 1:
            continue
        name = str(info.get("name") or "").strip()
        if name:
            out.append(InputDeviceInfo(index=index, name=name))
    return out


@dataclass(frozen=True)
class InputDeviceResolution:
    """``index`` is None when the OS default input device should be used."""

    index: Optional[int]
    requested_name: str
    matched_by_name: bool


def resolve_input_device_index(
    pyaudio_instance: Any,
    device_name: str,
) -> InputDeviceResolution:
    requested = sanitize_input_device_name(device_name)
    if not requested:
        return InputDeviceResolution(None, "", True)

    for dev in enumerate_input_devices(pyaudio_instance):
        if dev.name == requested:
            return InputDeviceResolution(dev.index, requested, True)
    return InputDeviceResolution(None, requested, False)


def device_names_for_tray(devices: Sequence[InputDeviceInfo]) -> List[Tuple[str, str]]:
    """Return (label, stored_name) pairs; first entry is always the default."""
    items = [("Par défaut (Windows)", "")]
    for dev in devices:
        label = dev.name if len(dev.name) <= 48 else dev.name[:45] + "…"
        items.append((label, dev.name))
    return items