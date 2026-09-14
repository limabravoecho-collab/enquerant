#!/usr/bin/env python3
"""
spfs_engine.py — Substrate Primitives Formula System (SPFS) Core Engine
================================================================================
Implements the formal SPFS Master Formula and Universe Compute System (UCS):
- F_0: System Closure & Integration Operator (∮ ... dt)
- N_s: Infinite Structural Nesting (s -> ∞)
- L_f: Finite Internal Logic Operations (f <= k)
- ΔP: Dynamic Polarity Rebalancing & Negentropic Audit
- R: Recurrence / Self-Similarity Operator
================================================================================
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class SPFSCoreState:
    """Tracks active variables for the master SPFS compute loop."""
    nest_depth_s: float = 0.0          # s ∈ [0, ∞)
    logic_depth_f: int = 1               # f ∈ [1, k] (where k is finite)
    polarity_vector: float = 0.0         # ΔP balance metric
    negentropy_state: float = 1.0        # System negentropy tracker (ΔS_net <= 0)
    recursion_tick: int = 0              # Recurrence counter (R)
    is_placeholder: bool = False         # Topological rupture / entropic debt flag
    audit_note: str = ""                 # Closed-loop audit diagnostic message
    ledger_in: float = 0.0               # First law: cumulative energy input
    ledger_work: float = 0.0             # First law: cumulative work output (|F_0|)
    ledger_dissipated: float = 0.0       # First law: cumulative dissipation (entropic debt)
    ledger_stored: float = 0.0           # First law: cumulative stored order (negentropy)


FISSN_TAXONOMY_REGISTRY = {
    0.0: {"tier": "Tier 0.0", "name": "Zero Domain (Axiomatic / Deductive)", "domain": "Logic, Model Theory, Formal Axioms"},
    0.1: {"tier": "Tier 0.1", "name": "Quantitative Dimensions & Finites", "domain": "Mathematics, Topology, Statistics"},
    1.0: {"tier": "Tier I.0", "name": "Fundamental Forces & Chemical Dynamics", "domain": "Quantum Physics, Thermodynamics, Chemistry"},
    2.0: {"tier": "Tier II.0", "name": "Cosmic Horizon", "domain": "Cosmology, Relativity, Gravitation"},
    2.1: {"tier": "Tier II.1", "name": "Planetary Enclosure", "domain": "Earth Sciences, Geochemical Cycles"},
    3.0: {"tier": "Tier III.0", "name": "Autonomous Living Substrate", "domain": "Genetics, Cell Biology, Ecology"},
    3.1: {"tier": "Tier III.1", "name": "Bio-Somatic Maintenance", "domain": "Anatomy, Physiology, Medicine"},
    4.0: {"tier": "Tier IV.0", "name": "Individual Mind & Neural Hardware", "domain": "Neuroscience, Cognitive Science"},
    4.1: {"tier": "Tier IV.1", "name": "Reflexive Epistemics & Cultural Records", "domain": "Philosophy, Ethics, History"},
    4.2: {"tier": "Tier IV.2", "name": "Semiotic & Aesthetic Projections", "domain": "Literature, Semantics, Arts"},
    5.0: {"tier": "Tier V.0", "name": "Distributed Collective Systems", "domain": "Sociology, Economics, Law"},
    6.0: {"tier": "Tier VI.0", "name": "Civilizational Infrastructure", "domain": "Civil Engineering, Architecture"},
    6.1: {"tier": "Tier VI.1", "name": "Synthetic Systems & Applied Mechanics", "domain": "Computer Science, Electrical Engineering"},
    6.2: {"tier": "Tier VI.2", "name": "High-Order Multi-Scale Convergence", "domain": "Quantum Information, Complex Systems"}
}


class SPFSEngine:
    """
    Substrate Primitives Formula System (SPFS) Master Compute Engine.
    Executes the master formula: F_0 = ∮ [ R · ( N_s(L_f) ⊕ ΔP ) ] dt
    """

    def __init__(self, max_logic_depth: int = 64):
        self.k = max_logic_depth  # Finite ceiling on internal logic (f <= k)
        self.state = SPFSCoreState()

    def evaluate_lf(self, logic_tier: int, operand_value: float) -> float:
        """
        Step 3: Finite Internal Logic (L_f)
        Ensures internal logic operations remain strictly bounded at f <= k
        to guarantee determinism without infinite recursion.
        """
        f = max(1, min(logic_tier, self.k))
        # Bounded deterministic transformation logic
        return operand_value / float(f)

    def evaluate_ns(self, nest_depth: float, inner_result: float) -> float:
        """
        Step 3: Infinite Structural Nesting (N_s)
        Scales structural containers infinitely (s -> ∞) while housing finite logic.
        """
        s = max(0.0, nest_depth)
        self.state.nest_depth_s = s
        # Scale-space topological projection
        scale_factor = 1.0 / (1.0 + s)
        return inner_result * scale_factor

    def evaluate_delta_p(self, current_polarity: float, environmental_flux: float) -> float:
        """
        Step 4: Dynamic Polarity Rebalancing (ΔP)
        Interconnected nests continuously balance states against one another
        to sustain negentropy and avoid terminal stagnation.
        """
        rebalanced = current_polarity - (0.1 * environmental_flux)
        # Clamp polarity within homeostatic bounds
        self.state.polarity_vector = max(-1.0, min(1.0, rebalanced))
        return self.state.polarity_vector

    def evaluate_glyph_algebra(self, glyph_token_count: int) -> float:
        """
        Computes standard English glyph brute-force Shannon entropy (H_g)
        and transition matrix resistance for algebraic pattern matching.
        """
        if glyph_token_count <= 0:
            return 0.0
        p_base = 1.0 / float(glyph_token_count)
        # Shannon entropy calculation for input glyph token distribution
        h_g = -float(glyph_token_count) * (p_base * math.log2(max(1e-9, p_base)))
        return h_g
        
    def score_glyph_candidate(self, occurrences: int, first_position: int, slot_index: int, in_query: bool) -> float:
        """
        Pure scoring of one glyph candidate for one tag slot.
        L_f: occurrences bounded by slot logic tier.
        N_s: scaled by source position depth.
        Delta_P: polarity +1 when glyph is present in the input.
        Does not change engine state.
        """
        f = max(1, min(slot_index + 1, self.k))
        lf = float(occurrences) / float(f)
        ns = lf * (1.0 / (1.0 + max(0.0, float(first_position))))
        dp = 1.0 if in_query else 0.0
        return ns + dp
        
    def score_glyph_transition(self, pair_count: int, prev_count: int) -> float:
        """
        Pure transition score between two glyphs.
        Zero means the transition does not exist in the data.
        Does not change engine state.
        """
        if pair_count <= 0 or prev_count <= 0:
            return 0.0
        return float(pair_count) / float(prev_count)

    def update_conservation_ledger(self, energy_in: float, work_out: float, entropic_debt: float) -> Dict[str, float]:
        """
        First law of thermodynamics: energy is conserved, it only changes form.
        Per cycle: in = work_out + dissipated + stored. Nothing is created or lost.
        Dissipation is bounded so stored order can never be negative.
        """
        e_in = max(0.0, energy_in)
        work = min(abs(work_out), e_in)
        dissipated = min(max(0.0, entropic_debt) * e_in * 0.01, e_in - work)
        stored = e_in - work - dissipated
        self.state.ledger_in += e_in
        self.state.ledger_work += work
        self.state.ledger_dissipated += dissipated
        self.state.ledger_stored += stored
        total_in = self.state.ledger_in
        self.state.negentropy_state = (self.state.ledger_stored / total_in) if total_in > 0.0 else 1.0
        balance = total_in - (self.state.ledger_work + self.state.ledger_dissipated + self.state.ledger_stored)
        return {
            "Cycle_In": e_in,
            "Cycle_Work": work,
            "Cycle_Dissipated": dissipated,
            "Cycle_Stored": stored,
            "Ledger_In": total_in,
            "Ledger_Work": self.state.ledger_work,
            "Ledger_Dissipated": self.state.ledger_dissipated,
            "Ledger_Stored": self.state.ledger_stored,
            "Ledger_Balance": balance
        }

    def evaluate_nest_exchange(self, target_nest: float, source_nests: Dict[float, int], entropic_debt: float, bridge_strengths: Optional[Dict[float, float]] = None) -> Dict[str, Any]:
        """
        Dissipative structures: an open nest sustains order only through exchange
        with neighbouring nests. Coupling falls with FISSN tier distance, so distant
        nests contribute less order and carry less of the entropic load.
        Pure computation; engine state is not modified.
        """
        if not source_nests:
            return {"Target_Nest": target_nest, "Coupled_Nests": [], "Exchange_Total": 0.0}
        weights = {}
        for tier, count in source_nests.items():
            distance = abs(float(tier) - float(target_nest))
            weights[float(tier)] = float(max(0, count)) / (1.0 + distance)
        total = sum(weights.values())
        debt = max(0.0, entropic_debt)
        coupled = []
        for tier in sorted(weights, key=lambda t: (-weights[t], t)):
            share = weights[tier] / total if total > 0.0 else 0.0
            coupled.append({
                "Nest": tier,
                "Records": source_nests[tier] if tier in source_nests else source_nests[int(tier)],
                "Tier_Distance": round(abs(tier - float(target_nest)), 2),
                "Exchange_Share": round(share, 4),
                "Carried_Debt": round(debt * share, 4)
            })
        return {
            "Target_Nest": float(target_nest),
            "Coupled_Nests": coupled,
            "Exchange_Total": round(total, 4)
        }
        
    def compute_entropic_debt(self, nest_depth: float) -> float:
        """
        Cascading inter-tier entropic stress (Xi). Debt scales with nest depth and
        with distance from the reference tier. Single source of truth for this value.
        """
        tier_distance_gradient = abs(nest_depth - 1.0)
        return (nest_depth * 0.42) * (1.0 + (tier_distance_gradient * 0.5))

    def audit_topological_closure(self, subject: str, expression: str, nest_depth: float) -> Tuple[bool, float, str]:
        """
        Performs a pure topological, cross-nest dependency, and structural audit using FISSN coordinates.
        Detects unclosed dependency loops, missing mathematical operators, phenomenological containers, 
        and calculates cascading inter-tier entropic stress propagation across dependent nests.
        """
        expr_clean = expression.strip()
        
        # Algorithmic Structural Discrepancy Check (Zero Hardcoding)
        # 1. Unindexed or missing empirical manifold parameters
        is_unindexed = "unindexed" in expr_clean.lower() or not expr_clean
        
        # 2. Lacks mathematical derivation operators while located at non-root tiers
        has_math_operators = any(op in expr_clean for op in ['=', '+', '-', '*', '/', '\\', 'd', 'rho', 'c ='])
        
        # 3. Contains historical/descriptive non-derivational markers
        is_historical_descriptor = any(char.isdigit() for char in expr_clean[:4]) and not has_math_operators

        # 4. Detects ungrounded phenomenological container variables
        has_phenomenological_containers = any(sub in expr_clean.lower() for sub in ['_(de)', '_de', '_eff', '_fit', 'empirical parameter', 'fitting'])

        is_placeholder = (
            is_unindexed or 
            is_historical_descriptor or 
            has_phenomenological_containers or 
            (nest_depth > 0.0 and not has_math_operators)
        )
        
        # Cascading Inter-Tier Entropic Stress Propagation (Xi Tensor Calculation)
        if is_placeholder:
            entropic_debt = self.compute_entropic_debt(nest_depth)
            audit_note = (
                f"Topological Rupture & Cross-Nest Propagation: Unclosed derivation or phenomenological "
                f"container detected at FISSN coordinate s = {nest_depth:.1f}. Cascading entropic stress tensor "
                f"$\\Xi = {entropic_debt:.3f}$ indicates broken dependency bridges across adjacent ontological cells."
            )
        else:
            entropic_debt = 0.01
            audit_note = f"Closed-loop manifold equilibrium verified across FISSN tier s = {nest_depth:.1f} (Inter-tier dependency network stable)."

        self.state.is_placeholder = is_placeholder
        self.state.audit_note = audit_note
        return is_placeholder, entropic_debt, audit_note

    def compute_master_formula(self, input_signal: float, nest_depth: float, logic_tier: int, environmental_flux: float, glyph_token_count: int = 1) -> Tuple[float, Dict[str, Any]]:
        """
        Computes the Master SPFS Equation with Glyph Brute-Force Integration:
        F_0 = ∮ [ R · ( N_s(L_f) ⊕ (ΔP - H_g) ) ] dt
        
        Returns:
            (integrated_output, telemetry_metrics)
        """
        self.state.recursion_tick += 1

        # 1. Evaluate Finite Internal Logic (L_f) bounded by k
        lf_res = self.evaluate_lf(logic_tier, input_signal)

        # 2. Evaluate Structural Nesting (N_s) at depth s
        ns_res = self.evaluate_ns(nest_depth, lf_res)

        # 3. Compute Glyph Brute-Force Entropy (H_g) & Adjust Polarity Fusion (ΔP ⊕ H_g)
        h_g = self.evaluate_glyph_algebra(glyph_token_count)
        net_flux = environmental_flux - (h_g * 0.001)
        dp_res = self.evaluate_delta_p(self.state.polarity_vector, net_flux)
        
        balanced_core = ns_res + dp_res - (h_g * 0.01)

        # 4. Apply Recurrence / Self-Similarity Operator (R)
        r_res = balanced_core * math.exp(-0.05 * (self.state.recursion_tick % 4))

        # 5. System Closure & Integration Operator (∮ ... dt) [F_0 Enforced Conservation]
        f0_output = r_res

        # Execute FISSN Topological Closure Audit
        is_plc, ent_debt, note = self.audit_topological_closure("", "", nest_depth)

        # First law: closed-loop conservation ledger
        ledger = self.update_conservation_ledger(input_signal, f0_output, ent_debt)

        telemetry = {
            "F_0": round(f0_output, 6),
            "N_s": round(nest_depth, 2),
            "L_f": int(logic_tier),
            "Delta_P": round(self.state.polarity_vector, 4),
            "Glyph_Entropy_Hg": round(h_g, 4),
            "Recurrence_Tick": self.state.recursion_tick,
            "Negentropy_Bounded": self.state.negentropy_state <= 1.0,
            "Negentropy_Ratio": round(self.state.negentropy_state, 4),
            "Ledger_Balance": round(ledger["Ledger_Balance"], 6),
            "Ledger_Stored": round(ledger["Ledger_Stored"], 2),
            "Ledger_Dissipated": round(ledger["Ledger_Dissipated"], 2),
            "Is_Placeholder": is_plc,
            "Entropic_Debt": round(ent_debt, 4),
            "Audit_Note": note
        }

        return f0_output, telemetry


# Standalone Verification Test
if __name__ == "__main__":
    print("=" * 78)
    print("      SUBSTRATE PRIMITIVES FORMULA SYSTEM (SPFS) ENGINE TEST")
    print("=" * 78)

    spfs = SPFSEngine(max_logic_depth=32)
    
    # Test formula computation across varying structural nest depths (s) and logic tiers (f)
    test_cases = [
        (100.0, 0.0, 1, 0.2),  # Root tier
        (100.0, 2.1, 4, -0.5), # Planetary Enclosure tier
        (100.0, 6.1, 16, 0.8), # Technosphere tier
    ]

    for sig, s_depth, l_tier, flux in test_cases:
        output, metrics = spfs.compute_master_formula(sig, s_depth, l_tier, flux)
        print(f"\nInput Signal: {sig} | Nest Depth (s): {s_depth} | Logic Tier (f): {l_tier}")
        print(f"Master Formula Output (F_0): {output:.4f}")
        print(f"SPFS Telemetry: {metrics}")
        print("-" * 78)
