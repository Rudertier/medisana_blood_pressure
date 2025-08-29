"""Unit tests for the blood pressure data parser."""

from datetime import datetime
import struct

from custom_components.medisana_blood_pressure.medisana_bp.parser import (
    parse_blood_pressure,
)


def make_sfloat(value: float) -> bytes:
    """Encode a float into IEEE-11073 SFLOAT (approx, exponent=0)."""
    mantissa = int(value)
    raw = mantissa & 0x0FFF
    return struct.pack("<H", raw)


def test_parse_basic_measurement():
    """Test parsing a minimal measurement with only systolic/diastolic/MAP."""
    flags = 0x00
    systolic = make_sfloat(120)
    diastolic = make_sfloat(80)
    map_ = make_sfloat(95)

    data = bytes([flags]) + systolic + diastolic + map_
    result = parse_blood_pressure(data)

    assert result["systolic"] == 120  # noqa: PLR2004
    assert result["diastolic"] == 80  # noqa: PLR2004
    assert result["mean_arterial_pressure"] == 95  # noqa: PLR2004
    assert result["timestamp"] is None
    assert result["pulse_rate"] is None
    assert result["user_id"] is None
    assert result["measurement_status"] is None


def test_parse_with_timestamp_and_pulse():
    """Test parsing a measurement including timestamp and pulse rate."""
    flags = 0x02 | 0x04
    systolic = make_sfloat(125)
    diastolic = make_sfloat(85)
    map_ = make_sfloat(98)

    timestamp = struct.pack("<HBBBBB", 2023, 8, 27, 14, 30, 45)
    pulse = make_sfloat(72)

    data = bytes([flags]) + systolic + diastolic + map_ + timestamp + pulse
    result = parse_blood_pressure(data)

    assert result["systolic"] == 125  # noqa: PLR2004
    assert result["diastolic"] == 85  # noqa: PLR2004
    assert result["mean_arterial_pressure"] == 98  # noqa: PLR2004
    assert isinstance(result["timestamp"], datetime)
    assert result["timestamp"].year == 2023  # noqa: PLR2004
    assert result["pulse_rate"] == 72  # noqa: PLR2004
    assert result["user_id"] is None
    assert result["measurement_status"] is None


def test_parse_with_user_id_and_status():
    """Test parsing a measurement including user ID and status flags."""
    flags = 0x08 | 0x10
    systolic = make_sfloat(110)
    diastolic = make_sfloat(70)
    map_ = make_sfloat(90)

    user_id = bytes([3])
    status = struct.pack("<H", 0x1234)

    data = bytes([flags]) + systolic + diastolic + map_ + user_id + status
    result = parse_blood_pressure(data)

    assert result["systolic"] == 110  # noqa: PLR2004
    assert result["diastolic"] == 70  # noqa: PLR2004
    assert result["mean_arterial_pressure"] == 90  # noqa: PLR2004
    assert result["user_id"] == 3  # noqa: PLR2004
    assert result["measurement_status"] == 0x1234  # noqa: PLR2004
