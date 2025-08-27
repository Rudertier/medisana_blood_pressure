"""Helper functions for the Medisana Blood Pressure integration.

This module contains utility functions such as masking sensitive data
(e.g., MAC addresses) before writing them to logs.
"""

def mask_mac(mac: str) -> str:
    """Return a masked MAC address for logging (keeps first 3 and last octet)."""
    parts = mac.split(":")
    if len(parts) != 6: #noqa PLR2004
        return mac  # fallback: return as-is if format is unexpected
    return f"{parts[0]}:{parts[1]}:{parts[2]}:XX:XX:{parts[5]}"