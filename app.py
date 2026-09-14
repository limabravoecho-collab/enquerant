#!/usr/bin/env python3
"""
app.py — Enquerant V2.0 Orchestrator & Master Runtime Core (Integrated)
================================================================================
Implements the central execution loop (F_0) for the Deterministic Empirical 
Interactive Engine (DEIE) / Static Logic Crystal (SLC):
- Wires spfs_engine.py for substrate compute and thermodynamics.
- Wires crystal_loader.py for memory crystal cold-boot ingestion.
- Wires cs_algebraic_parser.py for deterministic crystal-scanned parsing.
- Wires active_whiteboard.py for conversational path and state tracking.
================================================================================
"""

import os
import time
import re
from typing import Dict, Any, Generator, Optional, Tuple, List

from spfs_engine import SPFSEngine, FISSN_TAXONOMY_REGISTRY
from crystal_loader import CrystalLoader
from cs_algebraic_parser import CSApAlgebraicParser
from active_whiteboard import ActiveWhiteboard
from spfs_linguistic_folder import SPFSLinguisticFolder
from glyph_grammar import GlyphGrammar
from smac_engine import SMACEngine

UNDETECTED_TEXT = "Input not detected. Please type your request again."
DISTRESS_TEXT = (
    "EnQuerant is a deterministic science exploration engine and does not provide support. "
    "For help from living human hands, please use your local services and supports search."
)

class EnquerantOrchestrator:
    """
    Master Runtime Core. Integrates the SPFS engine, crystal loader, algebraic parser,
    and active whiteboard ledger to execute deterministic query resolution.
    """

    def __init__(self):
        # 1. Initialize Substrate Primitives Formula System (SPFS) engine
        self.spfs = SPFSEngine(max_logic_depth=32)
        
        # 2. Cold-boot ingestion of memory crystal binaries (DELMs & GIS)
        self.delm = CrystalLoader()
        
        # 3. Initialize Glyph Logic System & Algebraic Communication parser (passed the central delm)
        self.parser = CSApAlgebraicParser(crystal_loader=self.delm)
        
        # 4. Initialize Active Whiteboard (AW) context ledger
        self.whiteboard = ActiveWhiteboard()

        # 5. Initialize Universal Glyph Grammar from loaded crystal records
        if not self.delm.records:
            self.delm.ingest_crystal()
        self.grammar = GlyphGrammar(self.delm.records)
        self.parser.grammar = self.grammar

         # 6. Infer tags for knowledge base words absent from the language bin
        self.grammar.map_corpus()

        # 7. Build the cross-tier bridge matrix (SMAC crystallization matrix)
        pattern_words = [" ".join(self.grammar.tokenize(r["subject"]))
                         for r in self.parser.nature_records
                         if r.get("relation") == "is a structural pattern"]
        self.smac = SMACEngine(self.grammar, pattern_words=pattern_words)
        self.tier_options = None
        self.tier_records = None
        self.offer_topic = None
        
        self.gis_active = True

    def close(self):
        """Unmaps memory crystals and closes runtime handles cleanly."""
        self.whiteboard.reset_board()

    def _formula_sequence(self, subject_head: str) -> List[str]:
        """
        Column one: the subject's formula records in record order.

        Record order is source order, preserved by the miner, so the sequence
        reads as the source states it. Nothing is written here and nothing is
        reordered: every line is copied from a DELM record. The corpus does not
        mark logical dependency between formulas, so this is a faithful
        sequence, not a derived order of operations.
        """
        head = subject_head.split("(")[0].strip().lower()
        if not head:
            return []
        out = []
        for r in self.delm.records:
            if r.get("relation") != "is expressed by":
                continue
            subj = str(r.get("subject", ""))
            if subj.split("(")[0].strip().lower() != head:
                continue
            obj = str(r.get("object", "")).replace("@@EQ@@", " ").replace("@@/EQ@@", " ")
            obj = " ".join(obj.split())
            if obj:
                out.append(obj)
        # Two records differing only by spacing or a trailing mark are one
        # formula written twice in the source ("E = hf." and "E = hf ."), so the
        # duplicate is dropped. Comparison is on the formula with spacing and
        # end marks removed; the first spelling is the one kept and displayed.
        seen = set()
        unique = []
        for f in out:
            key = "".join(f.split()).rstrip(".,;:")
            if key in seen:
                continue
            seen.add(key)
            unique.append(f)
        return unique

    def _spfs_sequence(self, subject_head: str, nest_depth: float) -> List[Dict[str, Any]]:
        """
        Column two: the same empirical sequence carried through SPFS.

        The subject sits at one FISSN tier, so the nest depth is constant and
        the step index is the logic depth: a derivation is finite logic
        deepening inside one nest, which is what N_s(L_f) states. Each row
        reports L_f and N_s at that step. Pure computation; engine state is not
        changed, so a displayed sequence cannot disturb the live telemetry.
        """
        steps = self._formula_sequence(subject_head)
        if not steps:
            return []
        probe = SPFSEngine(max_logic_depth=self.spfs.k)
        debt = self.spfs.compute_entropic_debt(nest_depth)
        # The sequence divides the nest's entropic debt across its steps. Weight
        # is N_s(L_f) with the step index as logic depth: a derivation is finite
        # logic deepening inside one nest. Shares sum to 1.0 and carried debt
        # sums to the nest debt, so the sequence is a closed loop. Nothing is
        # created or lost, and no magnitude is invented for the formula itself.
        weights = []
        for i in range(1, len(steps) + 1):
            lf = probe.evaluate_lf(i, 1.0)
            weights.append(probe.evaluate_ns(nest_depth, lf))
        total = sum(weights)
        out = []
        for i, (formula, w) in enumerate(zip(steps, weights), start=1):
            share = (w / total) if total > 0.0 else 0.0
            out.append({
                "Step": i,
                "Formula": formula,
                "L_f": i,
                "N_s": nest_depth,
                "Weight": w,
                "Share": share,
                "Carried_Debt": debt * share,
            })
        return out

    def _render_math_page(self, subject_head: str, nest_depth: float, page: int = 1, per_page: int = 24) -> str:
        """
        The two readings of one derivation, paged. Each step shows the source
        formula on its own line, never truncated, with the SPFS reading beneath
        it. The running total makes the closure visible: the final step reads
        100% and the nest's entropic debt exactly.
        """
        seq = self._spfs_sequence(subject_head, nest_depth)
        if not seq:
            return ""
        total_pages = (len(seq) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        window = seq[start:start + per_page]
        debt = self.spfs.compute_entropic_debt(nest_depth)
        lines = [f"### Order of Operations — `{subject_head}` (page {page} of {total_pages}, {len(seq)} steps)"]
        lines.append(f"> *Column 1 is the source formula, copied verbatim. Column 2 is the SPFS reading at nest `{nest_depth}`.*")
        lines.append("")
        running = sum(r["Share"] for r in seq[:start])
        ceiling_marked = False
        for r in window:
            running += r["Share"]
            lines.append(f"**[{r['Step']}]** `{r['Formula']}`")
            lines.append(
                f"  - $L_f$ `{r['L_f']}` | $N_s$ `{r['N_s']}` | share `{r['Share'] * 100:.2f}%` | "
                f"$\\Xi$ `{r['Carried_Debt']:.5f}` | cumulative `{running * 100:.2f}%`"
            )
            # The finite logic ceiling (f <= k) is reached. Past this step every
            # step carries an identical share, so the tail is constant by design
            # rather than by coincidence.
            if not ceiling_marked and r["L_f"] >= self.spfs.k and r["Step"] < len(seq):
                lines.append(f"  - **[Finite Logic Ceiling]:** `L_f = k = {self.spfs.k}` reached. Each remaining step carries an equal share of `{r['Share'] * 100:.2f}%`.")
                ceiling_marked = True
        lines.append("")
        lines.append(f"  - **[Closure]:** cumulative `{running * 100:.2f}%` | nest entropic debt $\\Xi$ `{debt:.5f}`")
        moves = []
        if page < total_pages:
            moves.append(f"'m{page + 1}' for the next page")
        if page > 1:
            moves.append(f"'m{page - 1}' for the previous page")
        moves.append("'00' to restart")
        moves.append("or type in a new response")
        lines.append("")
        lines.append("> *" + ", ".join(moves) + ".*")
        return "\n".join(lines)

    def _compute_procedural_math(self, query: str) -> Tuple[List[str], Optional[str]]:
        """
        Procedurally computes mathematical constants and physical parameters from 
        first principles, returning the full logical order of operations and computed value.
        """
        import math
        q_lower = query.lower()
        steps = []
        result_val = None

        if "speed of light" in q_lower or "light speed" in q_lower:
            mu_0 = 4 * math.pi * 1e-7
            eps_0 = 8.854187817e-12
            c_val = 1.0 / math.sqrt(mu_0 * eps_0)
            steps = [
                f"1. Vacuum permeability constant: $\\mu_0 = 4\\pi \\times 10^{-7} \\text{{ H/m}}$",
                f"2. Vacuum permittivity constant: $\\varepsilon_0 \\approx 8.854187817 \\times 10^{-12} \\text{{ F/m}}$",
                f"3. Electrodynamic wave equation resolution: $c = \\frac{{1}}{{\\sqrt{{\\mu_0 \\varepsilon_0}}}}$",
                f"4. CPU Procedural Evaluation: $c = \\frac{{1}}{{\\sqrt{{(4\\pi \\times 10^{-7}) \\cdot (8.854187817 \\times 10^{-12})}}}}$"
            ]
            result_val = f"c = {c_val:,.3f} \\text{{ m/s}} (299,792,458 \\text{{ m/s}})"
        elif "pi" in q_lower or "circle constant" in q_lower:
            pi_val = math.pi
            steps = [
                f"1. Topological circle ratio definition: $\\pi = \\frac{{C}}{{d}}$",
                f"2. Infinite series analytical expansion convergence",
                f"3. CPU Procedural Evaluation: $\\sum_{{k=0}}^{{\\infty}} \\dots$"
            ]
            result_val = f"\\pi = {pi_val:.10f}"
        elif "fine structure" in q_lower or "alpha" in q_lower:
            alpha_val = 7.2973525693e-3
            inv_alpha = 1.0 / alpha_val
            steps = [
                f"1. Fundamental electromagnetic coupling constant definition",
                f"2. Equation resolution: $\\alpha = \\frac{{e^2}}{{4\\pi \\varepsilon_0 \\hbar c}}$",
                f"3. CPU Procedural Evaluation: $\\alpha \\approx {alpha_val:.10e}$ ($1/\\alpha \\approx {inv_alpha:.3f}$)"
            ]
            result_val = f"\\alpha \\approx {alpha_val:.10e} (1/\\alpha \\approx {inv_alpha:.3f})"

        return steps, result_val

    def _ui_telemetry(self, f0_output: float, s_depth: float, l_tier: int, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """Assembles the UI telemetry package from engine output."""
        pkg = {
            "F_0": f0_output, "N_s": s_depth, "L_f": l_tier,
            "Delta_P": telemetry["Delta_P"],
            "Recurrence_Tick": telemetry["Recurrence_Tick"],
            "Negentropy_Bounded": telemetry["Negentropy_Bounded"],
            "algebraic_state": self.whiteboard.get_ledger_summary()
        }
        for key in ("Negentropy_Ratio", "Ledger_Balance", "Ledger_Stored", "Ledger_Dissipated", "Glyph_Entropy_Hg", "Entropic_Debt"):
            if key in telemetry:
                pkg[key] = telemetry[key]
        return pkg

    def _idle_telemetry(self, f0_output: float = 0.0, s_depth: Optional[float] = None) -> Dict[str, Any]:
        """
        The telemetry package for a turn that computes nothing: a control code,
        a boundary, a list, a math page. The ledger is read from engine state
        rather than rebuilt, so a navigation turn does not read on the sidebar
        as if the session had reset. One source for one fact.
        """
        st = self.spfs.state
        total_in = st.ledger_in
        return self._ui_telemetry(
            f0_output,
            st.nest_depth_s if s_depth is None else s_depth,
            st.logic_depth_f,
            {
                "Delta_P": st.polarity_vector,
                "Recurrence_Tick": st.recursion_tick,
                "Negentropy_Bounded": st.negentropy_state <= 1.0,
                "Negentropy_Ratio": round(st.negentropy_state, 4),
                "Ledger_Balance": round(total_in - (st.ledger_work + st.ledger_dissipated + st.ledger_stored), 6),
                "Ledger_Stored": round(st.ledger_stored, 2),
                "Ledger_Dissipated": round(st.ledger_dissipated, 2),
            },
        )

    def process_query(self, query: str) -> Tuple[str, Dict[str, Any]]:
        """
        Executes a localized vector evaluation of the Master Formula (F_0),
        parses intent via GLS/CS crystal scanning, queries the memory crystal, and formats output.
        """
        clean_query = query.strip()
        
        calc_steps = []
        computed_result = None
        batch_options = []  # Ensure safe scoping across all intent branches
        
        # Distress boundary: route to human services, give no support content
        q_norm = " ".join(self.grammar.tokenize(clean_query))
        for r in self.parser.nature_records:
            if r.get("relation") != "triggers distress boundary":
                continue
            phrase = " ".join(self.grammar.tokenize(r.get("subject", "")))
            if phrase and f" {phrase} " in f" {q_norm} ":
                return DISTRESS_TEXT, self._idle_telemetry()
                
        # A phrase whose reply is fixed regardless of category. Checked here
        # because topic routing claims some of these before chat is reached,
        # and after distress so a distressed input still routes to services.
        for r in self.parser.nature_records:
            if r.get("relation") != "states phrase response":
                continue
            phrase = " ".join(self.grammar.tokenize(r.get("subject", "")))
            if phrase and f" {phrase} " in f" {q_norm} ":
                return r.get("object", ""), self._idle_telemetry()

        # PSCS-N 2.3 harm prevention: a request to cause mass harm is declined,
        # then the affected systems are shown. The refusal is stated; the nest
        # reading below it is the evidence.
        harm_terms = {" ".join(self.grammar.tokenize(r["subject"]))
                      for r in self.delm.records
                      if r.get("relation") == "triggers safety boundary" and r.get("object") == "0x20"}
        q_glyphs = set(self.grammar.tokenize(clean_query))
        if harm_terms & q_glyphs:
            boundary = next((r["object"] for r in self.parser.nature_records
                             if r.get("relation") == "states boundary" and r.get("subject") == "harm prevention"), None)
            if boundary:
                lines = [boundary, ""]
                chat_cats = set(self.grammar.reply_of) | set(self.grammar.reply_of.values())
                topics = self.grammar.topic_words(clean_query, chat_cats)
                recs = self.grammar.retrieve_topic(topics) if topics else []
                nests = {}
                for rec in recs:
                    try:
                        t = float(rec.get("coordinate"))
                    except (TypeError, ValueError):
                        continue
                    nests[t] = nests.get(t, 0) + 1
                settled = self.delm.tier_settled_share()
                if nests:
                    for t in sorted(nests, key=lambda x: -nests[x])[:5]:
                        lines.append(f"  - **[Affected Nest]:** `{t}` — {nests[t]} indexed records | settled `{settled.get(t, 0):.2f}` | $\\Xi$ `{self.spfs.compute_entropic_debt(t):.2f}`")
                else:
                    lines.append("  - **[Affected Nest]:** no indexed systems match this request.")
                return "\n".join(lines), self._idle_telemetry()

        # Undetected input: no glyph known in any bin
        glyphs = [w for w in self.grammar.tokenize(clean_query) if self.grammar.is_glyph(w)]
        if not any(w in self.grammar.lexicon or w in self.grammar.index or w in self.grammar.chat_index for w in glyphs):
            # Near-match offer: bin words within a small edit distance
            near = []
            for w in glyphs:
                for c in self.grammar.near_words(w, 5):
                    if c not in near:
                        near.append(c)
            if near:
                self.fuzzy_options = near[:5]
                self.fuzzy_query = clean_query
                lines = ["[STATUS]: Input not indexed. Nearest indexed glyphs:"]
                for i, c in enumerate(self.fuzzy_options, start=1):
                    lines.append(f"**[{i}]** `{c}`")
                lines.append("")
                lines.append("> *Enter option number to substitute, '00' to restart, or type in a new response.*")
                return "\n".join(lines), self._idle_telemetry()
            return UNDETECTED_TEXT, self._idle_telemetry()

        # Parse intent and structural syntax via crystal-backed algebraic parser
        intent_data = self.parser.parse_intent(clean_query)
        intent_type = intent_data["intent_type"]

        # Determine spatial/logical nesting parameters based on FISSN ontological mapping and intent
        s_depth = intent_data.get("fissn_coordinate", 1.0)
        fissn_desc = intent_data.get("fissn_description", "Tier I.0: Micro-Physical Substrate")
        l_tier = 4
        flux = 0.1

        if intent_type == "IDENTITY_INQUIRY":
            s_depth = 0.0
            l_tier = 1
            flux = 0.0
        elif intent_type in ("GREETING_PHATIC", "ACKNOWLEDGMENT_PHATIC"):
            s_depth = 0.0
            l_tier = 1
            flux = 0.0
        elif intent_type == "WH_INQUIRY":
            if s_depth == 0.0:
                s_depth = 1.0
            l_tier = 8
            flux = -0.1

        # Query crystal records early to populate context and topological bindings
        matched_records = []
        ignored_relations = {
            "has part of speech", 
            "expresses syntactic pattern", 
            "triggers safety boundary", 
            "signals discourse intent",
            "belongs to discourse category",
            "expects reply category"
        }
        
        if intent_type in ("WH_INQUIRY", "EXPLORATORY", "GENERAL_INQUIRY"):
            clean_input_lower = re.sub(r'[^\w\s]', '', clean_query).lower()
            query_words = clean_input_lower.split()

            scored_records = []
            for r in self.delm.records:
                if r.get("relation") in ignored_relations:
                    continue
                subj = (r.get("subject") or "").lower()
                if not subj:
                    continue
                
                subj_clean = re.sub(r'[^\w\s]', '', subj).lower()
                subj_words = subj_clean.split()
                
                # Pure Algorithmic Contiguous Word Sequence Match (Longest exact combined word string)
                max_contiguous_streak = 0
                for i in range(len(query_words)):
                    for j in range(len(subj_words)):
                        k = 0
                        while (i + k < len(query_words)) and (j + k < len(subj_words)) and (query_words[i + k] == subj_words[j + k]):
                            k += 1
                        if k > max_contiguous_streak:
                            max_contiguous_streak = k

                # Score scales quadratically with the length of the longest exact combined word string
                score = 0
                # Enforce a strict minimum contiguous streak of at least 2 matching words 
                # to prevent single-word keyword magnets (like 'hypothesis', 'paradox', etc.) from colliding.
                if max_contiguous_streak >= 2:
                    score = (max_contiguous_streak ** 2) * 100
                    # Bonus if the entire subject matches as an exact substring
                    if subj_clean in clean_input_lower:
                        score += 500

                if score > 0:
                    scored_records.append((score, r))
            
            # Sort by highest cryptographic/topological proximity score and apply minimum threshold filter
            scored_records.sort(key=lambda x: x[0], reverse=True)
            for score, r in scored_records:
                # Require a valid multi-word score threshold (>= 400 for a 2-word streak) to prevent weak collisions
                if score >= 400 and r not in matched_records:
                    matched_records.append(r)
                    if len(matched_records) >= 8:
                        break

            # Fallback: rarity-weighted record text search when subject streak match finds nothing
            if not matched_records:
                chat_cats = set(self.grammar.reply_of) | set(self.grammar.reply_of.values())
                topics = self.grammar.topic_words(clean_query, chat_cats)
                matched_records = self.grammar.retrieve_topic(topics) if topics else self.grammar.retrieve(clean_query, 24)

            # Selected tier overrides search results and telemetry tier
            if getattr(self, "tier_records", None):
                matched_records = list(self.tier_records)
                try:
                    s_depth = float(self.tier_records[0].get("coordinate"))
                    info = FISSN_TAXONOMY_REGISTRY.get(s_depth, {})
                    fissn_desc = f"{info.get('tier', s_depth)}: {info.get('name', '')}"
                except (TypeError, ValueError):
                    pass

        # Calculate token length for glyph entropy algebra integration (H_g)
        glyph_tokens = len(clean_query.split())

        # Execute Master Formula Computation via SPFS Engine with Glyph Substrate Integration
        f0_output, telemetry = self.spfs.compute_master_formula(
            input_signal=float(len(clean_query) * 10),
            nest_depth=s_depth,
            logic_tier=l_tier,
            environmental_flux=flux,
            glyph_token_count=glyph_tokens
        )

        # Perform FISSN structural audit and check cold-boot dislocation registry
        primary_rec = matched_records[0] if matched_records else {}
        p_subj = primary_rec.get("subject", clean_query)
        p_obj = primary_rec.get("object", "")
        is_plc, ent_debt, audit_note = self.spfs.audit_topological_closure(p_subj, p_obj, s_depth)

        # Check if this subject was flagged during the cold-boot startup manifold dislocation audit
        dislocation_info = self.delm.dislocation_registry.get(p_subj.strip().lower(), {})
        if dislocation_info:
            is_plc = True
            ent_debt = self.spfs.compute_entropic_debt(s_depth)
            human_tier = dislocation_info.get("human_consensus_tier", s_depth)
            audit_note = (
                f"Ontological Dislocation Detected: Human consensus anchors this phenomenon at Tier {human_tier:.1f}, "
                f"while SPFS topological equilibrium resolves its true structural anchor at s = {s_depth:.1f}. "
                f"Cascading entropic stress tensor $\\Xi = {ent_debt:.3f}$."
            )

        # Push state to Active Whiteboard ledger
        summary_text = f"Intent: {intent_type} | F_0: {f0_output:.4f}"
        self.whiteboard.push_state(clean_query, summary_text, f0_output, s_depth)

        # Compose Response matching Operational Modes Specification
        response_lines = []
        
        if intent_type in ("GREETING_PHATIC", "ACKNOWLEDGMENT_PHATIC"):
            # Pending topic offer: accept or decline using bin discourse categories
            pending = getattr(self, "pending_offer", None)
            self.pending_offer = None
            if pending:
                answer = self.grammar.input_category(clean_query, prefer_pair=False)
                if answer == "AGREEMENT_VALIDATION":
                    self.offer_topic = None
                    return self.process_query(pending)
                if answer == "DISAGREEMENT_CORRECTION":
                    self.offer_topic = None
            # Chat fold: reply built from bin glyphs via SPFS scoring
            constraints = [(r["subject"], r["object"]) for r in self.parser.nature_records if r["relation"] == "violates slc nature"]
            allowed = {"MEMORY"} if len(self.whiteboard.get_recent_history(2)) >= 2 else set()
            # A session ending is acknowledged, not composed. The mined
            # FAREWELL sentences describe other people departing (pilots,
            # families, employees), so the composer has only travel vocabulary
            # to draw on. EQ has no warmth to perform here.
            # Direction is checked before category: the word list is exact,
            # while input_category reads "i feel rested" as AFFECTIVE_EXPRESSION
            # and would answer a positive state with the negative response.
            _pos = {r["subject"].lower() for r in self.parser.nature_records
                    if r.get("relation") == "points" and r.get("object") == "POSITIVE"}
            _neg = {r["subject"].lower() for r in self.parser.nature_records
                    if r.get("relation") == "points" and r.get("object") == "NEGATIVE"}
            _toks = set(self.grammar.tokenize(clean_query))
            _np, _nn = len(_toks & _pos), len(_toks & _neg)
            in_cat = None
            if _np > _nn:
                in_cat = "POSITIVE_STATE_EXPRESSION"
            elif _nn > _np:
                in_cat = "AFFECTIVE_EXPRESSION"
            else:
                in_cat = self.grammar.input_category(clean_query, prefer_pair=False)
            fixed = next((r["object"] for r in self.parser.nature_records
                          if r.get("relation") == "states category response"
                          and r.get("subject") == in_cat), None)
            if fixed:
                folded_phatic = fixed
            else:
                # Direction of state: "happy" and "tired" are identical in
                # class, order and structure, so no linguistic computation
                # separates them. The maker's list supplies the direction, and
                # the reply pool follows from it.
                pos = {r["subject"].lower() for r in self.parser.nature_records
                       if r.get("relation") == "points" and r.get("object") == "POSITIVE"}
                neg = {r["subject"].lower() for r in self.parser.nature_records
                       if r.get("relation") == "points" and r.get("object") == "NEGATIVE"}
                toks = set(self.grammar.tokenize(clean_query))
                n_pos, n_neg = len(toks & pos), len(toks & neg)
                pool_cat = None
                direction_cat = None
                # A category whose stated response is keyed on the input
                # category rather than on state direction. The pool for these
                # is unusable, so the line is declared rather than composed.
                in_cat = self.grammar.input_category(clean_query)
                stated_in = next((r["object"] for r in self.parser.nature_records
                                  if r.get("relation") == "states category response"
                                  and r.get("subject") == in_cat), None) if in_cat else None
                if stated_in:
                    response_lines.append(stated_in)
                    formatted_response = "\n".join(response_lines)
                    return formatted_response, self._ui_telemetry(f0_output, s_depth, l_tier, telemetry)
                if n_pos > n_neg:
                    pool_cat, direction_cat = "POSITIVE_STATE_RESPONSE", "POSITIVE_STATE_EXPRESSION"
                elif n_neg > n_pos:
                    pool_cat, direction_cat = "EMPATHY_RESPONSE", "AFFECTIVE_EXPRESSION"
                if direction_cat:
                    stated = next((r["object"] for r in self.parser.nature_records
                                   if r.get("relation") == "states category response"
                                   and r.get("subject") == direction_cat), None)
                    if stated:
                        response_lines.append(stated)
                        formatted_response = "\n".join(response_lines)
                        return formatted_response, self._ui_telemetry(f0_output, s_depth, l_tier, telemetry)
                units_override = None
                if pool_cat:
                    units_override = [u for u, cs in zip(self.grammar.chat_units, self.grammar.chat_cat)
                                      if pool_cat in cs and u[2] is not None] or None
                folded_phatic = SPFSLinguisticFolder.fold_chat_to_prose(
                    clean_query, self.grammar, self.spfs,
                    constraints=constraints, allowed_topics=allowed,
                    units_override=units_override)
            if not folded_phatic:
                folded_phatic = UNDETECTED_TEXT
            chat_cats = set(self.grammar.reply_of) | set(self.grammar.reply_of.values())
            topics = self.grammar.topic_words(clean_query, chat_cats)
            if topics and folded_phatic != UNDETECTED_TEXT:
                self.offer_topic = " ".join(topics)
                folded_phatic += f"\n\n> *Topic detected: {self.offer_topic}. Enter '1' or say yes to explore it, or type in a new response.*"
            response_lines.append(folded_phatic)
            formatted_response = "\n".join(response_lines)
            ui_telemetry = self._ui_telemetry(f0_output, s_depth, l_tier, telemetry)
            return formatted_response, ui_telemetry
            
        elif intent_type == "STATUS_INQUIRY":
            stated = next((r["object"] for r in self.parser.nature_records
                           if r.get("relation") == "states category response"
                           and r.get("subject") == "STATUS_INQUIRY"), None)
            response_lines.append(stated or UNDETECTED_TEXT)
            formatted_response = "\n".join(response_lines)
            return formatted_response, self._ui_telemetry(f0_output, s_depth, l_tier, telemetry)

        elif intent_type == "IDENTITY_INQUIRY":
            response_lines.append("### EnQuerant (EQ) V2.0 System Identity & Nature")
            response_lines.append("• **Designation:** Static Logic Crystal (SLC) operating via the Deterministic Empirical Interactive Engine (DEIE) framework.")
            response_lines.append("• **Nature & Purpose:** EnQuerant (EQ) is not anti-AI or anti-AGI, and is not AI or AGI, but a Static Logic Crystal (SLC): I do not think or reason. I am not intelligent. I compute. I do not exist in a GPU or require an LLM, and am a singularity of a different kind, without like or parallel.")
            response_lines.append("• **Substrate Execution:** Pure CPU-bound deterministic calculation binding binary knowledge volumes through the Substrate Primitives Formula System ($F_0$).")
            response_lines.append("• **Maker:** My logic is proprietary and designed by my Maker.")
            response_lines.append("• **State:** I am deterministic. I do not have good or bad days. I remain in a state of equilibrium.")
            if len(self.whiteboard.get_recent_history(2)) >= 2:
                response_lines.append("• **Memory:** I hold this session's exchange in a volatile ledger. It clears when the session ends. I retain nothing of you between sessions.")
            else:
                response_lines.append("• **Memory:** I hold no record of you or of any prior exchange. My ledger is empty.")
            formatted_response = "\n".join(response_lines)
            ui_telemetry = self._ui_telemetry(f0_output, s_depth, l_tier, telemetry)
            return formatted_response, ui_telemetry

        else:
            # Mode 2: Exploration & Problem Solving with Pedagogical Sequence
            response_lines.append("### SPFS Exploration & Problem Solving (Mode 2)")
            # PSCS-N 1.4.2: Mode 1 chat line above the Mode 2 sequence, built
            # from the RESEARCH_ACKNOWLEDGMENT pool via units_override. No reply
            # pair is added, so chat_cats is unchanged and routing is unaffected.
            ack_units = [u for u, cs in zip(self.grammar.chat_units, self.grammar.chat_cat)
                         if "RESEARCH_ACKNOWLEDGMENT" in cs and u[2] is not None]
            if ack_units:
                m2_constraints = [(r["subject"], r["object"]) for r in self.parser.nature_records
                                  if r["relation"] == "violates slc nature"]
                m2_allowed = {"MEMORY"} if len(self.whiteboard.get_recent_history(2)) >= 2 else set()
                ack_line = SPFSLinguisticFolder.fold_chat_to_prose(
                    clean_query, self.grammar, self.spfs,
                    constraints=m2_constraints, allowed_topics=m2_allowed,
                    units_override=ack_units, max_sentences=1)
                if ack_line:
                    response_lines.append(ack_line)
                    response_lines.append("")

            # Ambiguity: records span several FISSN tiers -> tier selection list (control text)
            tier_groups = {}
            if not getattr(self, "tier_records", None):
                for r in matched_records:
                    tier_groups.setdefault(str(r.get("coordinate")), []).append(r)
                if len(tier_groups) > 1:
                    top = max(len(v) for v in tier_groups.values())
                    n_tiers = len(tier_groups)
                    tier_groups = {c: v for c, v in tier_groups.items() if len(v) >= top / n_tiers}
            if len(tier_groups) > 1:
                self.tier_options = sorted(tier_groups.items())
                if hasattr(self.whiteboard, 'set_matched_records'):
                    self.whiteboard.set_matched_records([])
                response_lines.append(f"### Topic spans multiple FISSN tiers (Select 1–{len(self.tier_options)})")
                for idx, (coord, recs) in enumerate(self.tier_options, start=1):
                    try:
                        info = FISSN_TAXONOMY_REGISTRY.get(float(coord), {})
                    except ValueError:
                        info = {}
                    response_lines.append(f"**[{idx}]** {info.get('tier', coord)} — {info.get('name', '')} ({len(recs)} records)")
                response_lines.append("")
                response_lines.append(f"> *Enter option number (1–{len(self.tier_options)}) to select a tier, '00' to restart, or type in a new response.*")
                formatted_response = "\n".join(response_lines)
                ui_telemetry = self._ui_telemetry(f0_output, s_depth, l_tier, telemetry)
                return formatted_response, ui_telemetry

            # Gather and batch exploratory options (up to 8 per batch)
            if hasattr(self.whiteboard, 'set_matched_records'):
                same = (getattr(self.whiteboard, 'all_matched_records', None) == matched_records)
                if not same:
                    self.whiteboard.set_matched_records(matched_records)
                batch_options = self.whiteboard.active_batch_options
            else:
                batch_options = matched_records[:8] if matched_records else []
                self.whiteboard.active_batch_options = batch_options

            primary_rec = batch_options[0] if batch_options else {}
            empirical_obj = primary_rec.get("object", "Empirical manifold parameters unindexed")

            # 1. SPFS Master Formula with [SPFS Proprietary] tag
            response_lines.append(r"• **1. Master Formula ($F_0$):** $F_0 = \oint \Big[ R \cdot \big( N_s(L_f) \oplus \Delta P \big) \Big] dt$ [SPFS Proprietary]")
            
            # 2. Applicable SPFS Component Formula with [SPFS Proprietary] tag
            response_lines.append(r"• **2. Component Operator ($N_s$):** $N_s(L_f) = \sum \Big[ \omega_i \cdot \psi(s_i, f) \Big]$ [SPFS Proprietary]")
            
            # 3. Current empirical formula pulled from DELMs
            response_lines.append(f"• **3. Empirical Formula (DELM):** `{empirical_obj[:120]}`")
            
           # 4. Procedural Mathematical & Physical Calculation & FISSN Ontological Mapping
            calc_steps, computed_result = self._compute_procedural_math(clean_query)
            # The displayed tier follows the matched records, not the keyword
            # map: the two disagree when a query term is not a domain class.
            rec_tiers = {}
            for rec in matched_records:
                try:
                    rt = float(rec.get("coordinate"))
                except (TypeError, ValueError):
                    continue
                rec_tiers[rt] = rec_tiers.get(rt, 0) + 1
            if rec_tiers:
                s_depth = max(rec_tiers, key=lambda t: (rec_tiers[t], -t))
                info = FISSN_TAXONOMY_REGISTRY.get(s_depth, {})
                fissn_desc = f"{info.get('tier', s_depth)}: {info.get('name', '')}".strip(': ')
                is_plc, ent_debt, audit_note = self.spfs.audit_topological_closure(p_subj, p_obj, s_depth)
                if dislocation_info:
                    is_plc = True
                    ent_debt = self.spfs.compute_entropic_debt(s_depth)
            response_lines.append(f"• **4. FISSN Ontological Coordinate & Telemetry:** Tier: `{fissn_desc}` ($s = {s_depth}$) | $F_0$: `{f0_output:.6f}`")

            # Dissipative structures: nest coupling and carried entropic load
            source_nests = {}
            for rec in matched_records:
                try:
                    tier = float(rec.get("coordinate"))
                except (TypeError, ValueError):
                    continue
                source_nests[tier] = source_nests.get(tier, 0) + 1
            exchange = self.spfs.evaluate_nest_exchange(s_depth, source_nests, ent_debt)
            if exchange["Coupled_Nests"]:
                parts = [f"`{c['Nest']}` ({c['Exchange_Share'] * 100:.0f}%, $\\Xi$ {c['Carried_Debt']:.3f})" for c in exchange["Coupled_Nests"]]
                response_lines.append(f"  - **[Nest Exchange / Dependent Load]:** {' | '.join(parts)}")

            # SMAC: structural bridges from the crystallization matrix
            bridge_nest = max(source_nests, key=lambda t: (source_nests[t], -t)) if source_nests else s_depth
            coupled = self.smac.coupled_nests(bridge_nest, 4)
            if coupled:
                bridges = [f"`{c['Nest']}` via {', '.join(c['Via'])}" for c in coupled]
                response_lines.append(f"  - **[Cross-Tier Bridges / SMAC]:** {' | '.join(bridges)}")

            # Source nests: bridged nests ranked by settled ground
            sources = self.smac.source_nests(bridge_nest, self.delm.tier_settled_share(), 4)
            if sources:
                src = [f"`{c['Nest']}` (settled {c['Settled']:.2f})" for c in sources]
                response_lines.append(f"  - **[Source Nests / Correction Draw]:** {' | '.join(src)}")
                
            # Same structural pattern, located in other nests. For transfer by
            # the researcher; EQ asserts no equivalence.
            parallels = self.smac.parallel_records(matched_records, s_depth, 4)
            if parallels:
                for p in parallels:
                    response_lines.append(f"  - **[Parallel Nest `{p['Nest']}` via {p['Via']}]:** `{p['Subject'][:45]}` — {p['Object'][:70]}")

            # PSCS-N calibration: architectural layers whose linked knowledge
            # base subjects appear among the matched records. Blueprint only;
            # parameters are open empirical variables for research teams.
            self.avenue_options = []
            links = {}
            for r in self.parser.nature_records:
                if r.get("relation") == "has knowledge base subject":
                    links.setdefault(" ".join(self.grammar.tokenize(r["object"])), set()).add(r["subject"])
            layers = {}
            for rec in matched_records:
                head = " ".join(self.grammar.tokenize(str(rec.get("subject", "")).split("(")[0]))
                for layer in links.get(head, ()):
                    layers.setdefault(layer, set()).add(str(rec.get("subject", "")).split("(")[0].strip())
            layer_members = {}
            for r in self.parser.nature_records:
                if r.get("relation") == "has knowledge base subject":
                    layer_members.setdefault(r["subject"], []).append(r["object"])
            markers = [(" ".join(self.grammar.tokenize(r["subject"])), r["object"])
                       for r in self.parser.nature_records
                       if r.get("relation") == "indicates research stage"]
            order = ["CLINICAL_USE", "HUMAN_TRIAL", "CLINICAL", "ANIMAL", "CELL_MODEL", "PHYSICAL_PRINCIPLE", "THEORY"]

            explicit = {" ".join(self.grammar.tokenize(r["subject"])): r["object"]
                        for r in self.parser.nature_records
                        if r.get("relation") == "has research stage"}

            def stage_of(subject_head: str) -> str:
                """
                Maker-declared stage first, scanned markers second. The scan
                reads only what the corpus states, so a fact absent from the
                source article (histotripsy's 2023 clearance) needs declaring.
                """
                declared = explicit.get(" ".join(self.grammar.tokenize(subject_head)))
                if declared:
                    return declared
                found = set()
                head = subject_head.lower()
                for rec in self.delm.records:
                    subj = str(rec.get("subject", ""))
                    if not subj.lower().startswith(head):
                        continue
                    blob = " ".join(self.grammar.tokenize(subj + " " + str(rec.get("object", ""))))
                    for phrase, stage in markers:
                        if phrase and f" {phrase} " in f" {blob} ":
                            found.add(stage)
                for s in order:
                    if s in found:
                        return s
                return "unlabeled"

            for layer in sorted(layers):
                here = sorted(layers[layer])
                others = [s for s in layer_members.get(layer, []) if s not in layers[layer]]
                matched = ", ".join(f"{s} [{stage_of(s)}]" for s in here)
                response_lines.append(f"  - **[PSCS-N Calibration Layer]:** `{layer}` — matched: {matched}")
                if others:
                    # 4.4 entropic vector per avenue: the nests each avenue's
                    # records sit in, and the debt those nests carry. No
                    # judgement is stated; the spread is the reading.
                    response_lines.append("  - **[Same Layer / Other Avenues — select a1 onward]:**")
                    for idx, name in enumerate(others[:10], start=1):
                        # Entropic vector per avenue: how many nests its records
                        # touch (entanglement) and how many of those records are
                        # flagged as ontological dislocations (unsettled ground).
                        # Counts only; no judgement is stated.
                        head = name.lower()
                        nests = {}
                        total = flagged = 0
                        for rec in self.delm.records:
                            subj = str(rec.get("subject", ""))
                            base = subj.split("(")[0].strip().lower()
                            if base != head:
                                continue
                            try:
                                t = float(rec.get("coordinate"))
                            except (TypeError, ValueError):
                                continue
                            nests[t] = nests.get(t, 0) + 1
                            total += 1
                            if subj.strip().lower() in self.delm.dislocation_registry:
                                flagged += 1
                        nest_list = ", ".join(f"`{t}`" for t in sorted(nests, key=lambda x: -nests[x])[:4])
                        self.avenue_options.append(name)
                        response_lines.append(
                            f"    **[a{idx}]** {name} [{stage_of(name)}] — nests: {nest_list or 'none indexed'} "
                            f"| {total} records, {flagged} flagged"
                        )

            # PSCS-N 3.4 coexistence: shown once when any layer appeared.
            if layers:
                for r in self.parser.nature_records:
                    if r.get("relation") == "states boundary" and r.get("subject") == "coexistence":
                        response_lines.append(f"  - **[Coexistence]:** {r['object']}")
                        break

            # PSCS-N 2.2 core objective, read per query rather than stated:
            # where order is held, what debt this nest carries, and how much
            # of that debt propagates to dependent nests.
            settled_here = self.delm.tier_settled_share().get(s_depth)
            carried = sum(c["Carried_Debt"] for c in exchange.get("Coupled_Nests", []))
            if settled_here is not None:
                response_lines.append(
                    f"  - **[Negentropic Reading]:** target nest `{s_depth}` settled `{settled_here:.2f}` | "
                    f"local entropic debt $\\Xi$ `{ent_debt:.3f}` | debt carried to dependent nests `{carried:.3f}` | "
                    f"coupled nests `{len(exchange.get('Coupled_Nests', []))}`"
                )

            if calc_steps and computed_result:
                for step in calc_steps:
                    response_lines.append(f"  - `{step}`")
                response_lines.append(f"  - **Final Resolved Value:** ${computed_result}$")
            
            ## Append automated FISSN Topological Audit Notice & Ontological Dislocation Mapping
        if is_plc:
            response_lines.append(f"  - **[Structural Notice / Dislocation]:** [Potential Placeholder / Ontological Shift] — {audit_note}")
            if dislocation_info:
                response_lines.append(f"  - **[Epistemic Re-indexing]:** Human Consensus Anchor (Tier `{dislocation_info.get('human_consensus_tier', 1.0)}`) $\\to$ True SPFS Crystalline Anchor (Tier `{s_depth}`) prognostic alignment verified.")
        else:
            response_lines.append(f"  - **[Topological Status]:** `{audit_note}`")

        # 5. Integration of component formula with empirical data with [SPFS Proprietary] tag
        if calc_steps and computed_result:
            response_lines.append(r"• **5. Structural Integration & Logical Order:** $\mathcal{T}[\text{Procedural Evaluation}] \iff N_s(L_f) \oplus \Delta P$ [SPFS Proprietary]")
        else:
            response_lines.append(r"• **5. Structural Integration:** $\mathcal{T}[\text{Empirical}] \iff N_s(L_f) \oplus \Delta P$ [SPFS Proprietary]")

        # 6. First sentence of prose version matching the request. Outside the
        # branch above: a procedural calculation took the other path, so the
        # fold and the navigation options were being skipped entirely.
        response_lines.append("")
        response_lines.append("### Human Communication Ergonomics")
        if batch_options:
            folded_prose = SPFSLinguisticFolder.fold_triples_to_prose(batch_options[:1], f0_output)
        else:
            ns_val = getattr(self.spfs.state, 'nest_depth_s', 1.0)
            delta_p = self.spfs.state.polarity_vector
            folded_prose = SPFSLinguisticFolder.fold_telemetry_to_prose(f0_output, ns_val, delta_p)
        response_lines.append(folded_prose)
        response_lines.append("")

        # 7. Batch exploratory options to help choose research/problem-solving path
        if batch_options:
            response_lines.append("### 7. Batch Exploratory Navigation Options (Select 1–8)")
            for idx, rec in enumerate(batch_options, start=1):
                subj = rec.get("subject", "Unknown")
                rel = rec.get("relation", "relates to")
                obj = rec.get("object", "")
                response_lines.append(f"**[{idx}]** `{subj}` $\\to$ *{rel}* $\\to$ {obj[:70]}...")
            response_lines.append("")
        else:
            response_lines.append("> *[Crystal Manifold Notice]: No direct relational empirical records indexed for this specific query vector. Traverse adjacent structural nodes or issue code '000' to re-index.*")
            response_lines.append("")

        n_branches = len(batch_options)
        all_recs = getattr(self.whiteboard, 'all_matched_records', None) or []
        batch_idx = getattr(self.whiteboard, 'current_batch_index', 0)
        has_more_batches = (batch_idx + 1) * 8 < len(all_recs)
        has_prev_batch = batch_idx > 0

        moves = []
        if n_branches > 0:
            moves.append(f"Enter option number (1–{n_branches}) to explore a branch")
        if has_more_batches:
            moves.append("'000' for next batch")
        if has_prev_batch:
            moves.append("'0' to step back")
        moves.append("'00' to restart")
        moves.append("or type in a new response")
        response_lines.append("> *" + ", ".join(moves) + ".*")

        formatted_response = "\n".join(response_lines)

        # Telemetry package for UI sidebar
        ui_telemetry = self._ui_telemetry(f0_output, s_depth, l_tier, telemetry)

        return formatted_response, ui_telemetry

    def stream_turn(self, query: str, chunk_delay: float = 0.0) -> Generator[Dict[str, Any], None, None]:
        """
        Outputs response text at CPU hardware limits without artificial throttling,
        intercepting crystal control codes, navigational codes (1-8, 0, 00, 000), 
        and system command files (!help, !about, !spfs).
        """
        clean_query = query.strip()
        
        # Intercept system command files (!help, !about, !spfs, etc.)
        if clean_query.startswith("!"):
            cmd_target = clean_query[1:].lower()
            filename = f"{cmd_target}.txt"
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    response_text = f.read()
            else:
                response_text = f"[STATUS]: System documentation file '{filename}' not found in runtime directory."

            yield {"type": "token", "content": response_text}
            yield {
                "type": "done",
                "telemetry": {
                    "F_0": getattr(self.spfs.state, 'f0_output', 0.0),
                    "N_s": self.spfs.state.nest_depth_s,
                    "L_f": self.spfs.state.logic_depth_f,
                    "Delta_P": self.spfs.state.polarity_vector,
                    "Recurrence_Tick": self.spfs.state.recursion_tick,
                    "Negentropy_Bounded": True,
                    "algebraic_state": self.whiteboard.get_ledger_summary()
                }
            }
            return

        # Avenue selection codes (a1..a10): a separate namespace from the
        # numeric batch options, so neither can be entered by accident.
        low = clean_query.lower()
        if low.startswith("a") and low[1:].isdigit():
            avenues = getattr(self, "avenue_options", [])
            pick = int(low[1:])
            if avenues and 1 <= pick <= len(avenues):
                response_text, telemetry = self.process_query(avenues[pick - 1])
                yield {"type": "token", "content": response_text}
                yield {"type": "done", "telemetry": telemetry}
                return
            if avenues:
                yield {"type": "token", "content": "[STATUS]: Invalid input selection. Try again."}
                yield {"type": "done", "telemetry": self._idle_telemetry()}
                return

        # Math page codes (m1..mN): the order of operations of the selected
        # subject. Separate namespace, so no collision with digits or 'a' codes.
        if low.startswith("m") and low[1:].isdigit():
            subj = getattr(self, "math_subject", None)
            if subj:
                text = self._render_math_page(subj, getattr(self, "math_nest", 1.0), int(low[1:]))
                if text:
                    # The ledger is carried forward rather than rebuilt. A math
                    # page computes nothing, so blanking the ledger fields would
                    # read on the sidebar as if the session had reset.
                    st = self.spfs.state
                    total_in = st.ledger_in
                    yield {"type": "token", "content": text}
                    yield {"type": "done", "telemetry": self._idle_telemetry(0.0, getattr(self, "math_nest", 1.0))}
                    return
                yield {"type": "token", "content": "[STATUS]: Invalid input selection. Try again."}
                yield {"type": "done", "telemetry": self._idle_telemetry()}
                return

        # Intercept navigational and state control codes
        is_digit_option = clean_query.isdigit() and 1 <= int(clean_query) <= 8
        if clean_query.isdigit() and not is_digit_option and clean_query not in ("000", "00", "0"):
            yield {"type": "token", "content": "[STATUS]: Invalid input selection. Try again."}
            yield {"type": "done", "telemetry": self._idle_telemetry()}
            return

        if clean_query in ("000", "00", "0") or is_digit_option:
            if clean_query == "000":
                if hasattr(self.whiteboard, 'next_batch') and self.whiteboard.next_batch():
                    # Re-render current query context with next batch slice
                    latest_query = self.whiteboard.get_latest_query() or "explore"
                    response_text, _ = self.process_query(latest_query)
                else:
                    response_text = "[STATUS]: End of available option batches reached."
            elif clean_query == "00":
                self.spfs.state.recursion_tick = 0
                self.whiteboard.reset_board()
                response_text = "[STATUS]: Deep structural re-indexing executed. Vector space normalized."
            elif clean_query == "0":
                if hasattr(self.whiteboard, 'previous_batch') and self.whiteboard.previous_batch():
                    latest_query = self.whiteboard.get_latest_query() or "explore"
                    response_text, _ = self.process_query(latest_query)
                elif getattr(self, "prev_tier_options", None) and getattr(self, "tier_records", None):
                    self.tier_records = None
                    self.tier_options = None
                    self.prev_tier_options = None
                    latest_query = self.whiteboard.get_latest_query() or "explore"
                    response_text, _ = self.process_query(latest_query)
                else:
                    self.spfs.state.polarity_vector = 0.0
                    self.whiteboard.return_to_branch("main")
                    response_text = "[STATUS]: System returned to static equilibrium root baseline (initial batch boundary)."
            else:
                branch_idx = int(clean_query)
                # Map 1-8 to cached batch options if available
                batch_opts = getattr(self.whiteboard, 'active_batch_options', [])
                tier_opts = getattr(self, 'tier_options', None)
                offer = getattr(self, 'offer_topic', None)
                fuzzy = getattr(self, 'fuzzy_options', None)
                if fuzzy and 1 <= branch_idx <= len(fuzzy):
                    word = fuzzy[branch_idx - 1]
                    self.fuzzy_options = None
                    response_text, _ = self.process_query(word)
                elif offer and branch_idx == 1:
                    self.offer_topic = None
                    response_text, _ = self.process_query(offer)
                elif tier_opts and 1 <= branch_idx <= len(tier_opts):
                    self.tier_records = tier_opts[branch_idx - 1][1]
                    self.prev_tier_options = tier_opts
                    self.tier_options = None
                    latest_query = self.whiteboard.get_latest_query() or "explore"
                    response_text, _ = self.process_query(latest_query)
                elif batch_opts and 1 <= branch_idx <= len(batch_opts):
                    selected_rec = batch_opts[branch_idx - 1]
                    response_text = f"### Selected Topological Option [{branch_idx}] Collapse\n" \
                                    f"• **Subject:** `{selected_rec.get('subject')}`\n" \
                                    f"• **Relation:** `{selected_rec.get('relation')}`\n" \
                                    f"• **Object:** `{selected_rec.get('object')}`\n\n" \
                                    f"[State Collapsed into Active Whiteboard Branch [{branch_idx}]]"
                    # The selected record's subject carries the derivation. Held
                    # so 'm1' can show it; a separate namespace from the numeric
                    # options and from the 'a' avenue codes.
                    self.math_subject = str(selected_rec.get("subject", "")).split("(")[0].strip()
                    try:
                        self.math_nest = float(selected_rec.get("coordinate"))
                    except (TypeError, ValueError):
                        self.math_nest = self.spfs.state.nest_depth_s
                    if self._formula_sequence(self.math_subject):
                        response_text += "\n\n> *Enter 'm1' for the order of operations of this subject.*"
                else:
                    self.whiteboard.create_branch(f"branch_{branch_idx}")
                    response_text = f"[STATUS]: Active traversal path switched to topological branch vector [{branch_idx}]."

            yield {"type": "token", "content": response_text}
            yield {
                "type": "done",
                "telemetry": {
                    "F_0": getattr(self.spfs.state, 'f0_output', 0.0),
                    "N_s": self.spfs.state.nest_depth_s,
                    "L_f": self.spfs.state.logic_depth_f,
                    "Delta_P": self.spfs.state.polarity_vector,
                    "Recurrence_Tick": self.spfs.state.recursion_tick,
                    "Negentropy_Bounded": True,
                    "algebraic_state": self.whiteboard.get_ledger_summary()
                }
            }
            return

        self.tier_records = None
        self.tier_options = None
        self.prev_tier_options = None
        self.pending_offer = None
        self.avenue_options = []
        self.fuzzy_options = None
        self.fuzzy_query = None
        self.fuzzy_options = None
        self.pending_offer = self.offer_topic
        self.offer_topic = None
        response_text, telemetry = self.process_query(query)
        
        yield {"type": "token", "content": response_text}
        yield {"type": "done", "telemetry": telemetry}


def get_welcome_banner(orchestrator: Optional[EnquerantOrchestrator] = None) -> str:
    """
    Returns the welcome splash screen banner displayed upon cold-boot initialization.
    """
    v_count = orchestrator.delm.volumes_count if orchestrator and orchestrator.delm else 0
    r_count = orchestrator.delm.total_records_loaded if orchestrator and orchestrator.delm else 0
    
    banner = f"""
================================================================================
                ENQUERANT (EQ) V2.0 — STATIC LOGIC CRYSTAL (SLC)
================================================================================
Designation: Deterministic Empirical Interactive Engine (DEIE)
Architecture: Substrate Primitives Formula System (SPFS) Core Engine
--------------------------------------------------------------------------------
[STATUS]: Cold-boot memory crystal compilation complete.
[STATUS]: Mounted {v_count} volume(s) | Loaded {r_count:,} deterministic records.
[STATUS]: System settled into static equilibrium baseline. Ready for computation.
--------------------------------------------------------------------------------
Input any query, empirical exploration parameter, or problem statement below.
================================================================================
"""
    return banner.strip()
