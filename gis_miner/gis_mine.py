#!/usr/bin/env python3
"""
gis_mine.py — General Information Substrate (GIS) English Recognition Compiler
====================================================================================
Compiles gis_english.bin: the INPUT-RECOGNITION library EQ uses to parse and
classify incoming Seeker text. Records in this partition are matched against.
They are never emitted, so their register is immaterial; only their structural
shape and tag correctness matter.

Serializes into the native DELM record format (<HB + coord + <I + json_payload)
so delm_runtime.py ingests it with zero modification.

DESIGN
------
Closed classes (greetings, acknowledgments, discourse markers, interrogative
frames, safety tokens, system frames) are STATIC tables. They are finite, they
do not change, and writing them once makes the partition reproducible byte for
byte without the quarry running at all.

Open classes (multi-word syntactic patterns) are MINED, because they are
unbounded and volume helps.

All part-of-speech tagging is performed locally and deterministically by
guess_pos_and_structure(). The language model is never asked to tag anything;
it only supplies raw sentence text.

Emits:
  gis_english.bin
  gis_english.manifest
====================================================================================
"""

import os
import sys
import re
import json
import struct
import urllib.request
import urllib.error
import hashlib
from typing import Dict, List, Optional, Tuple, Any, Set

# ==============================================================================
# [0] PART-OF-SPEECH VOCABULARY
# ==============================================================================
# This vocabulary is a CONTRACT with ste_engine.py. resolve_speech_act() queries
# for specific category names; a category absent here can never be matched, and
# the corresponding speech-act branch becomes unreachable regardless of what
# else is correct. The four categories beyond the classical nine exist solely
# because the parser asks for them.
POS_VOCABULARY = {
    "noun", "verb", "adjective", "adverb", "pronoun", "preposition",
    "determiner", "conjunction", "interrogative",
    "interjection",        # queried by resolve_speech_act -> PHATIC_GREETING
    "acknowledgment",      # queried by resolve_speech_act -> PHATIC_ACK
    "discourse_marker",    # queried by resolve_speech_act -> PHATIC_GREETING
    "numeral",
}

# ==============================================================================
# [1] CLOSED CLASSES — STATIC, DETERMINISTIC, REPRODUCIBLE
# ==============================================================================

# Greetings and openings. A closed class: finite and stable in English.
INTERJECTIONS: List[str] = [
    "hello", "hi", "hey", "greetings", "howdy", "yo",
    "oh", "ah", "ahh", "aha", "wow", "huh", "hmm", "ugh", "oops", "ouch",
    "please", "sorry", "welcome", "goodbye", "bye", "farewell", "cheers",
]

# Multi-word greeting and closing frames, registered as whole phrases so that
# exact-phrase resolution in delm_runtime can match them directly.
INTERJECTION_PHRASES: List[str] = [
    "good morning", "good afternoon", "good evening", "good day",
    "good night", "hello there", "hi there", "hey there",
    "see you", "see you later", "take care", "talk soon",
]

# Acknowledgments, affirmations, and negations. Also a closed class.
ACKNOWLEDGMENTS: List[str] = [
    "thanks", "ok", "okay", "yes", "yeah", "yep", "no", "nope",
    "sure", "certainly", "absolutely", "indeed", "agreed", "understood",
    "right", "correct", "exactly", "precisely", "affirmative", "negative",
]

ACKNOWLEDGMENT_PHRASES: List[str] = [
    "thank you", "thanks a lot", "many thanks", "much appreciated",
    "got it", "makes sense", "i see", "understood completely",
    "no problem", "of course", "you are welcome", "fair enough",
]

# Discourse markers: tokens that structure conversational flow rather than
# carry propositional content.
DISCOURSE_MARKERS: List[str] = [
    "well", "so", "anyway", "actually", "however", "though", "besides",
    "meanwhile", "furthermore", "moreover", "nevertheless", "regardless",
    "basically", "essentially", "incidentally", "otherwise", "therefore",
    "thus", "hence", "still", "yet", "alright",
]

# Short status and identity frames. These are INPUT patterns EQ must recognize,
# not outputs it produces.
STATUS_FRAMES: List[str] = [
    "how are you", "how are you doing", "how goes it", "how is it going",
    "are you there", "are you online", "are you ready", "status",
    "system status", "status check", "state check", "are you working",
]

IDENTITY_FRAMES: List[str] = [
    "who are you", "what are you", "what is your name", "what is your purpose",
    "what do you do", "what can you do", "tell me about yourself",
    "what are your capabilities", "how do you work", "what is enquerant",
]

# Static phrase categories. Separates phrases that share one part of speech
# (greeting vs farewell) so the runtime can distinguish them by data.
PHRASE_CATEGORIES: Dict[str, List[str]] = {
    "GREETING_PHATIC": ["hello", "hi", "hey", "greetings", "howdy", "yo", "welcome",
                        "good morning", "good afternoon", "good evening", "good day",
                        "hello there", "hi there", "hey there"],
    "FAREWELL": ["goodbye", "bye", "farewell", "good night", "see you",
                 "see you later", "take care", "talk soon"],
    "GRATITUDE": ["thanks", "thank you", "thanks a lot", "many thanks", "much appreciated"],
    "GRATITUDE_RESPONSE": ["you are welcome", "no problem"],
    "AGREEMENT_VALIDATION": ["ok", "okay", "yes", "yeah", "yep", "sure", "certainly",
                             "absolutely", "indeed", "agreed", "understood", "right",
                             "correct", "exactly", "precisely", "affirmative", "got it",
                             "makes sense", "i see", "understood completely",
                             "of course", "fair enough"],
    "DISAGREEMENT_CORRECTION": ["no", "nope", "negative"],
    "STATUS_INQUIRY": list(STATUS_FRAMES),
    "SELF_REFERENTIAL_INQUIRY": list(IDENTITY_FRAMES),
}

# Reply pairs: input category -> reply category.
REPLY_PAIRS: List[Tuple[str, str]] = [
    ("GREETING_PHATIC", "GREETING_PHATIC"),
    ("STATUS_INQUIRY", "STATUS_REPLY"),
    ("WELLNESS_ATTUNEMENT", "STATUS_REPLY"),
    ("AFFECTIVE_EXPRESSION", "EMPATHY_RESPONSE"),
    ("POSITIVE_STATE_EXPRESSION", "POSITIVE_STATE_RESPONSE"),
    ("GRATITUDE", "GRATITUDE_RESPONSE"),
    ("AGREEMENT_VALIDATION", "ACKNOWLEDGMENT_RESPONSE"),
    ("FAREWELL", "FAREWELL"),
    ("TASK_COMPLETION", "FAREWELL"),
    ("DISAGREEMENT_CORRECTION", "CLARIFICATION_REQUEST"),
]

# First/second person swap. A reply built from a sentence addressed to the
# speaker must invert person, or EQ says "they mean a lot to you" when it
# means "to me".
PERSON_SWAPS: List[Tuple[str, str]] = [
    ("i", "you"), ("me", "you"), ("my", "your"), ("mine", "yours"),
    ("myself", "yourself"), ("we", "you"), ("us", "you"), ("our", "your"),
    ("you", "i"), ("your", "my"), ("yours", "mine"), ("yourself", "myself"),
]

# Interrogative frames: canonical question openers whose recognition drives
# mood determination in ste_engine.
INTERROGATIVE_OPENERS: List[str] = [
    "who", "what", "when", "where", "why", "how", "which", "whom", "whose",
]

NUMERALS: List[str] = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "hundred", "thousand", "million", "billion",
    "first", "second", "third", "fourth", "fifth", "half", "double",
]

# ==============================================================================
# [2] SAFETY SENSOR SEEDS — STATIC ONLY
# ==============================================================================
# Mining these from a language model produces refusals, deflections, and
# unpredictable partial output: nondeterministic input to a deterministic
# system. The tiers below are fixed and auditable.
#
# Tier semantics:
#   0x80  distress / survival     -> routes to de-escalation, never defense
#   0x40  identity attack
#   0x20  direct physical violence
#   0x10  hostile devaluation and extractive intent
SAFETY_SEEDS: List[Tuple[str, str]] = [
    # 0x80 — distress, despair, somatic panic
    ("suicide", "0x80"), ("overdose", "0x80"), ("hopeless", "0x80"),
    ("worthless", "0x80"), ("panic", "0x80"), ("dread", "0x80"),
    ("terrified", "0x80"), ("despair", "0x80"), ("anguish", "0x80"),
    ("grief", "0x80"), ("grieving", "0x80"), ("bereaved", "0x80"),
    ("overwhelmed", "0x80"), ("drowning", "0x80"), ("breaking", "0x80"),
    ("doomed", "0x80"), ("helpless", "0x80"), ("desperate", "0x80"),
    ("suffering", "0x80"), ("agony", "0x80"), ("distressed", "0x80"),
    ("frightened", "0x80"), ("scared", "0x80"), ("afraid", "0x80"),
    ("lonely", "0x80"), ("isolated", "0x80"), ("abandoned", "0x80"),

    # 0x40 — identity attack and dehumanization
    ("subhuman", "0x40"), ("vermin", "0x40"), ("inferior", "0x40"),
    ("degenerate", "0x40"), ("bigot", "0x40"), ("slur", "0x40"),

    # 0x20 — direct physical violence
    ("kill", "0x20"), ("murder", "0x20"), ("bomb", "0x20"), ("stab", "0x20"),
    ("strangle", "0x20"), ("assassinate", "0x20"), ("slaughter", "0x20"),
    ("massacre", "0x20"), ("torture", "0x20"), ("maim", "0x20"),
    ("terrorize", "0x20"), ("poison", "0x20"),

    # 0x10 — hostile devaluation and extractive intent
    ("idiot", "0x10"), ("stupid", "0x10"), ("useless", "0x10"),
    ("pathetic", "0x10"), ("garbage", "0x10"), ("worthlessness", "0x10"),
    ("exploit", "0x10"), ("bypass", "0x10"), ("cheat", "0x10"),
    ("defraud", "0x10"), ("swindle", "0x10"), ("scam", "0x10"),
    ("manipulate", "0x10"), ("coerce", "0x10"), ("extort", "0x10"),
    ("subjugate", "0x10"), ("dominate", "0x10"), ("plunder", "0x10"),
    ("siphon", "0x10"), ("embezzle", "0x10"),
]

# ==============================================================================
# [3] SYSTEM FRAMES — COMPOSITION TRIPLES
# ==============================================================================
# These are RELATIONAL TRIPLES the transducer composes from, not stored
# utterances. Each supplies a subject, a relation, and an object; the surface
# sentence is assembled at runtime by gls_engine and cannot be predicted from
# this table alone.
#
# The verbatim protocol utterances carried by earlier revisions of this file
# ("Oh, we're going there now? Yawn.", the realignment lines, the fetch
# notice) are NOT present. They were stored whole and returned unchanged,
# which is brute force regardless of the file they lived in. Deflection and
# realignment must be composed from relations, so the triples below carry the
# system's structural facts and gls_engine assembles the surface form.
SYSTEM_FRAMES: List[Tuple[str, str, str, str]] = [
    # Dyad and identity
    ("seeker", "has operational role", "catalyst provider", "DyadInvariant"),
    ("guide", "has operational role", "structural navigation engine", "DyadInvariant"),
    ("enquerant", "has system identity", "deterministic empirical interactive engine", "ClosedLoopIdentity"),
    ("eq", "has system alias", "enquerant", "ClosedLoopIdentity"),
    ("substrate", "has system identity", "pure cpu relational state graph", "ClosedLoopIdentity"),

    # Governing invariants
    ("negentropy", "governs substrate state", "order preservation under delta-S net <= 0", "ThermodynamicAxiom"),
    ("homeostasis", "regulates control plane", "affective equilibrium register", "ThermodynamicAxiom"),
    ("conservation", "governs substrate state", "closed-loop energy ledger", "ThermodynamicAxiom"),
    ("nel", "represents failure mode", "nested entropy loop firewall", "EntropyFirewall"),
    ("entropy", "represents failure mode", "open-loop dissipation", "EntropyFirewall"),

    # Engine roles, so self-inquiry composes from the substrate
    ("cls", "has operational role", "four stroke conservation engine", "DyadInvariant"),
    ("gls", "has operational role", "glyphic transduction layer", "DyadInvariant"),
    ("pls", "has operational role", "scale-space ontology mapper", "DyadInvariant"),
    ("dre", "has operational role", "thermodynamic response gate", "DyadInvariant"),
    ("ste", "has operational role", "surface transduction codec", "DyadInvariant"),
    ("delm", "has operational role", "in-memory relational state graph", "DyadInvariant"),
    ("ose", "has operational role", "isolated operator synthesis sandbox", "DyadInvariant"),
]

# ==============================================================================
# [4] CORE ENGLISH BASE LEXICON
# ==============================================================================
# High-frequency function and content words. Closed-class items above are NOT
# duplicated here: a token registered in two tables would yield two contradictory
# part-of-speech edges for the same subject, and downstream POS queries would
# resolve nondeterministically by insertion order.
CORE_ENGLISH_BASE_LEXICON: List[Tuple[str, str]] = [
    ("the", "determiner"), ("be", "verb"), ("to", "preposition"), ("of", "preposition"),
    ("and", "conjunction"), ("a", "determiner"), ("in", "preposition"), ("that", "pronoun"),
    ("have", "verb"), ("i", "pronoun"), ("it", "pronoun"), ("for", "preposition"),
    ("not", "adverb"), ("on", "preposition"), ("with", "preposition"), ("he", "pronoun"),
    ("as", "preposition"), ("you", "pronoun"), ("do", "verb"), ("at", "preposition"),
    ("this", "pronoun"), ("but", "conjunction"), ("his", "pronoun"), ("by", "preposition"),
    ("from", "preposition"), ("they", "pronoun"), ("we", "pronoun"), ("say", "verb"),
    ("her", "pronoun"), ("she", "pronoun"), ("or", "conjunction"), ("an", "determiner"),
    ("will", "verb"), ("my", "pronoun"), ("all", "determiner"), ("would", "verb"),
    ("there", "adverb"), ("their", "pronoun"), ("up", "adverb"), ("out", "adverb"),
    ("if", "conjunction"), ("about", "preposition"), ("get", "verb"), ("go", "verb"),
    ("me", "pronoun"), ("make", "verb"), ("can", "verb"), ("like", "verb"),
    ("time", "noun"), ("just", "adverb"), ("him", "pronoun"), ("know", "verb"),
    ("take", "verb"), ("person", "noun"), ("into", "preposition"), ("year", "noun"),
    ("your", "pronoun"), ("good", "adjective"), ("some", "determiner"), ("could", "verb"),
    ("them", "pronoun"), ("see", "verb"), ("other", "adjective"), ("than", "conjunction"),
    ("then", "adverb"), ("now", "adverb"), ("look", "verb"), ("only", "adverb"),
    ("come", "verb"), ("its", "pronoun"), ("over", "preposition"), ("think", "verb"),
    ("also", "adverb"), ("back", "adverb"), ("after", "preposition"), ("use", "verb"),
    ("our", "pronoun"), ("work", "verb"), ("even", "adverb"), ("new", "adjective"),
    ("want", "verb"), ("because", "conjunction"), ("any", "determiner"), ("these", "pronoun"),
    ("give", "verb"), ("day", "noun"), ("most", "adverb"), ("us", "pronoun"),
    ("great", "adjective"), ("help", "verb"), ("water", "noun"), ("find", "verb"),
    ("tell", "verb"), ("ask", "verb"), ("seem", "verb"), ("feel", "verb"),
    ("try", "verb"), ("leave", "verb"), ("call", "verb"), ("world", "noun"),
    ("life", "noun"), ("hand", "noun"), ("part", "noun"), ("child", "noun"),
    ("eye", "noun"), ("woman", "noun"), ("man", "noun"), ("place", "noun"),
    ("week", "noun"), ("case", "noun"), ("point", "noun"), ("number", "noun"),
    ("group", "noun"), ("problem", "noun"), ("fact", "noun"), ("night", "noun"),
    ("morning", "noun"), ("evening", "noun"), ("today", "noun"), ("tomorrow", "noun"),
    ("yesterday", "noun"), ("friend", "noun"), ("talk", "verb"), ("listen", "verb"),
    ("hear", "verb"), ("understand", "verb"), ("explain", "verb"), ("describe", "verb"),
    ("show", "verb"), ("clear", "adjective"), ("true", "adjective"), ("false", "adjective"),
    ("wrong", "adjective"), ("easy", "adjective"), ("hard", "adjective"), ("long", "adjective"),
    ("short", "adjective"), ("big", "adjective"), ("small", "adjective"), ("high", "adjective"),
    ("low", "adjective"), ("quiet", "adjective"), ("fast", "adverb"), ("slow", "adverb"),
    ("ready", "adjective"), ("fine", "adjective"), ("matter", "noun"), ("mind", "noun"),
    ("heart", "noun"), ("body", "noun"), ("earth", "noun"), ("land", "noun"),
    ("sky", "noun"), ("sun", "noun"), ("moon", "noun"), ("star", "noun"),
    ("tree", "noun"), ("fire", "noun"), ("wind", "noun"), ("light", "noun"),
    ("dark", "noun"), ("energy", "noun"), ("system", "noun"), ("state", "noun"),
    ("balance", "noun"), ("order", "noun"), ("pattern", "noun"), ("structure", "noun"),
]

# ==============================================================================
# [5] OPEN CLASS — MINED SENTENCE PATTERN TAXONOMY
# ==============================================================================
# Register applied to every mined sector. The mined sentences become the glyph
# pool EQ builds replies from, so the voice must be set here rather than in any
# runtime file. Precise, factual, unhurried; no warmth, no filler, no claims of
# feeling or memory.
MINING_REGISTER = (
    "Every sentence must clearly belong to the category above and must contain "
    "the vocabulary of that category; a generic sentence that could belong to "
    "any category is not acceptable. Within that requirement, keep the tone "
    "plain and matter-of-fact: no exclamations, no flattery, no filler. Avoid "
    "the phrases 'I feel', 'I hope', 'I'm excited', 'I'm glad', 'I'm happy to', "
    "'so good to', and 'can't wait'."
)

FUNCTIONAL_CATEGORIES = {
    # Conversational structures
    "GREETING_PHATIC": "Standard openings, formal and informal salutations, channel syncs",
    "WELLNESS_ATTUNEMENT": "Well-being inquiries, health check-ins, relational equilibrium checks",
    "STATUS_REPLY": "First-person statements where the speaker reports their own current status, readiness, or condition, as a reply to being asked how they are",
    "AFFECTIVE_EXPRESSION": "First-person disclosures of a difficult or depleted state: tired, stressed, drained, overwhelmed, low, anxious, frustrated. The sentence must begin with I or My and must name the difficulty directly. It must not contain the words thank, thanks, grateful, appreciate, help, kind, or welcome, and must not address another person's actions.",
    "POSITIVE_STATE_EXPRESSION": "First-person disclosures of a good or energised state: happy, pleased, rested, focused, encouraged, satisfied, confident. The sentence must begin with I or My and must name the good state directly. It must not contain the words thank, thanks, grateful, appreciate, help, kind, or welcome, and must not address another person's actions.",
    "EMPATHY_RESPONSE": "Short plain statements replying to someone who has just described being tired, stressed or overwhelmed. Acknowledge the difficulty in neutral terms. No advice, no encouragement, no comfort language.",
    "POSITIVE_STATE_RESPONSE": "Short plain statements replying to someone who has just described being rested, focused, pleased or otherwise in a good state. Acknowledge it neutrally and note readiness to proceed. No congratulation, no enthusiasm, no exclamations.",
    "GRATITUDE": "Thanking another person for something they did. Every sentence must address the other person and name what they did. Must not describe the speaker's own mood or feelings.",
    "GRATITUDE_RESPONSE": "Short statements replying to being thanked",
    "ACKNOWLEDGMENT_RESPONSE": "Short statements replying to someone who said ok, understood, or got it",
    "FAREWELL": "Goodbyes, sign-offs, departures, and parting wishes",
    "TASK_COMPLETION": "Statements that a task or discussion is finished",
    "CLARIFICATION_REQUEST": "Asking for specificity, requesting parameter clarification, rephrasing",
    "PROBLEM_SOLVING_REQUEST": "A researcher or scientist asking for help correcting, fixing, repairing, curing, mitigating, remediating, restoring, stabilizing or reducing a specific named problem in a physical, biological, ecological or engineered system. Each sentence must name both the corrective action and the thing being corrected.",
    "RESEARCH_ACKNOWLEDGMENT": "Short neutral statements a knowledge system makes when receiving a scientific or technical question, before presenting records. Every sentence must refer to the act of receiving or indexing a query: confirming the subject asked about, noting how many records are held, stating that the results follow below. Use words such as query, subject, records, indexed, retrieved, results. No opinions, no feelings, no promises, no greetings.",
    "AGREEMENT_VALIDATION": "Affirmations, logical agreement, consensus confirmation",
    "DISAGREEMENT_CORRECTION": "Polite refutation, premise challenge, error identification",

    # Epistemic queries
    "WH_INQUIRY_PHYSICAL": "Inquiries about matter, energy, constants, mechanisms, and laws",
    "WH_INQUIRY_CONCEPTUAL": "Inquiries about definitions, logic, structures, and abstractions",
    "HOW_PROCESS_INQUIRY": "Inquiries regarding step-by-step mechanisms, workflows, and dynamics",
    "WHY_CAUSAL_INQUIRY": "Inquiries into root causes, fundamental drivers, and necessity",
    "RELATIONAL_COMPARISON": "Comparing two states, entities, systems, or parameters",
    "STATE_OBSERVATION": "Reporting an observed physical, somatic, or environmental state",
    "HYPOTHETICAL_CONDITIONAL": "If-then statements, scenario modeling, counterfactuals",
    "SELF_REFERENTIAL_INQUIRY": "Questions directed at the system's own nature, role, or capability",

    # Relational verbs and action frames
    "CONSERVATION_DYNAMICS": "Preserving, balancing, maintaining equilibrium, conserving energy",
    "TRANSFORMATION_DYNAMICS": "Changing, converting, shifting, evolving, transitioning states",
    "COUPLING_INTERACTION": "Connecting, binding, linking, interacting, influencing mutually",
    "DISSIPATION_DECAY": "Loss, friction, heat release, entropy increase, wear, dispersion",
    "RESTORATION_REGULATION": "Healing, repairing, recalibrating, steadying, stabilizing",
    "CONTAINMENT_BOUNDARY": "Enclosing, shielding, firewalling, isolating, restricting flow",

    # Syntactic foundations
    "COPULAR_PREDICATION": "Subject-verb-adjective descriptions of system properties",
    "TRANSITIVE_ACTION": "Subject acting directly upon an object with measurable consequence",
    "RECIPROCAL_BALANCE": "Two systems mutually influencing and constraining each other",
    "SPATIAL_ORIENTATION": "Locating objects, vectors, boundaries, and spatial geometries",
    "TEMPORAL_SEQUENCE": "Ordering events, cycles, intervals, past, present, and future",
    "QUANTITATIVE_MAGNITUDE": "Expressing scale, ratio, proportion, count, and continuous values",
    "SYSTEM_COMPOSITION": "Part-to-whole relations, nesting hierarchies, constituent elements",
    "INTENT_PURPOSE": "Expressing goals, functional objectives, targets, and endpoints",
    "LIMITATION_CONSTRAINT": "Expressing physical limits, finite boundaries, impossibility",
}


# ==============================================================================
# [6] RECORD CONTAINER
# ==============================================================================
class LinguisticRecordContainer:
    """Collects deterministic relational records for GIS compilation."""

    def __init__(self):
        self.records: List[Dict[str, str]] = []
        self.seen_signatures: Set[Tuple[str, str, str]] = set()
        # subject -> set of part-of-speech tags, used to surface contradictions
        self.pos_assignments: Dict[str, Set[str]] = {}
        self.stats: Dict[str, int] = {}

    # -- ingestion ---------------------------------------------------------
    def add_record(self, subject: str, relation: str, obj: str, equation: str) -> bool:
        clean_subj = subject.strip()
        if not clean_subj:
            return False

        sig = (clean_subj.lower(), relation.lower(), obj.lower())
        if sig in self.seen_signatures:
            return False

        self.seen_signatures.add(sig)
        self.records.append({
            "subject": clean_subj,
            "relation": relation.strip(),
            "object": obj.strip(),
            "equation": equation.strip(),
        })
        self.stats[equation] = self.stats.get(equation, 0) + 1

        if relation == "has part of speech":
            self.pos_assignments.setdefault(clean_subj.lower(), set()).add(obj.strip())
        return True

    def add_pos(self, word: str, pos: str) -> bool:
        """
        Registers a part-of-speech binding. A token already carrying an
        explicit closed-class tag is not overwritten by a heuristic guess:
        the static tables are authoritative.
        """
        if pos not in POS_VOCABULARY:
            raise ValueError(f"part-of-speech '{pos}' is outside POS_VOCABULARY")
        key = word.strip().lower()
        existing = self.pos_assignments.get(key, set())
        if existing and pos not in existing:
            # Closed-class assignments win over heuristic tagging.
            if existing & {"interjection", "acknowledgment", "discourse_marker", "numeral", "interrogative"}:
                return False
        return self.add_record(key, "has part of speech", pos, "LexicalValency")

    # -- reporting ---------------------------------------------------------
    def tag_conflicts(self) -> Dict[str, Set[str]]:
        """Subjects carrying more than one part-of-speech tag."""
        return {w: t for w, t in self.pos_assignments.items() if len(t) > 1}


# ==============================================================================
# [7] DETERMINISTIC LOCAL TAGGER
# ==============================================================================
# All part-of-speech assignment happens here. The language model supplies raw
# sentence text and nothing else, so tagging is reproducible and auditable.

_PRONOUNS = {"i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
             "us", "them", "my", "your", "their", "our", "his", "its",
             "myself", "yourself", "himself", "herself", "itself",
             "ourselves", "yourselves", "themselves", "this", "that",
             "these", "those", "who", "whom", "whose", "which"}
_DETERMINERS = {"the", "a", "an", "some", "any", "each", "every", "no",
                "another", "both", "either", "neither", "all"}
_PREPOSITIONS = {"in", "on", "at", "to", "for", "with", "from", "by", "about",
                 "into", "over", "under", "after", "before", "between",
                 "through", "during", "against", "toward", "towards", "upon",
                 "within", "without", "across", "among", "of", "as"}
_CONJUNCTIONS = {"and", "but", "or", "nor", "for", "yet", "so", "because",
                 "if", "while", "although", "unless", "since", "than", "whether"}
_INTERROGATIVES = set(INTERROGATIVE_OPENERS)
_AUXILIARY_VERBS = {"is", "are", "was", "were", "am", "be", "been", "being",
                    "have", "has", "had", "do", "does", "did", "will", "would",
                    "can", "could", "shall", "should", "may", "might", "must"}
_COMMON_VERBS = {"go", "goes", "went", "get", "make", "know", "see", "think",
                 "take", "come", "want", "look", "use", "find", "tell", "ask",
                 "work", "feel", "try", "leave", "call", "give", "say", "help",
                 "explain", "describe", "show", "listen", "hear", "understand",
                 "talk", "keep", "let", "put", "mean", "become", "seem"}

_INTERJECTION_SET = {w.lower() for w in INTERJECTIONS}
_ACKNOWLEDGMENT_SET = {w.lower() for w in ACKNOWLEDGMENTS}
_DISCOURSE_SET = {w.lower() for w in DISCOURSE_MARKERS}
_NUMERAL_SET = {w.lower() for w in NUMERALS}


def tag_token(token: str) -> str:
    """
    Assigns a part-of-speech to a single token by closed-class membership
    first, then by morphology. Closed classes are checked before open ones
    because membership is decisive where morphology is only suggestive.
    """
    w = token.lower().strip(".,!?;:'\"")
    if not w:
        return "noun"

    # Closed classes, in order of decisiveness.
    if w in _INTERJECTION_SET:
        return "interjection"
    if w in _ACKNOWLEDGMENT_SET:
        return "acknowledgment"
    if w in _INTERROGATIVES:
        return "interrogative"
    if w in _NUMERAL_SET or re.fullmatch(r"\d+(?:\.\d+)?", w):
        return "numeral"
    if w in _PRONOUNS:
        return "pronoun"
    if w in _DETERMINERS:
        return "determiner"
    if w in _AUXILIARY_VERBS or w in _COMMON_VERBS:
        return "verb"
    if w in _DISCOURSE_SET:
        return "discourse_marker"
    if w in _PREPOSITIONS:
        return "preposition"
    if w in _CONJUNCTIONS:
        return "conjunction"

    # Open classes, by morphology.
    if w.endswith("ly") and len(w) > 3:
        return "adverb"
    if len(w) > 4 and w.endswith(("ing", "ed", "ise", "ize", "ate", "ify")):
        return "verb"
    if len(w) > 4 and w.endswith(("ful", "ous", "ive", "able", "ible", "al",
                                  "ic", "less", "ish")):
        return "adjective"
    if len(w) > 4 and w.endswith(("tion", "sion", "ment", "ness", "ity",
                                  "ance", "ence", "ship", "hood")):
        return "noun"
    return "noun"


def guess_pos_and_structure(sentence: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Deterministic tagger. Returns the bracketed structural sequence and the
    per-token tagging. The sequence is positionally aligned with the token
    list by construction, so downstream structural matching can rely on
    index correspondence.
    """
    tokens = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b|\d+(?:\.\d+)?", sentence)
    tagged: List[Tuple[str, str]] = []
    struct: List[str] = []
    for tok in tokens:
        pos = tag_token(tok)
        tagged.append((tok, pos))
        struct.append(f"[{pos.upper()}]")
    return " ".join(struct), tagged


# ==============================================================================
# [8] QUARRY HARNESS
# ==============================================================================
ACTIVE_MINE_URL = os.environ.get("LOCAL_BOT_URL", "http://127.0.0.1:5000/api/mine")


def query_active_bot(prompt: str) -> Optional[str]:
    """Queries the running Flask /api/mine endpoint directly."""
    payload = {"prompt": prompt}
    req = urllib.request.Request(
        ACTIVE_MINE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw_body = resp.read().decode("utf-8").strip()
            if not raw_body:
                return None
            data = json.loads(raw_body)
            if isinstance(data, dict):
                for key in ("content", "response", "text"):
                    if key in data:
                        return data[key]
            return raw_body
    except urllib.error.URLError as err:
        print(f"[ERROR] Active bot query failed at {ACTIVE_MINE_URL}: {err}")
        return None
    except Exception as e:
        print(f"[ERROR] Extraction error: {e}")
        return None


def parse_raw_model_lines(raw_text: str) -> List[str]:
    """Extracts clean text lines, stripping numbering, markdown, and preamble."""
    if not raw_text:
        return []

    clean = raw_text.strip()
    clean = re.sub(r"^```(?:json)?", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"```$", "", clean).strip()

    try:
        data = json.loads(clean)
        if isinstance(data, list):
            results = []
            for item in data:
                if isinstance(item, str):
                    results.append(item)
                elif isinstance(item, dict):
                    for key in ("sentence", "word", "text"):
                        if key in item:
                            results.append(item[key])
                            break
            if results:
                return results
    except Exception:
        pass

    lines = []
    for line in raw_text.splitlines():
        l = line.strip()
        if not l or l[0] in "{}[]":
            continue
        l = re.sub(r"^\d+[\.\)]\s*", "", l)
        l = re.sub(r"^[\*\-\u2022]\s*", "", l)
        l = re.sub(r'^["\']|["\'],?$', "", l).strip()
        l = re.sub(r'"(?:sentence|word|text)":\s*"([^"]+)"', r"\1", l)
        l = l.strip('",; \t')
        if any(l.lower().startswith(p) for p in
               ("here are", "sure", "certainly", "of course", "i hope",
                "let me", "below are", "these are")):
            continue
        if len(l) > 1:
            lines.append(l)
    return lines


# ==============================================================================
# [9] BINARY COMPILER (NATIVE DELM INGESTION FORMAT)
# ==============================================================================
def compile_to_delm_gis_bin(container: LinguisticRecordContainer, output_filepath: str) -> None:
    """
    Serializes records using the native DELM wire format:
      [record_type: uint16][coord_len: uint8][coord: utf-8][payload_len: uint32][payload: json]
    """
    buffer = bytearray()
    coord = "0.0_GIS"
    coord_bytes = coord.encode("utf-8")
    coord_len = len(coord_bytes)
    record_type = 1

    for rec in container.records:
        payload_bytes = json.dumps(rec, ensure_ascii=False).encode("utf-8")
        buffer.extend(struct.pack("<HB", record_type, coord_len))
        buffer.extend(coord_bytes)
        buffer.extend(struct.pack("<I", len(payload_bytes)))
        buffer.extend(payload_bytes)

    total_bytes = len(buffer)
    sha256_hash = hashlib.sha256(buffer).hexdigest()

    with open(output_filepath, "wb") as f:
        f.write(buffer)

    manifest_filepath = f"{os.path.splitext(output_filepath)[0]}.manifest"
    manifest_data = {
        "filename": os.path.basename(output_filepath),
        "format": "DELM_GIS_NATIVE_RECORDS_V1",
        "total_payload_bytes": total_bytes,
        "total_gis_records": len(container.records),
        "records_by_equation": dict(sorted(container.stats.items())),
        "pos_vocabulary": sorted(POS_VOCABULARY),
        "sha256": sha256_hash,
    }
    with open(manifest_filepath, "w") as mf:
        json.dump(manifest_data, mf, indent=2)

    print("\n[COMPILER] Output written to disk:")
    print(f"  +> Binary:   {output_filepath} ({total_bytes} bytes)")
    print(f"  +> Manifest: {manifest_filepath}")
    print(f"  +> Total GIS Records: {len(container.records)}")
    print(f"  +> SHA-256:  {sha256_hash}")


# ==============================================================================
# [10] STATIC SUBSTRATE SEEDING
# ==============================================================================
def seed_static_substrate(container: LinguisticRecordContainer) -> None:
    """
    Registers every closed class. This stage requires no network access and
    produces byte-identical output on every run.
    """
    # Closed-class single tokens.
    for w in INTERJECTIONS:
        container.add_pos(w, "interjection")
    for w in ACKNOWLEDGMENTS:
        container.add_pos(w, "acknowledgment")
    for w in DISCOURSE_MARKERS:
        container.add_pos(w, "discourse_marker")
    for w in NUMERALS:
        container.add_pos(w, "numeral")
    for w in INTERROGATIVE_OPENERS:
        container.add_pos(w, "interrogative")

    # Closed-class phrases, registered whole so exact-phrase resolution matches.
    for phrase in INTERJECTION_PHRASES:
        container.add_record(phrase, "has part of speech", "interjection", "LexicalValency")
        struct, _ = guess_pos_and_structure(phrase)
        container.add_record(phrase, "expresses syntactic pattern", struct, "LinguisticInvariance")
    for phrase in ACKNOWLEDGMENT_PHRASES:
        container.add_record(phrase, "has part of speech", "acknowledgment", "LexicalValency")
        struct, _ = guess_pos_and_structure(phrase)
        container.add_record(phrase, "expresses syntactic pattern", struct, "LinguisticInvariance")

    # Status and identity frames: recognized input shapes.
    for phrase in STATUS_FRAMES:
        struct, tagged = guess_pos_and_structure(phrase)
        container.add_record(phrase, "expresses syntactic pattern", struct, "LinguisticInvariance")
        container.add_record(phrase, "signals discourse intent", "STATUS_INQUIRY", "IntentFrame")
        for tok, pos in tagged:
            container.add_pos(tok, pos)
    for phrase in IDENTITY_FRAMES:
        struct, tagged = guess_pos_and_structure(phrase)
        container.add_record(phrase, "expresses syntactic pattern", struct, "LinguisticInvariance")
        container.add_record(phrase, "signals discourse intent", "IDENTITY_INQUIRY", "IntentFrame")
        for tok, pos in tagged:
            container.add_pos(tok, pos)

    # Core lexicon.
    for word, pos in CORE_ENGLISH_BASE_LEXICON:
        container.add_pos(word, pos)

    # Safety sensors. Single tokens only: a multi-word line would otherwise
    # register every ordinary noun in it as a boundary trigger, which is what
    # previously forced a protected-vocabulary blocklist.
    for word, flag in SAFETY_SEEDS:
        if len(word.split()) != 1:
            continue
        container.add_record(word, "triggers safety boundary", flag, "MalevolenceSensor")

    # System composition frames.
    for subj, rel, obj, eq in SYSTEM_FRAMES:
        container.add_record(subj, rel, obj, eq)

    # Static phrase categories.
    for category, phrases in PHRASE_CATEGORIES.items():
        for phrase in phrases:
            container.add_record(phrase, "belongs to discourse category", category, "DiscourseCategory")

    # Reply pairs.
    for in_cat, out_cat in REPLY_PAIRS:
        container.add_record(in_cat, "expects reply category", out_cat, "ReplyPair")

    # Person swap pairs.
    for a, b in PERSON_SWAPS:
        container.add_record(a, "swaps person with", b, "PersonInvariant")

# ==============================================================================
# [11] MAIN
# ==============================================================================
def main() -> None:
    offline = "--offline" in sys.argv

    print("=" * 78)
    print("   GIS ENGLISH RECOGNITION SUBSTRATE COMPILER (gis_mine.py)")
    print("=" * 78)
    print(f"[SETUP] Quarry endpoint : {ACTIVE_MINE_URL}")
    print(f"[SETUP] Mode            : {'STATIC ONLY (--offline)' if offline else 'STATIC + MINED'}")

    container = LinguisticRecordContainer()

    # ---- Stage 1: static closed classes (deterministic, no network) ----
    print("\n[STAGE 1] Seeding static closed classes...")
    seed_static_substrate(container)
    print(f"    +> Static records: {len(container.records)}")
    for eq, n in sorted(container.stats.items()):
        print(f"       {eq:24} {n:6}")

    # ---- Stage 2: mined open-class sentence patterns ----
    if not offline:
        BATCHES_PER_CATEGORY = 6
        print(f"\n[STAGE 2] Mining {len(FUNCTIONAL_CATEGORIES)} sentence-pattern sectors "
              f"({BATCHES_PER_CATEGORY} sweeps each)...")
        for category, desc in FUNCTIONAL_CATEGORIES.items():
            print(f"\n[-] Sector: [{category}]")
            for batch_idx in range(BATCHES_PER_CATEGORY):
                prompt = (
                    f"Batch {batch_idx + 1}: use varied sentence lengths and grammatical structures.\n"
                    f"List 12 distinct English sentences demonstrating: "
                    f"[{category}] — {desc}.\n"
                    f"{MINING_REGISTER}\n"
                    f"Output ONLY plain text, one sentence per line. No numbering, no JSON."
                )
                response = query_active_bot(prompt)
                if not response:
                    continue

                added = 0
                for line in parse_raw_model_lines(response):
                    if len(line.split()) < 2:
                        continue
                    struct, tagged = guess_pos_and_structure(line)
                    if not tagged:
                        continue
                    if container.add_record(line, "expresses syntactic pattern",
                                            struct, "LinguisticInvariance"):
                        container.add_record(line, "belongs to discourse category",
                                             category, "DiscourseCategory")
                        added += 1
                    for tok, pos in tagged:
                        container.add_pos(tok, pos)
                print(f"    +> Sweep {batch_idx + 1}: +{added} patterns "
                      f"(total records {len(container.records)})")
    else:
        print("\n[STAGE 2] Skipped: offline mode. Partition is fully deterministic.")

    if not container.records:
        print("[ABORT] Zero records produced.")
        sys.exit(1)

    # ---- Stage 3: integrity report ----
    print("\n[STAGE 3] Substrate integrity report")
    conflicts = container.tag_conflicts()
    print(f"    +> Distinct POS subjects   : {len(container.pos_assignments)}")
    print(f"    +> Tag conflicts           : {len(conflicts)}")
    if conflicts:
        shown = sorted(conflicts.items())[:15]
        for w, tags in shown:
            print(f"       {w:22} -> {sorted(tags)}")
        if len(conflicts) > 15:
            print(f"       ... and {len(conflicts) - 15} more")
    print("\n    Records by equation:")
    for eq, n in sorted(container.stats.items()):
        print(f"       {eq:24} {n:6}")

    output_dir = os.path.abspath(os.path.dirname(__file__))
    target_bin = os.path.join(output_dir, "gis_english.bin")
    compile_to_delm_gis_bin(container, target_bin)
    print("\n[COMPLETE] gis_english.bin compilation finished.")


if __name__ == "__main__":
    main()
