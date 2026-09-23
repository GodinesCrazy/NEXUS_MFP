"""Testable methodological primitives for NEXUS-MFP."""

from .embedded import registered_module
from .provenance import SourceRecord, promotion_eligibility
from .reproducibility import file_sha256, mapping_fingerprint, pandas_fingerprint
from .statistics import benjamini_hochberg, combined_pvalue, safe_corr_pvalue
from .temporal import mature_label_mask, purge_labeled_frame

__all__ = [
    "SourceRecord",
    "benjamini_hochberg",
    "combined_pvalue",
    "file_sha256",
    "mapping_fingerprint",
    "mature_label_mask",
    "promotion_eligibility",
    "purge_labeled_frame",
    "pandas_fingerprint",
    "registered_module",
    "safe_corr_pvalue",
]
