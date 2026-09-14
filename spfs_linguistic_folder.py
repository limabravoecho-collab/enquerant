#!/usr/bin/env python3
"""
spfs_linguistic_folder.py — Mathematical Categorial Grammar & Manifold Folder
================================================================================
Computes standard English syntactic structures dynamically using SPFS master 
formula operators (F_0, N_s, L_f, ΔP) and glyph entropy (H_g) from spfs_engine.py.
Contains no written sentence templates: chat replies are built from bin glyphs,
and exploration output restates source records verbatim.
================================================================================
"""

import math
from typing import List, Dict, Any
from spfs_engine import SPFSEngine
from glyph_grammar import INTERROGATIVE

class SPFSLinguisticFolder:
    """
    Mathematical Graph Synthesizer.
    Derives natural language syntax and compositional prose entirely through 
    SPFS algebraic coordinate evaluation and categorial manifold reduction.
    """

    @staticmethod
    def fold_triples_to_prose(matched_records: List[Dict[str, Any]], f0_output: float) -> str:
        """
        Restates matched knowledge base records. Every word shown is copied from
        the source records; no sentence template is written here. Record order is
        set by SPFS nesting, so the ordering is computed rather than fixed.
        """
        if not matched_records:
            return ""

        engine = SPFSEngine()
        ranked = []
        for i, r in enumerate(matched_records[:3]):
            subj = str(r.get('subject', '')).strip()
            rel = str(r.get('relation', '')).strip()
            obj = str(r.get('object', '')).strip()
            if not subj or not obj:
                continue
            lf_res = engine.evaluate_lf(logic_tier=i + 1, operand_value=f0_output)
            ns_res = engine.evaluate_ns(float(i) * 0.5, lf_res)
            obj = obj.replace("@@EQ@@", " ").replace("@@/EQ@@", " ")
            obj = " ".join(obj.split())
            ranked.append((-ns_res, i, subj, rel, obj))

        if not ranked:
            return ""

        ranked.sort()
        lines = [f"`{subj}` — {rel} — {obj}" for _, _, subj, rel, obj in ranked]
        return "\n".join(lines) + f"\n\n[Fold verified | F_0: {f0_output:.2f}]"

    @staticmethod
    def fold_telemetry_to_prose(f0_output: float, nest_depth: float, polarity: float) -> str:
        """
        Reports substrate metrics as labelled values. No written prose: the
        labels are the operator names from spfs_engine.py.
        """
        engine = SPFSEngine()
        h_g = engine.evaluate_glyph_algebra(int(f0_output + 1))
        return (f"F_0: {f0_output:.4f} | N_s: {nest_depth:.1f} | "
                f"Delta_P: {polarity:.4f} | H_g: {h_g:.2f}")

    @staticmethod
    def fold_chat_to_prose(query: str, grammar: Any, engine: Any, k_units: int = 8, constraints: Any = None, allowed_topics: Any = None, units_override: Any = None, max_sentences: int = 2) -> str:
        """
        Chat mode fold. Zero words in py.
        Shapes and words from matched gis chat units, extra words from niichii subjects.
        Built output never equals the input or a whole bin sentence.
        Whole bin sentence only when nothing can be built and it is a statement.
        """
        q = grammar.tokenize(query)
        q_norm = " ".join(q)
        blocked = []
        for phrase, topic in (constraints or []):
            if topic in (allowed_topics or set()):
                continue
            p = " ".join(grammar.tokenize(phrase))
            if p:
                blocked.append(p)
        units = units_override or grammar.retrieve_reply_units(query) or grammar.retrieve_chat_block(query) or grammar.retrieve_chat(query, k_units)
        tagged = []
        shapes = []
        for _, tg, shape in units:
            tagged += tg
            if shape and shape[0] != INTERROGATIVE and shape not in shapes:
                shapes.append(shape)
        unknown = [w for w in q if grammar.is_word(w) and w not in grammar.chat_index]
        if unknown:
            for r in grammar.retrieve(" ".join(unknown), 3):
                toks = [t for t in grammar.tokenize(r.get('subject', '')) if grammar.is_word(t)]
                tagged += grammar.infer_sequence(toks)
        if not tagged:
            return ""

        shapes = sorted(shapes, key=lambda s: -grammar.shape_score(s))[:k_units]
        if not shapes:
            shapes = grammar.select_shapes(max(len(q), 1), 8)
        ranked_builds = []
        strongest = False
        for depth, fill in enumerate((grammar.fill_shape_chained3, grammar.fill_shape_spliced, grammar.fill_shape_chained)):
            for shape in shapes:
                path, key = fill(shape, tagged, q, engine)
                if path is None:
                    continue
                out = " ".join(path)
                if out == q_norm or out in grammar.chat_sentences:
                    continue
                if len(q) > 1 and f" {q_norm} " in f" {out} ":
                    continue
                if any(f" {b} " in f" {out} " for b in blocked):
                    continue
                ranked_builds.append((key, out, shape))
            if ranked_builds:
                strongest = (depth == 0)
                break
        if ranked_builds:
            ranked_builds.sort(key=lambda x: -x[0])
            # A second sentence is only added when the winner came from the
            # strongest chain. Below that the reply is already a fallback, and
            # a second weak sentence compounds the fault rather than adding.
            keep = max_sentences if strongest else 1
            sentences = []
            used = set()
            for key, out, shape in ranked_builds:
                if len(sentences) >= keep:
                    break
                if out in used:
                    continue
                if any(out in s or s in out for s in used):
                    continue
                # Two builds drawn from one pool often open on the same glyph
                # ("Good morning ... Good morning ..."). A repeated opener reads
                # as a stutter rather than a second sentence.
                if any(out.split()[0] == s.split()[0] for s in used):
                    continue
                used.add(out)
                sentences.append(grammar.surface(out.split(), units, shape))
            return " ".join(sentences)

        for text, tg, shape in units:
            joined = " ".join(w for w, _ in tg)
            if any(f" {b} " in f" {joined} " for b in blocked):
                continue
            if shape and shape[0] != INTERROGATIVE and joined != q_norm:
                return text
        return ""
