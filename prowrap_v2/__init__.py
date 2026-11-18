"""Shared calculation package for PROWRAP single-repair and batch apps."""
__version__ = "2.0.0"
ISO_STANDARD = "ISO 24817:2017"
PROCUREMENT_REPORT_VERSION = "all-plies-width-metres-1"

LEGACY_INPUT_FIELDS = frozenset({
    "axial_mawp_bar",
    "assessed_axial_capacity_kn",
    "thicker_repair_limit_mm",
    "thicker_repair_ref",
})
