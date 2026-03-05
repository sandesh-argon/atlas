#!/usr/bin/env python3
import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "atlas_findings_extraction.py"
SPEC = importlib.util.spec_from_file_location("atlas_findings_extraction", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules["atlas_findings_extraction"] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DummyCorpus:
    def __init__(self):
        self.indicators = {
            "cur_a": {"label": "Alpha Metric", "domain": "Governance"},
            "cur_b": {"label": "Beta Metric", "domain": "Economic"},
        }
        self.v21_nodes_paths = []
        self.v21_edges_paths = []

    def indicator_label(self, code: str) -> str:
        return str(self.indicators.get(code, {}).get("label", code))

    def indicator_domain(self, code: str) -> str:
        return str(self.indicators.get(code, {}).get("domain", "unknown"))


class AtlasFindingsExtractionTests(unittest.TestCase):
    def _candidate(
        self,
        cls: str,
        source: str,
        target: str,
        score_seed: float = 0.5,
        mediator: str = "",
    ) -> dict:
        return {
            "class": cls,
            "title": f"{source}->{target}",
            "variables": {
                "source": {"code": source, "label": source},
                "mediator": {"code": mediator, "label": mediator} if mediator else None,
                "target": {"code": target, "label": target},
            },
            "availability": {"years_active": "35/35", "graphs_active": "140/140"},
            "stratum_betas": {},
            "_score_inputs": {
                "graphs_active": 140,
                "years_active": 35,
                "beta_magnitude": score_seed,
                "ci_coverage": 1.0,
                "reversal_strength": score_seed,
                "class": cls,
                "decade_consistency": 1.0,
                "direct_edge_graphs": 0 if cls == "mediation" else 0,
                "indirect_graphs": 140 if cls == "mediation" else 0,
            },
            "outcome_priority": {"is_outcome_target": cls == "mediation", "outcome_concept": "gdp_income"},
            "policy_relevance": {"is_policy_relevant_lever": cls == "threshold"},
            "nonlinearity": {"country_split_latest": {"below_count": 1, "above_count": 1}},
        }

    def test_synthetic_mediation_detection(self) -> None:
        pair_counts = {
            ("A", "B"): 140,
            ("B", "C"): 140,
            ("A", "C"): 0,
        }
        self.assertTrue(MODULE.synthetic_mediation_rule(pair_counts, "A", "B", "C"))
        pair_counts[("A", "C")] = 1
        self.assertFalse(MODULE.synthetic_mediation_rule(pair_counts, "A", "B", "C"))

    def test_synthetic_reversal_detection(self) -> None:
        self.assertTrue(
            MODULE.synthetic_reversal_rule(
                {"unified": -0.2, "developing": -0.1, "emerging": 0.1, "advanced": 0.3}
            )
        )
        self.assertFalse(
            MODULE.synthetic_reversal_rule(
                {"unified": 0.2, "developing": 0.1, "emerging": 0.3, "advanced": 0.4}
            )
        )

    def test_synthetic_threshold_persistence(self) -> None:
        flags_25 = [True] * 25 + [False] * 10
        flags_24 = [True] * 24 + [False] * 11
        self.assertTrue(MODULE.synthetic_threshold_persistence(flags_25, min_years=25))
        self.assertFalse(MODULE.synthetic_threshold_persistence(flags_24, min_years=25))

    def test_interpretability_filter_blocks_proxy_variables(self) -> None:
        reason = MODULE.interpretability_reason(
            code="SP.POP.TOTL",
            label="Total Population",
            node_type="indicator",
            layer=4,
        )
        self.assertEqual(reason, "population_bucket_proxy_code")

        reason_ok = MODULE.interpretability_reason(
            code="SE.XPD.TOTL.GD.ZS",
            label="Government Expenditure on Education, Total (% of GDP)",
            node_type="indicator",
            layer=5,
        )
        self.assertIsNone(reason_ok)

    def test_lineage_renamed_mapping_resolves(self) -> None:
        corpus = DummyCorpus()
        mapper = MODULE.LineageMapper(corpus)
        mapper.v21_nodes = {"old_a", "old_b"}
        mapper.v21_edges = {("old_a", "old_b")}
        mapper.v21_label_to_ids = {
            "alpha metric": {"old_a"},
            "beta metric": {"old_b"},
        }

        status, _ = mapper.edge_status("cur_a", "cur_b")
        self.assertEqual(status, "code_renamed_semantically_same")

    def test_uncertainty_flags_include_missing_ci(self) -> None:
        finding = {
            "class": "threshold",
            "availability": {"years_active": "35/35", "graphs_active": "140/140"},
            "stratum_betas": {
                "unified": {"beta": 0.2, "ci_lower": None, "ci_upper": None},
                "developing": {"beta": 0.2, "ci_lower": None, "ci_upper": None},
                "emerging": {"beta": 0.2, "ci_lower": None, "ci_upper": None},
                "advanced": {"beta": 0.2, "ci_lower": None, "ci_upper": None},
            },
            "lineage": {"v2_v21_status": "confirmed_same_edge"},
            "nonlinearity": {"reverted_recently": False},
        }
        flags = MODULE.uncertainty_flags_for_finding(finding)
        self.assertIn("ci_missing_or_sparse", flags)

        finding_with_ci = {
            **finding,
            "stratum_betas": {
                "unified": {"beta": 0.2, "ci_lower": 0.1, "ci_upper": 0.3},
                "developing": {"beta": 0.2, "ci_lower": None, "ci_upper": None},
                "emerging": {"beta": 0.2, "ci_lower": None, "ci_upper": None},
                "advanced": {"beta": 0.2, "ci_lower": None, "ci_upper": None},
            },
        }
        flags_with_ci = MODULE.uncertainty_flags_for_finding(finding_with_ci)
        self.assertNotIn("ci_missing_or_sparse", flags_with_ci)

    def test_ranking_determinism(self) -> None:
        base = {
            "class": "reversal",
            "title": "Test Finding",
            "variables": {
                "source": {"code": "A", "label": "Alpha"},
                "mediator": None,
                "target": {"code": "B", "label": "Beta"},
            },
            "availability": {"years_active": "35/35", "graphs_active": "140/140"},
            "stratum_betas": {},
            "_score_inputs": {
                "graphs_active": 140,
                "years_active": 35,
                "beta_magnitude": 0.8,
                "ci_coverage": 1.0,
                "reversal_strength": 1.2,
                "class": "reversal",
                "decade_consistency": 1.0,
            },
        }
        candidates1 = [
            dict(base),
            {
                **dict(base),
                "title": "Test Finding 2",
                "variables": {
                    "source": {"code": "C", "label": "Gamma"},
                    "mediator": None,
                    "target": {"code": "D", "label": "Delta"},
                },
            },
        ]
        candidates2 = [dict(candidates1[0]), dict(candidates1[1])]

        ranked1 = MODULE.compute_scores(candidates1)
        ranked2 = MODULE.compute_scores(candidates2)

        self.assertEqual(
            MODULE.deterministic_rank_signature(ranked1),
            MODULE.deterministic_rank_signature(ranked2),
        )

    def test_diverse_top10_selection_quotas_and_forced_reversals(self) -> None:
        forced = MODULE.FORCED_REVERSAL_EDGES
        candidates = []
        for idx, (s, t) in enumerate(forced):
            candidates.append(self._candidate("reversal", s, t, score_seed=0.9 - idx * 0.05))
        candidates.append(self._candidate("reversal", "extra_rev_src", "extra_rev_tgt", score_seed=0.95))
        candidates.append(self._candidate("mediation", "m1", "m1_t", score_seed=0.75, mediator="m1_mid"))
        candidates.append(self._candidate("mediation", "m2", "m2_t", score_seed=0.74, mediator="m2_mid"))
        candidates.append(self._candidate("mediation", "m3", "m3_t", score_seed=0.73, mediator="m3_mid"))
        candidates.append(self._candidate("threshold", "t1", "t1_t", score_seed=0.70))
        candidates.append(self._candidate("threshold", "t2", "t2_t", score_seed=0.69))
        candidates.append(self._candidate("hub", "h1", "h1_t", score_seed=0.68))

        ranked = MODULE.compute_scores(candidates)
        top10, warnings = MODULE.select_diverse_top10(ranked)

        self.assertEqual(len(top10), 10)
        self.assertFalse(any(w.startswith("final_quota_shortfall") for w in warnings))
        class_counts = {}
        for row in top10:
            class_counts[row["class"]] = class_counts.get(row["class"], 0) + 1
        self.assertEqual(class_counts.get("reversal", 0), 4)
        self.assertEqual(class_counts.get("mediation", 0), 3)
        self.assertEqual(class_counts.get("threshold", 0), 2)

        forced_set = set(forced)
        selected_reversals = {
            (x["variables"]["source"]["code"], x["variables"]["target"]["code"])
            for x in top10
            if x["class"] == "reversal"
        }
        self.assertTrue(forced_set.issubset(selected_reversals))
        self.assertNotIn(("extra_rev_src", "extra_rev_tgt"), selected_reversals)

    def test_public_top4_class_mix(self) -> None:
        top10 = [
            self._candidate("reversal", "r", "rt", 0.9),
            self._candidate("mediation", "m", "mt", 0.8, mediator="mm"),
            self._candidate("threshold", "t", "tt", 0.7),
            self._candidate("hub", "h", "ht", 0.6),
        ]
        for i, row in enumerate(top10):
            row["scores"] = {"total": 1.0 - i * 0.1}
        out, warnings = MODULE.select_public_top4_diverse(top10)
        self.assertEqual(len(out), 4)
        classes = [x["class"] for x in out]
        self.assertIn("reversal", classes)
        self.assertIn("mediation", classes)
        self.assertIn("threshold", classes)
        self.assertEqual(len(warnings), 0)


if __name__ == "__main__":
    unittest.main()
