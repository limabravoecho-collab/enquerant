#!/usr/bin/env python3
"""
cs_algebraic_parser.py — Glyph Logic System (GLS) & Algebraic Communication System (CS) Engine
================================================================================
Implements deterministic parsing and algebraic transformation for incoming Seeker text:
- Fully dynamic crystal lexicon scanning via GIS/DELM binaries for all token and POS lookups.
- Zero hardcoded fallback lists; all linguistic semantics derive from the crystal manifold.
- Discourse intent mapping (Status, Identity, Wh-Inquiry, Safety/Distress).
- Algebraic translation operators (T: Lambda_A -> Lambda_B).
================================================================================
"""

import os
import glob
import re
from typing import Dict, List, Tuple, Any, Optional, Set
from crystal_loader import CrystalLoader


class CSApAlgebraicParser:
    """
    Deterministic communication and glyph parsing engine utilizing raw crystal manifold scans.
    """

    def __init__(self, crystal_loader: Optional[CrystalLoader] = None):
        # Bind to the central crystal memory manifold (DELMs & gis_english)
        self.delm = crystal_loader if crystal_loader else CrystalLoader()

        # SLC nature records from maker-written files (slc_nature_*.tsv), same record shape as bins
        self.nature_records = []
        base = os.path.dirname(os.path.abspath(__file__))
        for path in sorted(glob.glob(os.path.join(base, "slc_nature_*.tsv"))
                           + glob.glob(os.path.join(base, "pscs_n_*.tsv"))
                           + glob.glob(os.path.join(base, "structural_patterns_*.tsv"))
                           + glob.glob(os.path.join(base, "query_filler_*.tsv"))
                           + glob.glob(os.path.join(base, "state_direction_*.tsv"))):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) == 3 and all(parts):
                        self.nature_records.append({"subject": parts[0], "relation": parts[1], "object": parts[2]})

        # FISSN Domain Ontology Keyword Mapping to Scalar Coordinates (s)
        # FISSN domain ontology, loaded from maker-written data files rather
        # than a py word list. Format: tier | domain class.
        self.fissn_domain_map: Dict[str, float] = {}
        for path in sorted(glob.glob(os.path.join(base, "fissn_taxonomy_*.tsv"))):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) != 2 or not parts[0] or not parts[1]:
                        continue
                    try:
                        tier = float(parts[0])
                    except ValueError:
                        continue
                    self.fissn_domain_map[parts[1].lower()] = tier

    def _scan_crystal_lexicon(self, word: str) -> str:
        """
        Scans the ingested crystal volumes and gis_english binaries directly 
        to determine part-of-speech classification and lexical categorization.
        """
        w_lower = word.lower()
        grammar = getattr(self, "grammar", None)
        if grammar is not None:
            tag = grammar.tag_of(w_lower)
            return tag if tag else "LEXICAL_PRIMITIVE"

        # Fallback when no grammar is attached: scan crystal records directly
        recs = self.delm.query_by_subject(w_lower)
        for r in recs:
            relation = r.get("relation", "").lower()
            if "part of speech" in relation or "syntactic" in relation:
                obj = str(r.get("object", "")).upper()
                if obj:
                    return obj

        # Broad manifold dispersion scan if exact subject key is unindexed
        for r in self.delm.records:
            if r.get("subject", "").lower() == w_lower:
                rel = r.get("relation", "").lower()
                if "speech" in rel or "category" in rel:
                    obj = str(r.get("object", "")).upper()
                    if obj:
                        return obj

        # Default structural classification returned by the crystal manifold if unmapped
        return "LEXICAL_PRIMITIVE"

    def tokenize_and_tag(self, text: str) -> List[Tuple[str, str]]:
        """
        Splits input text and assigns structural lexical tags dynamically via crystal scanning.
        """
        tokens = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b|\d+(?:\.\d+)?", text)
        tagged = []
        for tok in tokens:
            pos = self._scan_crystal_lexicon(tok)
            tagged.append((tok, pos))
        return tagged
        
    def map_to_fissn_coordinate(self, text: str) -> Tuple[float, str]:
        """
        Maps incoming query terms to their FISSN ontological tier coordinate (s)
        and semantic description using dynamic semantic token intersection and domain weighting.
        """
        lower_text = text.lower()
        # Closed-tag words are dropped by the grammar, which knows them in any
        # language. Only the words the tagger reads as open-tag (verbs such as
        # "is", nouns such as "versus") need declaring, in query_filler_*.tsv.
        stop_words = {r["subject"].lower() for r in self.nature_records
                      if r.get("relation") == "is a query filler"}
        grammar = getattr(self, "grammar", None)
        if grammar is not None:
            for w in re.findall(r'\b[a-zA-Z]{3,}\b', lower_text):
                tag = grammar.tag_of(w)
                if tag is not None and tag not in grammar.open_prior:
                    stop_words.add(w)
        
        query_tokens = [w for w in re.findall(r'\b[a-zA-Z]{3,}\b', lower_text) if w not in stop_words]
        
        # Score tiers based on token and substring intersections across domain keys
        tier_scores: Dict[float, int] = {}
        
        for keyword, s_val in self.fissn_domain_map.items():
            kw_parts = keyword.split()
            # Full phrase match gets higher weight
            if keyword in lower_text:
                tier_scores[s_val] = tier_scores.get(s_val, 0) + 3
            # Individual token matches within domain keywords
            for kp in kw_parts:
                if kp in query_tokens:
                    tier_scores[s_val] = tier_scores.get(s_val, 0) + 1

        if tier_scores:
            # Select the tier coordinate with the highest structural intersection score
            matched_s = max(tier_scores, key=tier_scores.get)
        else:
            matched_s = 1.0  # Fallback baseline

        # Map scalar coordinate to formal ontological tier description
        # Single source for tier names: FISSN_TAXONOMY_REGISTRY in spfs_engine.py.
        # A second copy here drifted out of date when the registry was corrected.
        from spfs_engine import FISSN_TAXONOMY_REGISTRY
        info = FISSN_TAXONOMY_REGISTRY.get(matched_s, {})
        matched_desc = f"{info.get('tier', matched_s)}: {info.get('name', '')}".strip(': ')
        return matched_s, matched_desc

    def parse_intent(self, text: str) -> Dict[str, Any]:
        """
        Parses incoming Seeker input to determine intent, structural signature,
        and safety/distress triggers using pure crystal manifold topology.
        """
        lower_text = text.lower().strip()
        tagged_tokens = self.tokenize_and_tag(text)

        # Distress boundary is handled in app.py before routing (slc_nature_*.tsv)
        safety_flag = None
        
        # Chat and identity routing from bin data only (no word lists)
        intent_type = None
        grammar = getattr(self, "grammar", None)
        if grammar is not None:
            q_norm = " ".join(grammar.tokenize(text))
            intent_hit, hit_len, hit_subj = None, 0, ""
            identity_cats = set()
            for r in list(self.delm.records) + self.nature_records:
                if r.get("relation") != "signals discourse intent":
                    continue
                subj = " ".join(grammar.tokenize(r.get("subject", "")))
                obj = str(r.get("object", ""))
                if obj == "IDENTITY_INQUIRY":
                    identity_cats |= grammar.category_of.get(subj, set())
                n = len(subj.split())
                if subj and f" {subj} " in f" {q_norm} " and n > hit_len:
                    intent_hit, hit_len, hit_subj = obj, n, subj
            cat = grammar.input_category(text, prefer_pair=False)
            chat_cats = set(grammar.reply_of) | set(grammar.reply_of.values()) | identity_cats
            lean = grammar.chat_lean(text, chat_cats)
            strong = lean is None or lean > 0.0
            # A knowledge base topic outranks chat lean. topic_words already
            # requires the term to appear in a knowledge base record subject and to
            # lean science, so a stray mention in one mined chat sentence
            # cannot pull a science query into chat.
            topics = grammar.topic_words(text, chat_cats)
            if topics:
                strong = False
            cancelled = False
            if intent_hit in ("IDENTITY_INQUIRY", "STATUS_INQUIRY"):
                rest = f" {q_norm} ".replace(f" {hit_subj} ", " ", 1).strip()
                rest_lean = grammar.chat_lean(rest, chat_cats, strict=True) if rest else None
                if rest_lean is not None and rest_lean <= 0.0:
                    intent_hit = None
                    cancelled = True
            if cancelled:
                pass
            elif intent_hit == "STATUS_INQUIRY":
                intent_type = "STATUS_INQUIRY"
            elif intent_hit == "IDENTITY_INQUIRY" or (intent_hit is None and strong and cat in identity_cats):
                intent_type = "IDENTITY_INQUIRY"
            elif intent_hit is not None or (strong and (cat in grammar.reply_of or cat in set(grammar.reply_of.values()))):
                intent_type = "GREETING_PHATIC"

        if intent_type is None:
            if lower_text.endswith("?") or any(w[1] == "INTERROGATIVE" for w in tagged_tokens):
                intent_type = "WH_INQUIRY"
            else:
                intent_type = "EXPLORATORY"

        # Construct structural syntax pattern sequence
        syntax_structure = " ".join([f"[{pos}]" for _, pos in tagged_tokens])

        # Map query to FISSN Ontological Tier Coordinate
        fissn_s, fissn_desc = self.map_to_fissn_coordinate(text)

        return {
            "raw_text": text,
            "intent_type": intent_type,
            "safety_flag": safety_flag,
            "tokens": tagged_tokens,
            "syntax_structure": syntax_structure,
            "fissn_coordinate": fissn_s,
            "fissn_description": fissn_desc
        }


# Standalone Verification Test
if __name__ == "__main__":
    print("=" * 78)
    print("        CS ALGEBRAIC PARSER & GLS ENGINE TEST (PURE CRYSTAL SCAN)")
    print("=" * 78)

    parser = CSApAlgebraicParser()
    test_queries = [
        "Hello EnQuerant",
        "What is your nature?",
        "Are you online and operational?",
    ]

    for q in test_queries:
        result = parser.parse_intent(q)
        print(f"\nQuery: {q}")
        print(f"Intent Type : {result['intent_type']}")
        print(f"Structure   : {result['syntax_structure']}")
        print(f"Safety Flag : {result['safety_flag']}")
        print("-" * 78)
