#!/usr/bin/env python3
"""
Atlas causal findings extraction (current corpus + v2/v2.1 lineage).

Generates a reproducible findings package for marketing and academic usage:
- Canonical edge table (optional CSV.GZ)
- Top 10 ranked findings + Top 4 public subset
- Evidence sheets per finding
- Lineage appendix (v2/v2.1)
- Exclusion audit + uncertainty flags

This script intentionally uses only Python stdlib to keep execution portable.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


# -----------------------------------------------------------------------------
# Paths and constants
# -----------------------------------------------------------------------------

STRATA = ("unified", "developing", "emerging", "advanced")
DECADE_BINS = (
    (1990, 1999, "1990s"),
    (2000, 2009, "2000s"),
    (2010, 2019, "2010s"),
    (2020, 2029, "2020s"),
)
FULL_GRAPH_COUNT = 140
YEARS_EXPECTED = 35

TARGET_TOP10_CLASS_QUOTAS = {
    "reversal": 4,
    "mediation": 3,
    "threshold": 2,
}

# User-locked reversal findings to retain.
FORCED_REVERSAL_EDGES = [
    ("GER.5T8.GPIA", "wdi_birth"),  # college enrollment gender gap -> birth rate
    ("gdiincj992", "warc_wmin"),  # income inequality -> armed conflict severity
    ("ygmxhni999", "chisols_warlord"),  # income per person -> child soldier recruitment
    ("mprpfci999", "mseccoi999"),  # middle class income share -> economic output
]

POLICY_LEVER_KEYWORDS = (
    "expenditure",
    "enrollment",
    "education",
    "health",
    "internet",
    "broadband",
    "electricity",
    "inflation",
    "tax",
    "governance",
    "democracy",
    "corruption",
    "trade",
    "emission",
    "renewable",
    "nutrition",
    "vaccin",
    "school",
    "labor",
    "employment",
    "unemployment",
    "inequality",
    "income share",
)

FINDING_SCHEMA = {
    "finding_id": "F01",
    "title": "...",
    "class": "mediation|reversal|threshold|hub|outcome_surprise",
    "variables": {
        "source": {"code": "...", "label": "..."},
        "mediator": {"code": "...", "label": "..."},
        "target": {"code": "...", "label": "..."},
    },
    "edge_type": "linear|threshold|quadratic|logarithmic|saturation|mixed",
    "availability": {"years_active": "X/35", "graphs_active": "X/140"},
    "stratum_betas": {
        "unified": {"beta": 0.0, "ci_lower": 0.0, "ci_upper": 0.0},
        "developing": {"beta": 0.0, "ci_lower": 0.0, "ci_upper": 0.0},
        "emerging": {"beta": 0.0, "ci_lower": 0.0, "ci_upper": 0.0},
        "advanced": {"beta": 0.0, "ci_lower": 0.0, "ci_upper": 0.0},
    },
    "temporal_profile": {
        "1990s": "...",
        "2000s": "...",
        "2010s": "...",
        "2020s": "...",
    },
    "directionality": {"reversal": True, "reverse_edge_presence": "X/140"},
    "nonlinearity": {
        "threshold": None,
        "beta_low": None,
        "beta_high": None,
        "flip_years": 0,
    },
    "lineage": {"v2_v21_status": "...", "notes": "..."},
    "caveats": ["..."],
    "plain_language": "...",
    "academic_summary": "...",
    "confidence": "high|medium|low",
}


# -----------------------------------------------------------------------------
# Data models
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class EdgeObs:
    source: str
    target: str
    stratum: str
    year: int
    beta: float
    ci_lower: Optional[float]
    ci_upper: Optional[float]
    p_value: Optional[float]
    lag: Optional[int]
    r_squared: Optional[float]
    n_samples: Optional[int]
    relationship_type: str
    nonlinearity_type: str
    nonlinearity_params: Dict[str, object]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def as_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def decade_label(year: int) -> str:
    for lo, hi, label in DECADE_BINS:
        if lo <= year <= hi:
            return label
    return "other"


def mean(values: Iterable[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def stdev(values: Iterable[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    var = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
    return math.sqrt(var)


def mode(values: Iterable[str], default: Optional[str] = "unknown") -> Optional[str]:
    c = Counter(v for v in values if v)
    if not c:
        return default
    return c.most_common(1)[0][0]


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def stable_hash(parts: Iterable[str]) -> str:
    payload = "|".join(parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


OUTCOME_CONCEPTS = {
    "life_expectancy": {
        "patterns": [r"life expectancy", r"lifexp", r"sp\.dyn\.le00"],
        "preferred": ["SP.DYN.LE00.IN", "wdi_lifexp", "wdi_lifexpf", "wdi_lifexpm"],
    },
    "education": {
        "patterns": [r"education", r"enrollment", r"school"],
        "preferred": ["SE.SEC.ENRR", "SE.PRM.ENRR", "GER.5T8.GPIA"],
    },
    "gdp_income": {
        "patterns": [r"gdp", r"gni", r"economic output", r"income per person"],
        "preferred": ["NY.GDP.MKTP.KD.ZG", "NY.GNP.MKTP.PC.CD", "mseccoi999", "ygmxhni999"],
    },
    "infant_mortality": {
        "patterns": [r"infant", r"neonatal", r"mortality"],
        "preferred": ["wdi_mortnn", "wdi_mortf"],
    },
    "inequality": {
        "patterns": [r"inequal", r"gini", r"income distribution"],
        "preferred": ["gdiincj999", "gdiincj992"],
    },
    "homicide_security": {
        "patterns": [r"homicide", r"murder", r"violence", r"conflict", r"child soldiers"],
        "preferred": ["warc_wmin", "chisols_warlord"],
    },
    "nutrition": {
        "patterns": [r"nutrition", r"malnutrition", r"stunting", r"undernour"],
        "preferred": [],
    },
    "internet_access": {
        "patterns": [r"internet", r"broadband", r"digital"],
        "preferred": ["wdi_interexp", "wdi_interrev"],
    },
}


def indicator_matches_outcome_concept(code: str, label: str, concept_cfg: dict) -> bool:
    hay = f"{code} {label}"
    for preferred in concept_cfg.get("preferred", []):
        if code == preferred:
            return True
    for pattern in concept_cfg.get("patterns", []):
        if re.search(pattern, hay, flags=re.IGNORECASE):
            return True
    return False


def classify_outcome_concept(code: str, label: str) -> Optional[str]:
    for concept, cfg in OUTCOME_CONCEPTS.items():
        if indicator_matches_outcome_concept(code, label, cfg):
            return concept
    return None


def is_policy_relevant_indicator(code: str, label: str, domain: str) -> bool:
    hay = normalize_text(f"{code} {label} {domain}")
    return any(token in hay for token in POLICY_LEVER_KEYWORDS)


# -----------------------------------------------------------------------------
# Interpretability filter
# -----------------------------------------------------------------------------


INTERPRETABILITY_BLOCK_PATTERNS = (
    (re.compile(r"^group_\d+$"), "hierarchy_group_id"),
    (re.compile(r"^coarse_\d+$"), "hierarchy_coarse_id"),
    (re.compile(r"^fine_\d+$"), "hierarchy_fine_id"),
    (re.compile(r"^\d+$"), "numeric_category_id"),
    (re.compile(r"^SP\.POP\."), "population_bucket_proxy_code"),
    (re.compile(r"^npopul"), "population_bucket_proxy_code"),
    (re.compile(r"_nr$"), "data_quality_suffix_nr"),
)

INTERPRETABILITY_BLOCK_TEXT = (
    ("data quality", "label_data_quality"),
    ("data availability", "label_data_availability"),
    ("coverage", "label_coverage_metric"),
    ("population count", "population_bucket_proxy"),
    ("total population", "population_bucket_proxy"),
    ("population ages", "population_bucket_proxy"),
    ("number of households", "population_bucket_proxy"),
    ("working-age men", "population_bucket_proxy"),
    ("working-age women", "population_bucket_proxy"),
    ("consumer spending category", "category_placeholder"),
)


def interpretability_reason(
    code: str,
    label: str,
    node_type: str,
    layer: Optional[int],
) -> Optional[str]:
    c = code.strip()
    t = normalize_text(label or "")

    if node_type in {"root", "outcome_category", "coarse_domain", "fine_domain"}:
        return "non_indicator_hierarchy_node"

    if layer is not None and layer <= 2:
        return "upper_hierarchy_layer"

    for pat, reason in INTERPRETABILITY_BLOCK_PATTERNS:
        if pat.search(c):
            return reason

    for token, reason in INTERPRETABILITY_BLOCK_TEXT:
        if token in t:
            return reason

    # Disallow raw "all groups/all population" aggregate placeholders when labels are generic.
    if ("all groups" in t or "all population" in t) and "income" not in t and "revenue" not in t:
        return "generic_population_aggregate"

    return None


# -----------------------------------------------------------------------------
# Corpus loading
# -----------------------------------------------------------------------------


class Corpus:
    def __init__(self, repo_root: Path, write_canonical_csv: bool = True):
        self.repo_root = repo_root
        self.viz_root = repo_root / "viz"
        self.graph_paths = {
            "unified": self.viz_root / "data" / "v31" / "temporal_graphs" / "unified",
            "developing": self.viz_root / "data" / "v31" / "temporal_graphs" / "stratified" / "developing",
            "emerging": self.viz_root / "data" / "v31" / "temporal_graphs" / "stratified" / "emerging",
            "advanced": self.viz_root / "data" / "v31" / "temporal_graphs" / "stratified" / "advanced",
        }
        self.metadata_path = self.viz_root / "data" / "v31" / "metadata" / "indicator_properties.json"
        self.income_path = self.viz_root / "data" / "v31" / "metadata" / "income_classifications.json"
        self.baselines_root = self.viz_root / "data" / "v31" / "baselines"
        self.v21_edges_paths = [
            self.viz_root / "data" / "raw" / "v21_causal_edges.csv",
            repo_root / "v2.1" / "outputs" / "v3_exports" / "v21_causal_edges.csv",
        ]
        self.v21_nodes_paths = [
            self.viz_root / "data" / "raw" / "v21_nodes.csv",
            repo_root / "v2.1" / "outputs" / "v3_exports" / "v21_nodes.csv",
        ]
        self.write_canonical_csv = write_canonical_csv

        self.indicators: Dict[str, dict] = {}
        self.income_metadata: Dict[str, dict] = {}
        self.graph_index: List[Tuple[str, int, Path]] = []

        # Edge aggregates
        self.pair_obs: Dict[Tuple[str, str], Dict[str, List[EdgeObs]]] = defaultdict(lambda: defaultdict(list))
        self.pair_presence: Dict[Tuple[str, str], Set[Tuple[str, int]]] = defaultdict(set)
        self.threshold_details: Dict[Tuple[str, str], Dict[str, List[dict]]] = defaultdict(lambda: defaultdict(list))
        self.reverse_presence_cache: Dict[Tuple[str, str], int] = {}

        # Node connectivity aggregates for hub analysis
        self.node_graph_presence: Dict[str, Set[Tuple[str, int]]] = defaultdict(set)
        self.node_in_weight: Dict[str, float] = defaultdict(float)
        self.node_out_weight: Dict[str, float] = defaultdict(float)
        self.node_neighbors_in: Dict[str, Set[str]] = defaultdict(set)
        self.node_neighbors_out: Dict[str, Set[str]] = defaultdict(set)

        # Exclusion audit
        self.exclusion_reasons: Dict[str, str] = {}
        self.exclusion_edge_counts: Dict[str, int] = defaultdict(int)

        # Baseline cache for threshold country splits.
        self._baseline_year_cache: Dict[int, Dict[str, Dict[str, object]]] = {}

        self.total_graphs_seen = 0

    def load_metadata(self) -> None:
        data = read_json(self.metadata_path)
        self.indicators = data.get("indicators", {})
        if not self.indicators:
            raise RuntimeError(f"No indicators found in {self.metadata_path}")
        if self.income_path.exists():
            self.income_metadata = read_json(self.income_path)

        # Precompute exclusion reasons once per indicator.
        for code, meta in self.indicators.items():
            reason = interpretability_reason(
                code=code,
                label=str(meta.get("label", code)),
                node_type=str(meta.get("node_type", "")),
                layer=as_int(meta.get("layer")),
            )
            if reason:
                self.exclusion_reasons[code] = reason

    def indicator_label(self, code: str) -> str:
        meta = self.indicators.get(code, {})
        return str(meta.get("label", code))

    def indicator_domain(self, code: str) -> str:
        meta = self.indicators.get(code, {})
        return str(meta.get("domain", "unknown"))

    def indicator_layer(self, code: str) -> Optional[int]:
        return as_int(self.indicators.get(code, {}).get("layer"))

    def is_interpretable(self, code: str) -> bool:
        return code in self.indicators and code not in self.exclusion_reasons

    def build_graph_index(self) -> None:
        idx: List[Tuple[str, int, Path]] = []
        for stratum, folder in self.graph_paths.items():
            files = sorted(folder.glob("*_graph.json"))
            for path in files:
                year = as_int(path.name.split("_")[0])
                if year is None:
                    continue
                idx.append((stratum, year, path))
        self.graph_index = sorted(idx, key=lambda x: (x[0], x[1]))

        by_stratum: Dict[str, List[int]] = defaultdict(list)
        for stratum, year, _ in self.graph_index:
            by_stratum[stratum].append(year)
        expected_years = set(range(1990, 2025))
        for stratum in STRATA:
            years = set(by_stratum.get(stratum, []))
            if years != expected_years:
                missing = sorted(expected_years - years)
                extras = sorted(years - expected_years)
                raise RuntimeError(
                    f"Stratum {stratum} year coverage mismatch. "
                    f"missing={missing[:5]}{'...' if len(missing) > 5 else ''} "
                    f"extras={extras[:5]}{'...' if len(extras) > 5 else ''}"
                )
        if len(self.graph_index) != FULL_GRAPH_COUNT:
            raise RuntimeError(
                f"Graph coverage mismatch: found {len(self.graph_index)} expected {FULL_GRAPH_COUNT}"
            )

    def iter_graphs(self) -> Iterable[Tuple[str, int, dict]]:
        for stratum, year, path in self.graph_index:
            yield stratum, year, read_json(path)

    def parse(self, canonical_csv_path: Optional[Path] = None) -> None:
        self.load_metadata()
        self.build_graph_index()

        csv_writer = None
        csv_file_handle = None
        if self.write_canonical_csv and canonical_csv_path is not None:
            canonical_csv_path.parent.mkdir(parents=True, exist_ok=True)
            csv_file_handle = gzip.open(canonical_csv_path, "wt", encoding="utf-8", newline="")
            csv_writer = csv.DictWriter(
                csv_file_handle,
                fieldnames=[
                    "version",
                    "stratum",
                    "year",
                    "source",
                    "target",
                    "lag",
                    "relationship_type",
                    "beta",
                    "ci_lower",
                    "ci_upper",
                    "p_value",
                    "r_squared",
                    "n_samples",
                    "nonlinearity_type",
                    "nonlinearity_params_json",
                    "nonlinearity_marginal_effects_json",
                    "edge_active",
                ],
            )
            csv_writer.writeheader()

        try:
            for stratum, year, graph in self.iter_graphs():
                self.total_graphs_seen += 1
                edges = graph.get("edges", [])

                # Keep one strongest edge per (source,target) per graph for pair-level stats.
                strongest_by_pair: Dict[Tuple[str, str], dict] = {}
                for edge in edges:
                    source = str(edge.get("source", "")).strip()
                    target = str(edge.get("target", "")).strip()
                    if not source or not target:
                        continue

                    current = strongest_by_pair.get((source, target))
                    if current is None:
                        strongest_by_pair[(source, target)] = edge
                    else:
                        if abs(as_float(edge.get("beta")) or 0.0) > abs(as_float(current.get("beta")) or 0.0):
                            strongest_by_pair[(source, target)] = edge

                    if csv_writer is not None:
                        nonlin = edge.get("nonlinearity") or {}
                        csv_writer.writerow(
                            {
                                "version": "v31_current",
                                "stratum": stratum,
                                "year": year,
                                "source": source,
                                "target": target,
                                "lag": as_int(edge.get("lag")),
                                "relationship_type": edge.get("relationship_type", "unknown"),
                                "beta": as_float(edge.get("beta")),
                                "ci_lower": as_float(edge.get("ci_lower")),
                                "ci_upper": as_float(edge.get("ci_upper")),
                                "p_value": as_float(edge.get("p_value")),
                                "r_squared": as_float(edge.get("r_squared")),
                                "n_samples": as_int(edge.get("n_samples")),
                                "nonlinearity_type": nonlin.get("type", "linear"),
                                "nonlinearity_params_json": json.dumps(nonlin.get("params") or {}, ensure_ascii=True),
                                "nonlinearity_marginal_effects_json": json.dumps(
                                    nonlin.get("marginal_effects") or {}, ensure_ascii=True
                                ),
                                "edge_active": True,
                            }
                        )

                for (source, target), edge in strongest_by_pair.items():
                    nonlin = edge.get("nonlinearity") or {}
                    relationship_type = str(edge.get("relationship_type", "unknown"))
                    nonlin_type = str(nonlin.get("type", relationship_type if relationship_type else "unknown"))

                    obs = EdgeObs(
                        source=source,
                        target=target,
                        stratum=stratum,
                        year=year,
                        beta=as_float(edge.get("beta")) or 0.0,
                        ci_lower=as_float(edge.get("ci_lower")),
                        ci_upper=as_float(edge.get("ci_upper")),
                        p_value=as_float(edge.get("p_value")),
                        lag=as_int(edge.get("lag")),
                        r_squared=as_float(edge.get("r_squared")),
                        n_samples=as_int(edge.get("n_samples")),
                        relationship_type=relationship_type or "unknown",
                        nonlinearity_type=nonlin_type or "unknown",
                        nonlinearity_params=nonlin.get("params") or {},
                    )
                    pair = (source, target)
                    self.pair_obs[pair][stratum].append(obs)
                    self.pair_presence[pair].add((stratum, year))

                    self.node_graph_presence[source].add((stratum, year))
                    self.node_graph_presence[target].add((stratum, year))
                    self.node_out_weight[source] += abs(obs.beta)
                    self.node_in_weight[target] += abs(obs.beta)
                    self.node_neighbors_out[source].add(target)
                    self.node_neighbors_in[target].add(source)

                    if source in self.exclusion_reasons:
                        self.exclusion_edge_counts[source] += 1
                    if target in self.exclusion_reasons:
                        self.exclusion_edge_counts[target] += 1

                    is_threshold = (
                        obs.relationship_type == "threshold" or obs.nonlinearity_type == "threshold"
                    )
                    if is_threshold:
                        self.threshold_details[pair][stratum].append(
                            {
                                "year": year,
                                "beta": obs.beta,
                                "threshold": as_float(obs.nonlinearity_params.get("threshold")),
                                "beta_low": as_float(obs.nonlinearity_params.get("beta_low")),
                                "beta_high": as_float(obs.nonlinearity_params.get("beta_high")),
                                "lag": obs.lag,
                                "relationship_type": obs.relationship_type,
                                "nonlinearity_type": obs.nonlinearity_type,
                            }
                        )
        finally:
            if csv_file_handle is not None:
                csv_file_handle.close()

    def pair_graph_count(self, pair: Tuple[str, str]) -> int:
        return len(self.pair_presence.get(pair, set()))

    def pair_year_count(self, pair: Tuple[str, str], stratum: str) -> int:
        years = {(s, y) for (s, y) in self.pair_presence.get(pair, set()) if s == stratum}
        return len(years)

    def reverse_graph_count(self, pair: Tuple[str, str]) -> int:
        rev = (pair[1], pair[0])
        if rev in self.reverse_presence_cache:
            return self.reverse_presence_cache[rev]
        count = self.pair_graph_count(rev)
        self.reverse_presence_cache[rev] = count
        return count

    def country_classification(self, country: str, year: int = 2024) -> str:
        countries = self.income_metadata.get("countries", {})
        row = countries.get(country)
        if not isinstance(row, dict):
            return "Unknown"
        by_year = row.get("by_year", {})
        yrow = by_year.get(str(year))
        if isinstance(yrow, dict):
            value = yrow.get("classification_3tier", "Unknown")
            if value in (None, "", "None"):
                return "Unknown"
            return str(value)
        value = row.get("current_classification_3tier", "Unknown")
        if value in (None, "", "None"):
            return "Unknown"
        return str(value)

    def baseline_values_for_year(self, year: int = 2024) -> Dict[str, Dict[str, object]]:
        if year in self._baseline_year_cache:
            return self._baseline_year_cache[year]

        values_by_country: Dict[str, Dict[str, object]] = {}
        if not self.baselines_root.exists():
            self._baseline_year_cache[year] = values_by_country
            return values_by_country

        for country_dir in sorted(self.baselines_root.iterdir()):
            if not country_dir.is_dir():
                continue
            year_file = country_dir / f"{year}.json"
            if not year_file.exists():
                continue
            try:
                payload = read_json(year_file)
            except Exception:
                continue
            values = payload.get("values")
            if isinstance(values, dict):
                values_by_country[country_dir.name] = values

        self._baseline_year_cache[year] = values_by_country
        return values_by_country


# -----------------------------------------------------------------------------
# v2/v2.1 lineage mapping
# -----------------------------------------------------------------------------


class LineageMapper:
    def __init__(self, corpus: Corpus):
        self.corpus = corpus
        self.v21_edges: Set[Tuple[str, str]] = set()
        self.v21_nodes: Set[str] = set()
        self.v21_label_to_ids: Dict[str, Set[str]] = defaultdict(set)
        self.current_label_to_code: Dict[str, str] = {}

    def load(self) -> None:
        # Load v2.1 nodes
        for path in self.corpus.v21_nodes_paths:
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    node_id = str(row.get("id", "")).strip()
                    label = str(row.get("label", "")).strip()
                    if not node_id:
                        continue
                    self.v21_nodes.add(node_id)
                    self.v21_label_to_ids[normalize_text(label)].add(node_id)

        # Load v2.1 edges
        for path in self.corpus.v21_edges_paths:
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    source = str(row.get("source", "")).strip()
                    target = str(row.get("target", "")).strip()
                    if source and target:
                        self.v21_edges.add((source, target))

        for code, meta in self.corpus.indicators.items():
            self.current_label_to_code[normalize_text(str(meta.get("label", code)))] = code

    def map_code(self, code: str) -> Tuple[Set[str], str]:
        """
        Returns (candidate_v21_ids, method).
        method in: exact_code, label_exact, unresolved.
        """
        if code in self.v21_nodes:
            return {code}, "exact_code"

        label = normalize_text(self.corpus.indicator_label(code))
        ids = self.v21_label_to_ids.get(label, set())
        if len(ids) == 1:
            return set(ids), "label_exact"
        return set(), "unresolved"

    def edge_status(self, source: str, target: str) -> Tuple[str, str]:
        src_ids, src_method = self.map_code(source)
        tgt_ids, tgt_method = self.map_code(target)

        # Exact same edge present
        if source in self.v21_nodes and target in self.v21_nodes and (source, target) in self.v21_edges:
            return "confirmed_same_edge", "Exact source/target codes found in v2.1 edge set."

        if src_ids and tgt_ids:
            for s in src_ids:
                for t in tgt_ids:
                    if (s, t) in self.v21_edges:
                        if src_method == "exact_code" and tgt_method == "exact_code":
                            return "confirmed_same_edge", "Exact source/target codes found in v2.1 edge set."
                        return (
                            "code_renamed_semantically_same",
                            "Edge found via deterministic label mapping from current codes to v2.1 node IDs.",
                        )
            return (
                "structurally_changed",
                "Both endpoints mapped to v2.1, but directed edge absent in v2.1 edge exports.",
            )

        return (
            "not_resolved",
            "Unable to deterministically map one or both endpoints to v2.1 nodes.",
        )

    def finding_lineage(self, finding: dict) -> Dict[str, object]:
        edge_refs: List[Tuple[str, str]] = []

        source = finding["variables"]["source"]["code"]
        target = finding["variables"]["target"]["code"]
        edge_refs.append((source, target))

        mediator = finding["variables"].get("mediator")
        if mediator and mediator.get("code"):
            m = mediator["code"]
            edge_refs = [(source, m), (m, target)]

        statuses = []
        notes = []
        for s, t in edge_refs:
            status, note = self.edge_status(s, t)
            statuses.append(status)
            notes.append(f"{s}->{t}: {note}")

        if statuses and all(x == "confirmed_same_edge" for x in statuses):
            overall = "confirmed_same_edge"
        elif any(x == "not_resolved" for x in statuses):
            overall = "not_resolved"
        elif any(x == "structurally_changed" for x in statuses):
            overall = "structurally_changed"
        elif any(x == "code_renamed_semantically_same" for x in statuses):
            overall = "code_renamed_semantically_same"
        else:
            overall = "not_resolved"

        return {
            "v2_v21_status": overall,
            "notes": " | ".join(notes),
            "edge_statuses": [
                {"source": s, "target": t, "status": st}
                for (s, t), st in zip(edge_refs, statuses)
            ],
        }


# -----------------------------------------------------------------------------
# Feature extraction for findings classes
# -----------------------------------------------------------------------------


def pair_stratum_stats(corpus: Corpus, pair: Tuple[str, str]) -> Dict[str, dict]:
    out = {}
    for stratum in STRATA:
        obs = corpus.pair_obs.get(pair, {}).get(stratum, [])
        if not obs:
            out[stratum] = {
                "years_active": 0,
                "beta": None,
                "ci_lower": None,
                "ci_upper": None,
                "lag_mode": None,
                "edge_type": None,
                "nonlinearity_type": None,
                "pos_years": 0,
                "neg_years": 0,
            }
            continue

        betas = [o.beta for o in obs]
        lags = [str(o.lag) for o in obs if o.lag is not None]
        out[stratum] = {
            "years_active": len(obs),
            "beta": mean(betas),
            "ci_lower": mean(o.ci_lower for o in obs),
            "ci_upper": mean(o.ci_upper for o in obs),
            "lag_mode": mode(lags, default=None),
            "edge_type": mode((o.relationship_type for o in obs), default="unknown"),
            "nonlinearity_type": mode((o.nonlinearity_type for o in obs), default="unknown"),
            "pos_years": sum(1 for b in betas if b > 0),
            "neg_years": sum(1 for b in betas if b < 0),
        }
    return out


def pair_temporal_profile(corpus: Corpus, pair: Tuple[str, str]) -> Dict[str, dict]:
    profile = {label: {"count": 0, "beta_mean": None, "sign": "none"} for _, _, label in DECADE_BINS}
    obs = []
    for stratum in STRATA:
        obs.extend(corpus.pair_obs.get(pair, {}).get(stratum, []))
    for _, _, label in DECADE_BINS:
        vals = [o.beta for o in obs if decade_label(o.year) == label]
        if not vals:
            continue
        b = mean(vals)
        profile[label] = {
            "count": len(vals),
            "beta_mean": b,
            "sign": "positive" if (b or 0) > 0 else "negative" if (b or 0) < 0 else "zero",
        }
    return profile


def compute_mediation_candidates(corpus: Corpus) -> List[dict]:
    # High-coverage, interpretable directed edges only.
    path_edges = [
        pair
        for pair, present in corpus.pair_presence.items()
        if len(present) >= 120
        and corpus.is_interpretable(pair[0])
        and corpus.is_interpretable(pair[1])
    ]

    adjacency: Dict[str, Set[str]] = defaultdict(set)
    for s, t in path_edges:
        adjacency[s].add(t)

    candidates = []
    for source, mediators in adjacency.items():
        for mediator in mediators:
            targets = adjacency.get(mediator, set())
            for target in targets:
                if source == target or source == mediator or mediator == target:
                    continue

                pair_ab = (source, mediator)
                pair_bc = (mediator, target)
                pair_ac = (source, target)

                presence_ab = corpus.pair_presence.get(pair_ab, set())
                presence_bc = corpus.pair_presence.get(pair_bc, set())
                indirect_presence = presence_ab & presence_bc
                indirect_graphs = len(indirect_presence)
                if indirect_graphs < 120:
                    continue

                direct_graphs = corpus.pair_graph_count(pair_ac)
                if direct_graphs > 14:
                    continue

                stats_ab = pair_stratum_stats(corpus, pair_ab)
                stats_bc = pair_stratum_stats(corpus, pair_bc)
                stats_ac = pair_stratum_stats(corpus, pair_ac)

                indirect_by_stratum = {
                    s: len({x for x in indirect_presence if x[0] == s}) for s in STRATA
                }
                years_active_min = min(indirect_by_stratum.values()) if indirect_by_stratum else 0

                stratum_indirect = {}
                for stratum in STRATA:
                    b1 = stats_ab[stratum]["beta"]
                    b2 = stats_bc[stratum]["beta"]
                    stratum_indirect[stratum] = b1 * b2 if b1 is not None and b2 is not None else None

                target_label = corpus.indicator_label(target)
                outcome_concept = classify_outcome_concept(target, target_label)
                outcome_priority = 1.0 if outcome_concept is not None else 0.0
                ci_points = 0
                ci_possible = 0
                for stratum in STRATA:
                    for row in (stats_ab[stratum], stats_bc[stratum]):
                        ci_possible += 1
                        if row.get("ci_lower") is not None and row.get("ci_upper") is not None:
                            ci_points += 1
                ci_coverage = (ci_points / ci_possible) if ci_possible else 0.0
                confidence = "high" if indirect_graphs >= 135 and direct_graphs == 0 else "medium"

                caveats = [
                    "Mediation candidate is based on directed path persistence, not path-level experimental identification.",
                ]
                if direct_graphs > 0:
                    caveats.append(
                        f"Direct edge {source}->{target} is present in {direct_graphs}/140 graphs, so mediation is partial."
                    )

                candidates.append(
                    {
                        "class": "mediation",
                        "title": (
                            f"{corpus.indicator_label(source)} influences "
                            f"{corpus.indicator_label(target)} via {corpus.indicator_label(mediator)}"
                        ),
                        "variables": {
                            "source": {"code": source, "label": corpus.indicator_label(source)},
                            "mediator": {"code": mediator, "label": corpus.indicator_label(mediator)},
                            "target": {"code": target, "label": target_label},
                        },
                        "edge_type": "mixed",
                        "availability": {
                            "years_active": f"{years_active_min}/35",
                            "graphs_active": f"{indirect_graphs}/140",
                        },
                        "direct_edge_availability": f"{direct_graphs}/140",
                        "indirect_path_availability": f"{indirect_graphs}/140",
                        "indirect_path_years_by_stratum": indirect_by_stratum,
                        "stratum_betas": {
                            stratum: {
                                "beta_ab": stats_ab[stratum]["beta"],
                                "beta_bc": stats_bc[stratum]["beta"],
                                "indirect_beta_product": stratum_indirect[stratum],
                                "ci_lower_ab": stats_ab[stratum]["ci_lower"],
                                "ci_upper_ab": stats_ab[stratum]["ci_upper"],
                                "ci_lower_bc": stats_bc[stratum]["ci_lower"],
                                "ci_upper_bc": stats_bc[stratum]["ci_upper"],
                                "direct_beta_ac": stats_ac[stratum]["beta"],
                            }
                            for stratum in STRATA
                        },
                        "temporal_profile": {
                            "1990s": "active",
                            "2000s": "active",
                            "2010s": "active",
                            "2020s": "active",
                        },
                        "directionality": {
                            "reversal": False,
                            "reverse_edge_presence": (
                                f"{corpus.reverse_graph_count(pair_ab) + corpus.reverse_graph_count(pair_bc)}/280"
                            ),
                        },
                        "nonlinearity": {
                            "threshold": None,
                            "beta_low": None,
                            "beta_high": None,
                            "flip_years": 0,
                        },
                        "caveats": caveats,
                        "outcome_priority": {
                            "is_outcome_target": outcome_concept is not None,
                            "outcome_concept": outcome_concept,
                        },
                        "plain_language": (
                            f"Changes in {corpus.indicator_label(source)} are linked to "
                            f"{corpus.indicator_label(target)} through {corpus.indicator_label(mediator)}, "
                            "with most of the effect carried by the indirect path."
                        ),
                        "academic_summary": (
                            f"Directed mediation path {source}->{mediator}->{target} is active in {indirect_graphs}/140 graphs; "
                            f"direct edge {source}->{target} appears in {direct_graphs}/140 graphs."
                        ),
                        "confidence": confidence,
                        "_score_inputs": {
                            "graphs_active": indirect_graphs,
                            "years_active": years_active_min,
                            "beta_magnitude": mean(abs(v) for v in stratum_indirect.values() if v is not None) or 0.0,
                            "ci_coverage": ci_coverage,
                            "reversal_strength": 0.0,
                            "class": "mediation",
                            "decade_consistency": years_active_min / YEARS_EXPECTED if YEARS_EXPECTED else 0.0,
                            "outcome_priority": outcome_priority,
                            "direct_edge_graphs": direct_graphs,
                            "indirect_graphs": indirect_graphs,
                        },
                    }
                )

    # Deduplicate by semantic triple signature.
    dedup = {}
    for candidate in candidates:
        s = candidate["variables"]["source"]["code"]
        m = candidate["variables"]["mediator"]["code"]
        t = candidate["variables"]["target"]["code"]
        key = (s, m, t)
        # Keep candidate with strongest coverage then largest indirect magnitude.
        current = dedup.get(key)
        this_cov = candidate["_score_inputs"]["indirect_graphs"]
        this_mag = candidate["_score_inputs"]["beta_magnitude"]
        if current is None:
            dedup[key] = candidate
            continue
        cur_cov = current["_score_inputs"]["indirect_graphs"]
        cur_mag = current["_score_inputs"]["beta_magnitude"]
        if this_cov > cur_cov or (this_cov == cur_cov and this_mag > cur_mag):
            dedup[key] = candidate

    return list(dedup.values())


def compute_sign_reversal_candidates(corpus: Corpus) -> List[dict]:
    candidates = []

    for pair in corpus.pair_presence.keys():
        source, target = pair
        if not (corpus.is_interpretable(source) and corpus.is_interpretable(target)):
            continue

        stats = pair_stratum_stats(corpus, pair)
        if any(stats[s]["years_active"] == 0 for s in STRATA):
            continue

        means = [stats[s]["beta"] for s in STRATA if stats[s]["beta"] is not None]
        if not means:
            continue
        if not (min(means) < 0 < max(means)):
            continue

        # Decade split per stratum
        decade_split = {}
        for stratum in STRATA:
            bucket_vals = defaultdict(list)
            for obs in corpus.pair_obs.get(pair, {}).get(stratum, []):
                bucket_vals[decade_label(obs.year)].append(obs.beta)
            decade_split[stratum] = {
                dlabel: {
                    "mean": mean(vals),
                    "pos": sum(1 for x in vals if x > 0),
                    "neg": sum(1 for x in vals if x < 0),
                    "count": len(vals),
                }
                for _, _, dlabel in DECADE_BINS
                for vals in [bucket_vals.get(dlabel, [])]
            }

        beta_spread = max(means) - min(means)
        reversal_strength = abs(max(means)) + abs(min(means))

        edge_type = mode(stats[s]["edge_type"] for s in STRATA if stats[s]["edge_type"])
        nonlin_type = mode(stats[s]["nonlinearity_type"] for s in STRATA if stats[s]["nonlinearity_type"])

        candidates.append(
            {
                "class": "reversal",
                "title": (
                    f"{corpus.indicator_label(source)} changes direction across development strata for "
                    f"{corpus.indicator_label(target)}"
                ),
                "variables": {
                    "source": {"code": source, "label": corpus.indicator_label(source)},
                    "mediator": None,
                    "target": {"code": target, "label": corpus.indicator_label(target)},
                },
                "edge_type": edge_type or nonlin_type or "mixed",
                "availability": {
                    "years_active": f"{min(stats[s]['years_active'] for s in STRATA)}/35",
                    "graphs_active": f"{corpus.pair_graph_count(pair)}/140",
                },
                "stratum_betas": {
                    s: {
                        "beta": stats[s]["beta"],
                        "ci_lower": stats[s]["ci_lower"],
                        "ci_upper": stats[s]["ci_upper"],
                        "years_active": stats[s]["years_active"],
                        "pos_years": stats[s]["pos_years"],
                        "neg_years": stats[s]["neg_years"],
                    }
                    for s in STRATA
                },
                "temporal_profile": decade_split,
                "directionality": {
                    "reversal": True,
                    "reverse_edge_presence": f"{corpus.reverse_graph_count(pair)}/140",
                    "beta_spread": beta_spread,
                },
                "nonlinearity": {
                    "threshold": None,
                    "beta_low": None,
                    "beta_high": None,
                    "flip_years": 0,
                },
                "caveats": [
                    "Sign reversal is based on mean yearly beta by stratum; some decades may still show mixed signs.",
                ],
                "plain_language": (
                    f"{corpus.indicator_label(source)} is associated with opposite directional effects on "
                    f"{corpus.indicator_label(target)} depending on development stage."
                ),
                "academic_summary": (
                    f"Edge {source}->{target} exhibits cross-strata sign heterogeneity with "
                    f"means { {s: stats[s]['beta'] for s in STRATA} }."
                ),
                "confidence": "medium",
                "_score_inputs": {
                    "graphs_active": corpus.pair_graph_count(pair),
                    "years_active": min(stats[s]["years_active"] for s in STRATA),
                    "beta_magnitude": reversal_strength,
                    "ci_coverage": sum(1 for s in STRATA if stats[s]["ci_lower"] is not None and stats[s]["ci_upper"] is not None) / 4.0,
                    "reversal_strength": reversal_strength,
                    "class": "reversal",
                    "decade_consistency": _decade_consistency_from_split(decade_split),
                },
            }
        )

    return candidates


def _decade_consistency_from_split(decade_split: Dict[str, dict]) -> float:
    # Measures fraction of decade-stratum bins where sign is unambiguous.
    total = 0
    consistent = 0
    for stratum, decades in decade_split.items():
        for dlabel in ("1990s", "2000s", "2010s", "2020s"):
            info = decades.get(dlabel, {})
            count = info.get("count", 0)
            if not count:
                continue
            total += 1
            pos = info.get("pos", 0)
            neg = info.get("neg", 0)
            if pos == 0 or neg == 0:
                consistent += 1
    if total == 0:
        return 0.0
    return consistent / total


def compute_threshold_candidates(corpus: Corpus) -> List[dict]:
    candidates = []

    for pair, per_stratum in corpus.threshold_details.items():
        source, target = pair
        if not (corpus.is_interpretable(source) and corpus.is_interpretable(target)):
            continue

        threshold_year_counts = {s: len(per_stratum.get(s, [])) for s in STRATA}
        primary_stratum = max(STRATA, key=lambda s: threshold_year_counts[s])
        primary_count = threshold_year_counts[primary_stratum]

        if primary_count < 25:
            continue

        def stratum_threshold_summary(stratum: str) -> dict:
            rows = per_stratum.get(stratum, [])
            if not rows:
                return {
                    "years": 0,
                    "flip_years": 0,
                    "beta": None,
                    "threshold": None,
                    "beta_low": None,
                    "beta_high": None,
                    "first": None,
                    "last": None,
                }
            flips = sum(
                1
                for r in rows
                if r.get("beta_low") is not None
                and r.get("beta_high") is not None
                and (r["beta_low"] * r["beta_high"] < 0)
            )
            return {
                "years": len(rows),
                "flip_years": flips,
                "beta": mean(r.get("beta") for r in rows),
                "threshold": mean(r.get("threshold") for r in rows if r.get("threshold") is not None),
                "beta_low": mean(r.get("beta_low") for r in rows if r.get("beta_low") is not None),
                "beta_high": mean(r.get("beta_high") for r in rows if r.get("beta_high") is not None),
                "first": rows[0],
                "last": rows[-1],
            }

        summary = {s: stratum_threshold_summary(s) for s in STRATA}
        threshold_details_by_stratum = {
            s: {
                "years_threshold_active": summary[s]["years"],
                "threshold": summary[s]["threshold"],
                "beta_low": summary[s]["beta_low"],
                "beta_high": summary[s]["beta_high"],
                "flip_years": summary[s]["flip_years"],
            }
            for s in STRATA
        }

        # Detect recent linear fallback in primary stratum.
        recent_years = {2020, 2021, 2022, 2023, 2024}
        threshold_recent = {
            r["year"] for r in per_stratum.get(primary_stratum, []) if r.get("year") in recent_years
        }
        reverted_recent = len(threshold_recent) < len(recent_years)
        policy_relevant = is_policy_relevant_indicator(
            source,
            corpus.indicator_label(source),
            corpus.indicator_domain(source),
        )

        candidates.append(
            {
                "class": "threshold",
                "title": (
                    f"{corpus.indicator_label(source)} has robust threshold dynamics for "
                    f"{corpus.indicator_label(target)}"
                ),
                "variables": {
                    "source": {"code": source, "label": corpus.indicator_label(source)},
                    "mediator": None,
                    "target": {"code": target, "label": corpus.indicator_label(target)},
                },
                "edge_type": "threshold",
                "availability": {
                    "years_active": f"{primary_count}/35",
                    "graphs_active": f"{corpus.pair_graph_count(pair)}/140",
                },
                "stratum_betas": {
                    s: {
                        "beta": summary[s]["beta"],
                        "ci_lower": None,
                        "ci_upper": None,
                        "years_active": summary[s]["years"],
                    }
                    for s in STRATA
                },
                "temporal_profile": {
                    "1990s": "active" if any((r.get("year") or 0) < 2000 for r in per_stratum.get(primary_stratum, [])) else "inactive",
                    "2000s": "active" if any(2000 <= (r.get("year") or 0) < 2010 for r in per_stratum.get(primary_stratum, [])) else "inactive",
                    "2010s": "active" if any(2010 <= (r.get("year") or 0) < 2020 for r in per_stratum.get(primary_stratum, [])) else "inactive",
                    "2020s": "active" if any((r.get("year") or 0) >= 2020 for r in per_stratum.get(primary_stratum, [])) else "inactive",
                },
                "directionality": {
                    "reversal": False,
                    "reverse_edge_presence": f"{corpus.reverse_graph_count(pair)}/140",
                },
                "nonlinearity": {
                    "threshold": summary[primary_stratum]["threshold"],
                    "threshold_latest_year": (
                        summary[primary_stratum]["last"]["year"] if summary[primary_stratum]["last"] else None
                    ),
                    "threshold_latest_year_value": (
                        summary[primary_stratum]["last"]["threshold"]
                        if summary[primary_stratum]["last"] is not None
                        else None
                    ),
                    "beta_low": summary[primary_stratum]["beta_low"],
                    "beta_high": summary[primary_stratum]["beta_high"],
                    "flip_years": summary[primary_stratum]["flip_years"],
                    "primary_stratum": primary_stratum,
                    "threshold_years_by_stratum": threshold_year_counts,
                    "threshold_details_by_stratum": threshold_details_by_stratum,
                    "threshold_variable": source,
                    "reverted_recently": reverted_recent,
                },
                "caveats": [
                    "Threshold parameters are edge-level and may vary year-to-year.",
                ],
                "policy_relevance": {
                    "is_policy_relevant_lever": policy_relevant,
                    "lever_variable": {"code": source, "label": corpus.indicator_label(source)},
                },
                "plain_language": (
                    f"The effect of {corpus.indicator_label(source)} on {corpus.indicator_label(target)} "
                    f"changes by regime around a learned threshold in {primary_stratum}."
                ),
                "academic_summary": (
                    f"Edge {source}->{target} is classified as threshold in {primary_count}/35 years "
                    f"for {primary_stratum}; beta_low={summary[primary_stratum]['beta_low']}, "
                    f"beta_high={summary[primary_stratum]['beta_high']}."
                ),
                "confidence": "high" if primary_count >= 30 else "medium",
                "_score_inputs": {
                    "graphs_active": corpus.pair_graph_count(pair),
                    "years_active": primary_count,
                    "beta_magnitude": abs(summary[primary_stratum]["beta"] or 0.0),
                    "ci_coverage": 0.0,
                    "reversal_strength": abs((summary[primary_stratum]["beta_low"] or 0.0) - (summary[primary_stratum]["beta_high"] or 0.0)),
                    "class": "threshold",
                    "decade_consistency": primary_count / YEARS_EXPECTED,
                    "policy_relevance": 1.0 if policy_relevant else 0.0,
                },
            }
        )

    return candidates


def compute_hub_candidates(corpus: Corpus, top_n: int = 8) -> List[dict]:
    candidates = []

    for node, presence in corpus.node_graph_presence.items():
        if not corpus.is_interpretable(node):
            continue
        persistence = len(presence) / FULL_GRAPH_COUNT if FULL_GRAPH_COUNT else 0.0
        in_w = corpus.node_in_weight.get(node, 0.0)
        out_w = corpus.node_out_weight.get(node, 0.0)
        weighted_degree = (in_w + out_w) / FULL_GRAPH_COUNT
        hub_score = weighted_degree * persistence

        if hub_score <= 0:
            continue

        candidates.append(
            {
                "node": node,
                "label": corpus.indicator_label(node),
                "hub_score": hub_score,
                "persistence": persistence,
                "in_weight": in_w,
                "out_weight": out_w,
                "in_neighbors": len(corpus.node_neighbors_in.get(node, set())),
                "out_neighbors": len(corpus.node_neighbors_out.get(node, set())),
            }
        )

    candidates.sort(key=lambda x: x["hub_score"], reverse=True)
    top = candidates[:top_n]

    out = []
    for row in top:
        node = row["node"]
        # Pick strongest outgoing interpretable edge for concrete target in schema.
        pair_candidates = [
            ((s, t), obs)
            for (s, t), by_stratum in corpus.pair_obs.items()
            if s == node and corpus.is_interpretable(t)
            for obs in by_stratum.values()
        ]
        target = None
        if pair_candidates:
            best_pair = None
            best_beta = -1.0
            for (pair, obs_lists) in pair_candidates:
                mag = mean(abs(o.beta) for o in obs_lists) or 0.0
                if mag > best_beta:
                    best_beta = mag
                    best_pair = pair
            if best_pair:
                target = best_pair[1]

        if target is None:
            # fallback to self (schema requires target)
            target = node

        out.append(
            {
                "class": "hub",
                "title": f"{row['label']} acts as a high-connectivity hub",
                "variables": {
                    "source": {"code": node, "label": row["label"]},
                    "mediator": None,
                    "target": {"code": target, "label": corpus.indicator_label(target)},
                },
                "edge_type": "mixed",
                "availability": {
                    "years_active": f"{int(round(row['persistence'] * YEARS_EXPECTED))}/35",
                    "graphs_active": f"{len(corpus.node_graph_presence.get(node, set()))}/140",
                },
                "stratum_betas": {
                    s: {"beta": None, "ci_lower": None, "ci_upper": None}
                    for s in STRATA
                },
                "temporal_profile": {
                    "1990s": "active",
                    "2000s": "active",
                    "2010s": "active",
                    "2020s": "active",
                },
                "directionality": {
                    "reversal": False,
                    "reverse_edge_presence": "n/a",
                },
                "nonlinearity": {
                    "threshold": None,
                    "beta_low": None,
                    "beta_high": None,
                    "flip_years": 0,
                },
                "caveats": [
                    "Hub score uses weighted in/out degree aggregated over graphs and may still include residual proxy effects.",
                ],
                "plain_language": (
                    f"{row['label']} repeatedly appears as a central connector with strong links across the causal graph."
                ),
                "academic_summary": (
                    f"Node {node} ranks as a hub with weighted-degree persistence score {row['hub_score']:.4f}."
                ),
                "confidence": "medium",
                "_score_inputs": {
                    "graphs_active": len(corpus.node_graph_presence.get(node, set())),
                    "years_active": int(round(row["persistence"] * YEARS_EXPECTED)),
                    "beta_magnitude": row["hub_score"],
                    "ci_coverage": 0.0,
                    "reversal_strength": 0.0,
                    "class": "hub",
                    "decade_consistency": row["persistence"],
                },
                "hub_metrics": row,
            }
        )

    return out


def _match_indicator_codes(corpus: Corpus, patterns: List[str], preferred_codes: List[str]) -> List[str]:
    hits = []
    seen = set()
    for code in preferred_codes:
        if code in corpus.indicators and corpus.is_interpretable(code):
            seen.add(code)
            hits.append(code)
    rx = [re.compile(p, re.IGNORECASE) for p in patterns]
    for code, meta in corpus.indicators.items():
        if code in seen or not corpus.is_interpretable(code):
            continue
        label = str(meta.get("label", code))
        hay = f"{code} {label} {meta.get('domain', '')}"
        if any(r.search(hay) for r in rx):
            seen.add(code)
            hits.append(code)
    return hits


def compute_outcome_surprise_candidates(corpus: Corpus) -> List[dict]:
    candidates = []

    for outcome_name, cfg in OUTCOME_CONCEPTS.items():
        target_codes = _match_indicator_codes(corpus, cfg["patterns"], cfg["preferred"])
        if not target_codes:
            candidates.append(
                {
                    "class": "outcome_surprise",
                    "title": f"No clean canonical variable found for {outcome_name}",
                    "variables": {
                        "source": {"code": "not_available", "label": "not_available"},
                        "mediator": None,
                        "target": {"code": outcome_name, "label": outcome_name},
                    },
                    "edge_type": "mixed",
                    "availability": {"years_active": "0/35", "graphs_active": "0/140"},
                    "stratum_betas": {s: {"beta": None, "ci_lower": None, "ci_upper": None} for s in STRATA},
                    "temporal_profile": {
                        "1990s": "not represented",
                        "2000s": "not represented",
                        "2010s": "not represented",
                        "2020s": "not represented",
                    },
                    "directionality": {"reversal": False, "reverse_edge_presence": "0/140"},
                    "nonlinearity": {"threshold": None, "beta_low": None, "beta_high": None, "flip_years": 0},
                    "caveats": ["Outcome concept not represented cleanly by interpretable variables in current metadata."],
                    "plain_language": f"{outcome_name} is not represented cleanly enough for a robust finding.",
                    "academic_summary": f"No interpretable canonical indicator resolved for outcome concept {outcome_name}.",
                    "confidence": "low",
                    "_score_inputs": {
                        "graphs_active": 0,
                        "years_active": 0,
                        "beta_magnitude": 0.0,
                        "ci_coverage": 0.0,
                        "reversal_strength": 0.0,
                        "class": "outcome_surprise",
                        "decade_consistency": 0.0,
                    },
                    "not_represented_cleanly": True,
                }
            )
            continue

        best = None
        for target in target_codes:
            for pair in corpus.pair_presence.keys():
                if pair[1] != target:
                    continue
                source = pair[0]
                if not corpus.is_interpretable(source):
                    continue
                stats = pair_stratum_stats(corpus, pair)
                graphs_active = corpus.pair_graph_count(pair)
                years_min = min(stats[s]["years_active"] for s in STRATA)
                beta_mag = mean(abs(stats[s]["beta"] or 0.0) for s in STRATA) or 0.0
                score = graphs_active * 0.7 + years_min * 0.3 + beta_mag * 50.0
                if best is None or score > best[0]:
                    best = (score, pair, stats)

        if best is None:
            continue

        _, pair, stats = best
        source, target = pair
        graphs_active = corpus.pair_graph_count(pair)
        years_min = min(stats[s]["years_active"] for s in STRATA)
        means = [stats[s]["beta"] for s in STRATA if stats[s]["beta"] is not None]
        reversal = bool(means and min(means) < 0 < max(means))

        candidates.append(
            {
                "class": "outcome_surprise",
                "title": (
                    f"Strong upstream predictor for {outcome_name}: {corpus.indicator_label(source)} -> "
                    f"{corpus.indicator_label(target)}"
                ),
                "variables": {
                    "source": {"code": source, "label": corpus.indicator_label(source)},
                    "mediator": None,
                    "target": {"code": target, "label": corpus.indicator_label(target)},
                },
                "edge_type": mode(stats[s]["edge_type"] for s in STRATA if stats[s]["edge_type"]),
                "availability": {
                    "years_active": f"{years_min}/35",
                    "graphs_active": f"{graphs_active}/140",
                },
                "stratum_betas": {
                    s: {
                        "beta": stats[s]["beta"],
                        "ci_lower": stats[s]["ci_lower"],
                        "ci_upper": stats[s]["ci_upper"],
                        "years_active": stats[s]["years_active"],
                    }
                    for s in STRATA
                },
                "temporal_profile": pair_temporal_profile(corpus, pair),
                "directionality": {
                    "reversal": reversal,
                    "reverse_edge_presence": f"{corpus.reverse_graph_count(pair)}/140",
                },
                "nonlinearity": {
                    "threshold": None,
                    "beta_low": None,
                    "beta_high": None,
                    "flip_years": 0,
                },
                "caveats": [
                    "Outcome candidate selected by robustness and effect-size ranking among interpretable incoming edges.",
                ],
                "plain_language": (
                    f"{corpus.indicator_label(source)} is one of the strongest consistent upstream predictors of "
                    f"{corpus.indicator_label(target)} in this corpus."
                ),
                "academic_summary": (
                    f"For outcome concept {outcome_name}, edge {source}->{target} ranks highest by "
                    f"coverage/effect composite (graphs={graphs_active}/140, min_years={years_min}/35)."
                ),
                "confidence": "medium" if graphs_active >= 100 else "low",
                "_score_inputs": {
                    "graphs_active": graphs_active,
                    "years_active": years_min,
                    "beta_magnitude": mean(abs(stats[s]["beta"] or 0.0) for s in STRATA) or 0.0,
                    "ci_coverage": sum(1 for s in STRATA if stats[s]["ci_lower"] is not None and stats[s]["ci_upper"] is not None) / 4.0,
                    "reversal_strength": abs(max(means) - min(means)) if means else 0.0,
                    "class": "outcome_surprise",
                    "decade_consistency": _decade_consistency_from_split(
                        {
                            s: {
                                d: {
                                    "count": info["count"],
                                    "pos": 1 if info["sign"] == "positive" else 0,
                                    "neg": 1 if info["sign"] == "negative" else 0,
                                }
                                for d, info in pair_temporal_profile(corpus, pair).items()
                            }
                            for s in STRATA
                        }
                    ),
                },
                "outcome_concept": outcome_name,
            }
        )

    return candidates


# -----------------------------------------------------------------------------
# Ranking
# -----------------------------------------------------------------------------


def compute_scores(candidates: List[dict]) -> List[dict]:
    class_counts = Counter(c.get("class", "unknown") for c in candidates)
    if class_counts:
        min_class_count = min(class_counts.values())
        max_class_count = max(class_counts.values())
    else:
        min_class_count = 0
        max_class_count = 0

    def class_diversity_bonus(finding_class: str) -> float:
        count = class_counts.get(finding_class, 0)
        if max_class_count == min_class_count:
            return 0.5
        return clamp((max_class_count - count) / (max_class_count - min_class_count))

    scored = []
    for c in candidates:
        inp = c.get("_score_inputs", {})

        graphs_active = float(inp.get("graphs_active", 0))
        years_active = float(inp.get("years_active", 0))
        beta_mag = float(inp.get("beta_magnitude", 0.0))
        ci_cov = float(inp.get("ci_coverage", 0.0))
        reversal_strength = float(inp.get("reversal_strength", 0.0))
        decade_consistency = float(inp.get("decade_consistency", 0.0))
        finding_class = str(inp.get("class", c.get("class", "outcome_surprise")))
        diversity = class_diversity_bonus(finding_class)

        robustness = clamp(graphs_active / FULL_GRAPH_COUNT)

        labels = [
            c["variables"]["source"]["label"],
            c["variables"]["target"]["label"],
        ]
        mediator = c["variables"].get("mediator")
        hop_penalty = 0.15 if mediator else 0.0
        avg_words = mean(len(str(lbl).split()) for lbl in labels if lbl) or 8.0
        clarity = clamp(1.0 - min(avg_words / 14.0, 0.55) - hop_penalty)

        ci_tightness = 1.0 - clamp(reversal_strength / 1.5)
        academic = clamp(
            0.40 * clamp(beta_mag / 1.0)
            + 0.35 * ci_cov
            + 0.15 * decade_consistency
            + 0.10 * ci_tightness
        )

        total_score = 0.30 * robustness + 0.20 * clarity + 0.25 * academic + 0.25 * diversity

        c = dict(c)
        c["scores"] = {
            "robustness": robustness,
            "public_clarity": clarity,
            "academic_weight": academic,
            "class_diversity_bonus": diversity,
            "total": total_score,
        }
        scored.append(c)

    scored.sort(
        key=lambda x: (
            x["scores"]["total"],
            x["scores"]["robustness"],
            x["scores"]["class_diversity_bonus"],
            x["scores"]["academic_weight"],
            stable_hash(
                [
                    x["class"],
                    x["variables"]["source"]["code"],
                    x["variables"]["target"]["code"],
                    str(x["variables"].get("mediator", {})),
                ]
            ),
        ),
        reverse=True,
    )
    return scored


def _finding_theme_tokens(corpus: Corpus, finding: dict) -> Tuple[str, str, str, str]:
    source_code = finding["variables"]["source"]["code"]
    target_code = finding["variables"]["target"]["code"]
    source_domain = corpus.indicator_domain(source_code)
    target_domain = corpus.indicator_domain(target_code)
    source_prefix = source_code.split(".")[0].split("_")[0]
    target_prefix = target_code.split(".")[0].split("_")[0]
    return source_domain, target_domain, source_prefix, target_prefix


def select_public_top_findings(top10: List[dict], corpus: Corpus, n: int = 4) -> List[dict]:
    """
    Deterministically select a non-overlapping public subset from top10.
    Priority:
    1) maximize class diversity
    2) avoid duplicate source/target variables
    3) avoid duplicate domain/prefix theme signatures
    """

    selected: List[dict] = []
    selected_ids: Set[int] = set()
    used_classes: Set[str] = set()
    used_sources: Set[str] = set()
    used_targets: Set[str] = set()
    used_domain_pairs: Set[Tuple[str, str]] = set()
    used_prefix_pairs: Set[Tuple[str, str]] = set()

    def _pick(f: dict) -> None:
        selected.append(f)
        selected_ids.add(id(f))
        used_classes.add(f.get("class", "unknown"))
        s = f["variables"]["source"]["code"]
        t = f["variables"]["target"]["code"]
        used_sources.add(s)
        used_targets.add(t)
        source_domain, target_domain, source_prefix, target_prefix = _finding_theme_tokens(corpus, f)
        used_domain_pairs.add((source_domain, target_domain))
        used_prefix_pairs.add((source_prefix, target_prefix))

    # Pass 1: maximize class diversity with unique source/target codes.
    for f in top10:
        if len(selected) >= n:
            break
        fclass = f.get("class", "unknown")
        s = f["variables"]["source"]["code"]
        t = f["variables"]["target"]["code"]
        if fclass in used_classes:
            continue
        if s in used_sources or t in used_targets:
            continue
        _pick(f)

    # Pass 2: diversify themes (domain and prefix pair), still keeping unique source/target.
    for f in top10:
        if len(selected) >= n:
            break
        if id(f) in selected_ids:
            continue
        s = f["variables"]["source"]["code"]
        t = f["variables"]["target"]["code"]
        if s in used_sources or t in used_targets:
            continue
        source_domain, target_domain, source_prefix, target_prefix = _finding_theme_tokens(corpus, f)
        if (source_domain, target_domain) in used_domain_pairs:
            continue
        if (source_prefix, target_prefix) in used_prefix_pairs:
            continue
        _pick(f)

    # Pass 3: enforce only unique source/target codes.
    for f in top10:
        if len(selected) >= n:
            break
        if id(f) in selected_ids:
            continue
        s = f["variables"]["source"]["code"]
        t = f["variables"]["target"]["code"]
        if s in used_sources or t in used_targets:
            continue
        _pick(f)

    # Pass 4: fill remaining slots by rank order.
    for f in top10:
        if len(selected) >= n:
            break
        if id(f) in selected_ids:
            continue
        _pick(f)

    return selected[:n]


def finding_identity(finding: dict) -> Tuple[str, str, str, str]:
    source = finding["variables"]["source"]["code"]
    target = finding["variables"]["target"]["code"]
    mediator = ""
    if finding["variables"].get("mediator"):
        mediator = finding["variables"]["mediator"]["code"]
    return (finding.get("class", "unknown"), source, mediator, target)


def _pick_if_present(
    selected: List[dict],
    selected_keys: Set[Tuple[str, str, str, str]],
    candidate: Optional[dict],
) -> bool:
    if candidate is None:
        return False
    key = finding_identity(candidate)
    if key in selected_keys:
        return False
    selected.append(candidate)
    selected_keys.add(key)
    return True


def select_diverse_top10(ranked: List[dict]) -> Tuple[List[dict], List[str]]:
    warnings = []
    selected: List[dict] = []
    selected_keys: Set[Tuple[str, str, str, str]] = set()

    by_class: Dict[str, List[dict]] = defaultdict(list)
    by_edge: Dict[Tuple[str, str, str], dict] = {}
    for row in ranked:
        cls = row.get("class", "unknown")
        by_class[cls].append(row)
        source = row["variables"]["source"]["code"]
        target = row["variables"]["target"]["code"]
        by_edge[(cls, source, target)] = row

    # 1) Forced reversal findings.
    for source, target in FORCED_REVERSAL_EDGES:
        row = by_edge.get(("reversal", source, target))
        if row is None:
            warnings.append(
                f"forced_reversal_missing:{source}->{target}"
            )
            continue
        _pick_if_present(selected, selected_keys, row)

    # Fill reversal quota if a forced edge is missing.
    needed_reversal = TARGET_TOP10_CLASS_QUOTAS["reversal"] - sum(
        1 for x in selected if x.get("class") == "reversal"
    )
    if needed_reversal > 0:
        for row in by_class.get("reversal", []):
            if needed_reversal <= 0:
                break
            if _pick_if_present(selected, selected_keys, row):
                needed_reversal -= 1
        if needed_reversal > 0:
            warnings.append(f"reversal_quota_unfilled:{needed_reversal}")

    # 2) Mediation quota, prioritized by outcomes + weak/absent direct edge.
    mediation_pool = list(by_class.get("mediation", []))
    mediation_pool.sort(
        key=lambda x: (
            x.get("outcome_priority", {}).get("is_outcome_target", False),
            -float(x.get("_score_inputs", {}).get("direct_edge_graphs", 999.0)),
            float(x.get("_score_inputs", {}).get("indirect_graphs", 0.0)),
            float(x.get("scores", {}).get("total", 0.0)),
        ),
        reverse=True,
    )
    needed_mediation = TARGET_TOP10_CLASS_QUOTAS["mediation"]
    for row in mediation_pool:
        if needed_mediation <= 0:
            break
        if _pick_if_present(selected, selected_keys, row):
            needed_mediation -= 1
    if needed_mediation > 0:
        warnings.append(f"mediation_quota_unfilled:{needed_mediation}")

    # 3) Threshold quota, prioritized by policy-relevant source levers.
    threshold_pool = list(by_class.get("threshold", []))
    threshold_pool.sort(
        key=lambda x: (
            x.get("policy_relevance", {}).get("is_policy_relevant_lever", False),
            float(x.get("_score_inputs", {}).get("years_active", 0.0)),
            float(x.get("scores", {}).get("total", 0.0)),
        ),
        reverse=True,
    )
    needed_threshold = TARGET_TOP10_CLASS_QUOTAS["threshold"]
    for row in threshold_pool:
        if needed_threshold <= 0:
            break
        if _pick_if_present(selected, selected_keys, row):
            needed_threshold -= 1
    if needed_threshold > 0:
        warnings.append(f"threshold_quota_unfilled:{needed_threshold}")

    # 4) Wildcard: highest remaining score, prefer non-reversal to preserve forced reversal set.
    wildcard = None
    for row in ranked:
        if finding_identity(row) in selected_keys:
            continue
        if row.get("class") == "reversal":
            continue
        wildcard = row
        break
    if wildcard is None:
        for row in ranked:
            if finding_identity(row) in selected_keys:
                continue
            wildcard = row
            break
    if wildcard is not None:
        _pick_if_present(selected, selected_keys, wildcard)
    else:
        warnings.append("wildcard_unfilled")

    # 5) If still below 10, backfill from ranked list while avoiding extra reversals where possible.
    current_reversals = sum(1 for x in selected if x.get("class") == "reversal")
    for row in ranked:
        if len(selected) >= 10:
            break
        if finding_identity(row) in selected_keys:
            continue
        if row.get("class") == "reversal" and current_reversals >= TARGET_TOP10_CLASS_QUOTAS["reversal"]:
            continue
        if _pick_if_present(selected, selected_keys, row):
            if row.get("class") == "reversal":
                current_reversals += 1

    # Final fallback: allow any class if still under 10.
    for row in ranked:
        if len(selected) >= 10:
            break
        _pick_if_present(selected, selected_keys, row)

    selected = selected[:10]
    selected.sort(
        key=lambda x: (
            float(x.get("scores", {}).get("total", 0.0)),
            float(x.get("scores", {}).get("robustness", 0.0)),
            stable_hash(
                [
                    x.get("class", ""),
                    x["variables"]["source"]["code"],
                    x["variables"]["target"]["code"],
                ]
            ),
        ),
        reverse=True,
    )

    # Final quota checks.
    class_counts = Counter(x.get("class", "unknown") for x in selected)
    for cls, req in TARGET_TOP10_CLASS_QUOTAS.items():
        if class_counts.get(cls, 0) < req:
            warnings.append(f"final_quota_shortfall:{cls}:{class_counts.get(cls, 0)}/{req}")

    return selected, warnings


def select_public_top4_diverse(top10: List[dict]) -> Tuple[List[dict], List[str]]:
    warnings = []
    out: List[dict] = []
    used: Set[Tuple[str, str, str, str]] = set()

    def take_first(cls: str) -> Optional[dict]:
        for row in top10:
            if row.get("class") == cls and finding_identity(row) not in used:
                used.add(finding_identity(row))
                return row
        return None

    for cls in ("reversal", "mediation", "threshold"):
        row = take_first(cls)
        if row is None:
            warnings.append(f"public_slot_missing:{cls}")
            continue
        out.append(row)

    wildcard = None
    for row in top10:
        if finding_identity(row) not in used:
            wildcard = row
            used.add(finding_identity(row))
            break
    if wildcard is None:
        warnings.append("public_slot_missing:wildcard")
    else:
        out.append(wildcard)

    out = out[:4]
    return out, warnings


def threshold_country_split(
    corpus: Corpus,
    indicator_code: str,
    threshold_value: Optional[float],
    year: int = 2024,
) -> Optional[dict]:
    if threshold_value is None:
        return None

    values_by_country = corpus.baseline_values_for_year(year)
    income_countries = set(corpus.income_metadata.get("countries", {}).keys())
    if income_countries:
        country_universe = sorted(income_countries)
    else:
        country_universe = sorted(values_by_country.keys())
    below: List[str] = []
    above: List[str] = []
    unknown: List[str] = []
    below_by_class: Dict[str, int] = defaultdict(int)
    above_by_class: Dict[str, int] = defaultdict(int)

    for country in country_universe:
        values = values_by_country.get(country)
        if values is None:
            unknown.append(country)
            continue
        raw = values.get(indicator_code)
        val = as_float(raw)
        if val is None:
            unknown.append(country)
            continue
        group = corpus.country_classification(country, year=year)
        if val < threshold_value:
            below.append(country)
            below_by_class[group] += 1
        else:
            above.append(country)
            above_by_class[group] += 1

    below.sort()
    above.sort()
    unknown.sort()

    return {
        "year": year,
        "threshold_variable": indicator_code,
        "threshold_value": threshold_value,
        "coverage_countries": len(below) + len(above),
        "below_count": len(below),
        "above_count": len(above),
        "missing_count": len(unknown),
        "below_countries": below,
        "above_countries": above,
        "missing_countries": unknown,
        "below_count_by_income_stratum": dict(sorted(below_by_class.items())),
        "above_count_by_income_stratum": dict(sorted(above_by_class.items())),
    }


def attach_threshold_country_splits(findings: List[dict], corpus: Corpus, year: int = 2024) -> None:
    for finding in findings:
        if finding.get("class") != "threshold":
            continue
        nonlin = finding.get("nonlinearity", {})
        threshold_value = as_float(nonlin.get("threshold_latest_year_value"))
        if threshold_value is None:
            threshold_value = as_float(nonlin.get("threshold"))
        split = threshold_country_split(
            corpus=corpus,
            indicator_code=finding["variables"]["source"]["code"],
            threshold_value=threshold_value,
            year=year,
        )
        finding["nonlinearity"]["country_split_latest"] = split
        if split is None:
            finding.setdefault("caveats", []).append(
                "Missing threshold value prevented country below/above split for latest year."
            )


# -----------------------------------------------------------------------------
# Uncertainty flags and formatting
# -----------------------------------------------------------------------------


def uncertainty_flags_for_finding(finding: dict) -> List[str]:
    flags = []
    availability = finding.get("availability", {})
    years_active = str(availability.get("years_active", "0/35"))
    graphs_active = str(availability.get("graphs_active", "0/140"))

    try:
        y_num = int(years_active.split("/")[0])
    except Exception:
        y_num = 0
    try:
        g_num = int(graphs_active.split("/")[0])
    except Exception:
        g_num = 0

    if y_num < 20:
        flags.append("low_year_coverage")
    if g_num < 80:
        flags.append("low_graph_coverage")

    # CI presence check
    has_ci = False
    for sdata in finding.get("stratum_betas", {}).values():
        if isinstance(sdata, dict) and sdata.get("ci_lower") is not None and sdata.get("ci_upper") is not None:
            has_ci = True
            break
    if not has_ci:
        flags.append("ci_missing_or_sparse")

    lineage_status = finding.get("lineage", {}).get("v2_v21_status")
    if lineage_status in {"not_resolved", "structurally_changed"}:
        flags.append(f"lineage_{lineage_status}")

    if finding.get("class") == "reversal":
        flags.append("cross_strata_sign_instability")

    if finding.get("class") == "threshold" and finding.get("nonlinearity", {}).get("reverted_recently"):
        flags.append("recent_linear_reversion")
    if finding.get("class") == "threshold":
        if finding.get("nonlinearity", {}).get("country_split_latest") is None:
            flags.append("threshold_country_split_missing")

    if finding.get("class") == "mediation":
        direct = finding.get("direct_edge_availability", "0/140")
        try:
            d = int(str(direct).split("/")[0])
        except Exception:
            d = 0
        if d > 0:
            flags.append("partial_mediation_direct_edge_present")

    return flags


def compact_stratum_betas(finding: dict) -> Dict[str, dict]:
    out = {}
    for stratum in STRATA:
        row = finding.get("stratum_betas", {}).get(stratum, {})
        if finding["class"] == "mediation":
            out[stratum] = {
                "beta_ab": row.get("beta_ab"),
                "beta_bc": row.get("beta_bc"),
                "indirect_beta_product": row.get("indirect_beta_product"),
            }
        else:
            out[stratum] = {
                "beta": row.get("beta"),
                "ci_lower": row.get("ci_lower"),
                "ci_upper": row.get("ci_upper"),
                "years_active": row.get("years_active"),
            }
    return out


# -----------------------------------------------------------------------------
# Writers
# -----------------------------------------------------------------------------


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=True)


def write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_top_table_md(title: str, findings: List[dict]) -> str:
    lines = [f"# {title}", "", "| Rank | ID | Class | Finding | Graphs | Years | Score |", "|---|---|---|---|---|---|---|"]
    for i, f in enumerate(findings, start=1):
        lines.append(
            "| {rank} | {id} | {cls} | {title} | {graphs} | {years} | {score:.4f} |".format(
                rank=i,
                id=f["finding_id"],
                cls=f["class"],
                title=f["title"].replace("|", "\\|"),
                graphs=f["availability"].get("graphs_active", "n/a"),
                years=f["availability"].get("years_active", "n/a"),
                score=f["scores"].get("total", 0.0),
            )
        )
    lines.append("")
    lines.append("## Raw Evidence")
    for f in findings:
        lines.append("")
        lines.append(f"### {f['finding_id']} — {f['title']}")
        lines.append(f"- `class`: `{f['class']}`")
        lines.append(f"- `variables`: `{f['variables']}`")
        lines.append(f"- `edge_type`: `{f.get('edge_type', 'mixed')}`")
        lines.append(f"- `availability`: `{f['availability']}`")
        lines.append(f"- `stratum_betas`: `{compact_stratum_betas(f)}`")
        if f["class"] == "mediation":
            lines.append(f"- `direct_edge_availability`: `{f.get('direct_edge_availability', 'n/a')}`")
            lines.append(f"- `indirect_path_availability`: `{f.get('indirect_path_availability', 'n/a')}`")
            lines.append(f"- `indirect_path_years_by_stratum`: `{f.get('indirect_path_years_by_stratum', {})}`")
            lines.append(f"- `outcome_priority`: `{f.get('outcome_priority', {})}`")
        if f["class"] == "threshold":
            lines.append(f"- `nonlinearity`: `{f.get('nonlinearity', {})}`")
            lines.append(f"- `policy_relevance`: `{f.get('policy_relevance', {})}`")
        lines.append(f"- `lineage`: `{f.get('lineage', {})}`")
        lines.append(f"- `uncertainty_flags`: `{f.get('uncertainty_flags', [])}`")
        lines.append(f"- `plain_language`: {f.get('plain_language', '')}")
        lines.append(f"- `academic_summary`: {f.get('academic_summary', '')}")
    lines.append("")
    return "\n".join(lines)


def build_lineage_md(findings: List[dict]) -> str:
    lines = ["# v2/v2.1 Lineage Appendix", "", "| ID | Class | Status | Notes |", "|---|---|---|---|"]
    for f in findings:
        lineage = f.get("lineage", {})
        lines.append(
            "| {id} | {cls} | {status} | {notes} |".format(
                id=f["finding_id"],
                cls=f["class"],
                status=lineage.get("v2_v21_status", "unknown"),
                notes=str(lineage.get("notes", "")).replace("|", "\\|"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def build_uncertainty_md(findings: List[dict]) -> str:
    lines = ["# Uncertainty Flags", "", "| ID | Flags |", "|---|---|"]
    for f in findings:
        flags = ", ".join(f.get("uncertainty_flags", [])) or "none"
        lines.append(f"| {f['finding_id']} | {flags} |")
    lines.append("")
    return "\n".join(lines)


def write_exclusion_audit(path: Path, corpus: Corpus) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["code", "label", "domain", "layer", "reason", "excluded_edge_count"],
        )
        writer.writeheader()
        for code, reason in sorted(corpus.exclusion_reasons.items()):
            writer.writerow(
                {
                    "code": code,
                    "label": corpus.indicator_label(code),
                    "domain": corpus.indicator_domain(code),
                    "layer": corpus.indicator_layer(code),
                    "reason": reason,
                    "excluded_edge_count": corpus.exclusion_edge_counts.get(code, 0),
                }
            )


# -----------------------------------------------------------------------------
# Synthetic tests (used by unittest module)
# -----------------------------------------------------------------------------


def synthetic_mediation_rule(
    pair_counts: Dict[Tuple[str, str], int],
    source: str,
    mediator: str,
    target: str,
    full_graph_count: int = FULL_GRAPH_COUNT,
) -> bool:
    return (
        pair_counts.get((source, mediator), 0) == full_graph_count
        and pair_counts.get((mediator, target), 0) == full_graph_count
        and pair_counts.get((source, target), 0) == 0
    )


def synthetic_reversal_rule(stratum_means: Dict[str, float]) -> bool:
    values = [v for v in stratum_means.values() if v is not None]
    return bool(values) and min(values) < 0 < max(values)


def synthetic_threshold_persistence(year_flags: List[bool], min_years: int = 25) -> bool:
    return sum(1 for x in year_flags if x) >= min_years


def deterministic_rank_signature(findings: List[dict]) -> List[str]:
    return [
        stable_hash(
            [
                f.get("class", ""),
                f.get("variables", {}).get("source", {}).get("code", ""),
                f.get("variables", {}).get("target", {}).get("code", ""),
            ]
        )
        for f in findings
    ]


# -----------------------------------------------------------------------------
# Main pipeline
# -----------------------------------------------------------------------------


def run_pipeline(repo_root: Path, output_dir: Path, write_canonical_csv: bool = True) -> dict:
    started = utc_now_iso()

    corpus = Corpus(repo_root=repo_root, write_canonical_csv=write_canonical_csv)
    canonical_path = output_dir / "canonical" / "canonical_edges.csv.gz" if write_canonical_csv else None
    corpus.parse(canonical_csv_path=canonical_path)

    # Discover class candidates
    mediation = compute_mediation_candidates(corpus)
    reversals = compute_sign_reversal_candidates(corpus)
    thresholds = compute_threshold_candidates(corpus)
    hubs = compute_hub_candidates(corpus)
    outcomes = compute_outcome_surprise_candidates(corpus)

    all_candidates = mediation + reversals + thresholds + hubs + outcomes

    # Score and rank (global list)
    ranked = compute_scores(all_candidates)

    # Apply class-diverse constrained selection.
    top10, selection_warnings = select_diverse_top10(ranked)
    top4, public_selection_warnings = select_public_top4_diverse(top10)

    lineage_mapper = LineageMapper(corpus)
    lineage_mapper.load()

    # Add country below/above threshold splits for selected threshold findings.
    attach_threshold_country_splits(top10, corpus=corpus, year=2024)

    for i, finding in enumerate(top10, start=1):
        finding_id = f"F{i:02d}"
        finding["finding_id"] = finding_id
        finding["lineage"] = lineage_mapper.finding_lineage(finding)
        finding["uncertainty_flags"] = uncertainty_flags_for_finding(finding)

    for i, finding in enumerate(top4, start=1):
        finding["public_rank"] = i

    # Build evidence sheets for top10
    evidence_dir = output_dir / "evidence"
    for finding in top10:
        payload = {
            "finding": finding,
            "schema_reference": FINDING_SCHEMA,
        }
        write_json(evidence_dir / f"{finding['finding_id']}.json", payload)

    # Build markdown artifacts
    write_md(output_dir / "TOP_10_RAW.md", build_top_table_md("Atlas Causal Findings — Top 10", top10))
    write_md(output_dir / "TOP_4_PUBLIC.md", build_top_table_md("Atlas Causal Findings — Top 4 Public", top4))
    write_md(output_dir / "LINEAGE_APPENDIX.md", build_lineage_md(top10))
    write_md(output_dir / "UNCERTAINTY_FLAGS.md", build_uncertainty_md(top10))

    # Exclusion audit
    write_exclusion_audit(output_dir / "excluded_variables_audit.csv", corpus)

    package = {
        "generated_at": utc_now_iso(),
        "started_at": started,
        "source_of_truth": "viz/data/v31/temporal_graphs",
        "lineage_source": "v2/v2.1 edge and node exports",
        "locked_decisions": {
            "corpus": "current_v31_with_v2_v21_lineage",
            "filtering": "strict_scientific",
            "ranking": "robustness_first",
            "output_style": "raw_first",
        },
        "coverage": {
            "total_graphs_seen": corpus.total_graphs_seen,
            "expected_graphs": FULL_GRAPH_COUNT,
            "years_expected": YEARS_EXPECTED,
            "strata": list(STRATA),
            "pairs_total": len(corpus.pair_presence),
        },
        "candidate_counts": {
            "mediation": len(mediation),
            "reversal": len(reversals),
            "threshold": len(thresholds),
            "hub": len(hubs),
            "outcome_surprise": len(outcomes),
            "all_candidates": len(all_candidates),
        },
        "top10": top10,
        "top4": top4,
        "public_selection_policy": "top4 selected as 1 reversal + 1 mediation + 1 threshold + 1 wildcard",
        "top10_selection_policy": (
            "class-constrained selection: 4 reversal (forced set), 3 mediation, 2 threshold, 1 wildcard"
        ),
        "selection_warnings": selection_warnings,
        "public_selection_warnings": public_selection_warnings,
        "finding_schema": FINDING_SCHEMA,
        "notes": {
            "ci_policy": "edge-level CI only; no synthetic path-level CI",
            "lineage_statuses": [
                "confirmed_same_edge",
                "code_renamed_semantically_same",
                "structurally_changed",
                "not_resolved",
            ],
        },
    }

    write_json(output_dir / "atlas_findings_package.json", package)

    # Small summary for fast reading.
    summary_lines = [
        "# Atlas Causal Findings Extraction Summary",
        "",
        f"- Generated at: `{package['generated_at']}`",
        f"- Graphs parsed: `{package['coverage']['total_graphs_seen']}/{FULL_GRAPH_COUNT}`",
        f"- Candidate findings: `{package['candidate_counts']['all_candidates']}`",
        f"- Top findings written: `10` (with `4` public subset)",
        f"- Excluded variables: `{len(corpus.exclusion_reasons)}`",
        "",
        "## Top 10 Class Mix",
        f"- `{dict(Counter(f.get('class', 'unknown') for f in top10))}`",
        "",
        "## Selection Warnings",
    ]
    for warning in selection_warnings + public_selection_warnings:
        summary_lines.append(f"- `{warning}`")
    if not (selection_warnings or public_selection_warnings):
        summary_lines.append("- `none`")
    summary_lines.extend([
        "",
        "## Top 4",
    ])
    for f in top4:
        summary_lines.append(
            f"- `{f['finding_id']}` [{f['class']}] {f['title']} (score={f['scores']['total']:.4f})"
        )
    summary_lines.append("")
    write_md(output_dir / "SUMMARY.md", "\n".join(summary_lines))

    return package


def default_output_dir(viz_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return viz_root / "docs" / "reports" / f"atlas-causal-findings-{stamp}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Atlas causal findings from full v31 corpus.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Global_Project repository root (default inferred from script location).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for findings package (default docs/reports/atlas-causal-findings-YYYY-MM-DD).",
    )
    parser.add_argument(
        "--no-canonical-csv",
        action="store_true",
        help="Skip writing canonical edge CSV.GZ table.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    viz_root = repo_root / "viz"
    output_dir = args.output_dir.resolve() if args.output_dir else default_output_dir(viz_root)

    package = run_pipeline(
        repo_root=repo_root,
        output_dir=output_dir,
        write_canonical_csv=not args.no_canonical_csv,
    )

    top4 = package.get("top4", [])
    print("Atlas findings extraction completed")
    print(f"Output directory: {output_dir}")
    print(f"Graphs parsed: {package['coverage']['total_graphs_seen']}/{FULL_GRAPH_COUNT}")
    print(f"Candidates: {package['candidate_counts']['all_candidates']}")
    print("Top 4:")
    for f in top4:
        print(f"  - {f['finding_id']} [{f['class']}] score={f['scores']['total']:.4f}")


if __name__ == "__main__":
    main()
