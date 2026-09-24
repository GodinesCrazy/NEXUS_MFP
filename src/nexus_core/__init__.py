"""Testable methodological primitives for NEXUS-MFP."""

from .embedded import registered_module
from .bootstrap import BootstrapEvidence, paired_block_bootstrap
from .decisions import DecisionPolicy, DecisionResult, ForecastDistribution
from .provenance import SourceRecord, promotion_eligibility
from .reproducibility import file_sha256, mapping_fingerprint, pandas_fingerprint
from .scenarios import linear_portfolio_shock, transaction_cost_sensitivity
from .statistics import benjamini_hochberg, combined_pvalue, safe_corr_pvalue
from .temporal import mature_label_mask, purge_labeled_frame
from .vintages import SnapshotMetadata, VintageSnapshotStore

__all__ = [
    "SourceRecord",
    "BootstrapEvidence",
    "DecisionPolicy",
    "DecisionResult",
    "ForecastDistribution",
    "SnapshotMetadata",
    "VintageSnapshotStore",
    "benjamini_hochberg",
    "combined_pvalue",
    "file_sha256",
    "mapping_fingerprint",
    "linear_portfolio_shock",
    "mature_label_mask",
    "paired_block_bootstrap",
    "promotion_eligibility",
    "purge_labeled_frame",
    "pandas_fingerprint",
    "registered_module",
    "safe_corr_pvalue",
    "transaction_cost_sensitivity",
]
