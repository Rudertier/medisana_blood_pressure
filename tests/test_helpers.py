import pytest
from custom_components.medisana_blood_pressure.medisana_bp.helpers import mask_mac


@pytest.mark.parametrize(
    "mac,expected",
    [
        ("AA:BB:CC:DD:EE:FF", "AA:BB:CC:XX:XX:FF"),
        ("00:11:22:33:44:55", "00:11:22:XX:XX:55"),
        (None, None),
        ("", None),
    ],
)
def test_mask_mac_valid(mac, expected):
    """Test that valid MAC addresses are masked correctly."""
    assert mask_mac(mac) == expected


@pytest.mark.parametrize(
    "invalid_mac",
    [
        "AA:BB:CC:DD:EE",   # too short
        "AABBCCDDEEFF",     # missing colons
        "AA:BB:CC:DD:EE:FF:GG",  # too long
    ],
)
def test_mask_mac_invalid(invalid_mac):
    """Test that invalid MAC addresses are returned unchanged."""
    # None will raise, so coerce to string
    mac_str = str(invalid_mac)
    assert mask_mac(mac_str) == mac_str
