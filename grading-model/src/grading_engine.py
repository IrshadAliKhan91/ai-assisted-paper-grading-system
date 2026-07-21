"""
FairMark Grading Model v2 — Clean 3-Layer Architecture

Layer 1: Normalisation (text cleanup, numbers, units, spelling)
Layer 2: Dual Scoring (SBERT semantic 50% + Keyword coverage 40%)
Layer 3: Penalty Gates (negation, contradiction, gaming — 10% cap)
"""

import re
import difflib
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim
from nltk.corpus import wordnet
from spellchecker import SpellChecker
from preprocessing import (
    nlp, get_raw_tokens, normalise_number_words,
    normalise_numeric_formatting, normalise_fractions, normalise_spelling,
)

# ── Re-use proven constants from v1 ─────────────────────────────────

MONTH_MAP = {
    "jan": "january", "feb": "february", "mar": "march", "apr": "april",
    "jun": "june", "jul": "july", "aug": "august", "sep": "september",
    "sept": "september", "oct": "october", "nov": "november", "dec": "december",
}
ORDINAL_RE = re.compile(r"(\d+)\s*(?:st|nd|rd|th)\b", re.IGNORECASE)

ABBREVIATION_DB = {
    "us": "united states", "usa": "united states", "uk": "united kingdom",
    "un": "united nations", "eu": "european union",
    "who": "world health organization", "nato": "north atlantic treaty organization",
    "nasa": "national aeronautics and space administration",
    "dna": "deoxyribonucleic acid", "rna": "ribonucleic acid",
    "atp": "adenosine triphosphate", "co2": "carbon dioxide",
    "h2o": "water", "o2": "oxygen", "nacl": "sodium chloride",
    "cpu": "central processing unit", "gpu": "graphics processing unit",
    "ram": "random access memory", "rom": "read only memory",
    "os": "operating system", "ai": "artificial intelligence",
    "hiv": "human immunodeficiency virus",
    "mri": "magnetic resonance imaging",
    "bc": "before christ", "ad": "anno domini",
    "govt": "government", "dr": "doctor", "prof": "professor",
}

# ── Unit conversion (kept from v1) ──────────────────────────────────

UNIT_ALIASES = {
    "m": "meter", "meters": "meter", "metre": "meter", "metres": "meter",
    "cm": "centimeter", "centimeters": "centimeter",
    "mm": "millimeter", "millimeters": "millimeter",
    "km": "kilometer", "kilometers": "kilometer", "kilometres": "kilometer",
    "in": "inch", "inches": "inch", "ft": "foot", "feet": "foot",
    "kg": "kilogram", "kilograms": "kilogram", "kgs": "kilogram",
    "g": "gram", "grams": "gram", "mg": "milligram", "milligrams": "milligram",
    "lb": "pound", "lbs": "pound", "pounds": "pound",
    "l": "liter", "liters": "liter", "litres": "liter",
    "ml": "milliliter", "milliliters": "milliliter", "millilitres": "milliliter",
    # Single-letter aliases removed — too aggressive (matched first letter of words
    # like "cells", "copies", "force"). Use full unit names or standard abbreviations.
    "celsius": "celsius", "fahrenheit": "fahrenheit", "kelvin": "kelvin",
    "mph": "miles_per_hour", "kmh": "km_per_hour", "kph": "km_per_hour",
}

UNIT_TO_BASE = {
    "meter": ("meter", 1.0), "centimeter": ("meter", 0.01),
    "millimeter": ("meter", 0.001), "kilometer": ("meter", 1000.0),
    "inch": ("meter", 0.0254), "foot": ("meter", 0.3048),
    "kilogram": ("kilogram", 1.0), "gram": ("kilogram", 0.001),
    "milligram": ("kilogram", 0.000001), "pound": ("kilogram", 0.453592),
    "liter": ("liter", 1.0), "milliliter": ("liter", 0.001),
    "celsius": ("celsius", None), "fahrenheit": ("celsius", None),
    "kelvin": ("celsius", None),
    "miles_per_hour": ("km_per_hour", 1.60934),
    "km_per_hour": ("km_per_hour", 1.0),
}


def _resolve_unit(raw):
    if not raw: return None
    r = raw.lower().strip()
    if r in UNIT_TO_BASE: return r
    return UNIT_ALIASES.get(r)


def _convert_to_base(value, unit):
    if unit not in UNIT_TO_BASE: return None
    base, factor = UNIT_TO_BASE[unit]
    if unit == "fahrenheit": return (base, (value - 32) * 5.0 / 9.0)
    if unit == "kelvin": return (base, value - 273.15)
    if factor is None: return (base, value)
    return (base, value * factor)


def _normalise_text(text):
    """Full normalisation pipeline for comparison."""
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9.\s]', ' ', t)
    t = re.sub(r'(?<!\d)\.(?!\d)', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    t = normalise_numeric_formatting(t)
    t = normalise_fractions(t)
    t = normalise_number_words(t)
    t = normalise_spelling(t)
    # Expand month abbreviations and strip ordinals
    t = ORDINAL_RE.sub(r"\1", t)
    words = t.split()
    t = " ".join(MONTH_MAP.get(w, w) for w in words)
    return t


def _get_synonyms(word):
    """WordNet synonyms for a word."""
    syns = set()
    for ss in wordnet.synsets(word):
        for lemma in ss.lemmas():
            syns.add(lemma.name().replace("_", " ").lower())
        for hyp in ss.hypernyms():
            for ln in hyp.lemma_names():
                syns.add(ln.replace("_", " ").lower())
    syns.discard(word)
    return syns


def _extract_numbers_with_units(text):
    """Extract (value, unit_or_empty) pairs from text."""
    return re.findall(r"(\d+(?:\.\d+)?)\s*([a-z%]*)", text.lower())


# ── The Grading Model ───────────────────────────────────────────────

class GradingModel:
    # Filler phrases to strip before grading
    FILLERS = [
        r"\bi\s+think\s+that\b", r"\bi\s+believe\s+that\b",
        r"\bi\s+guess\b", r"\bi\s+am\s+not\s+sure\b",
        r"\bi\s+don'?t\s+know\s+but\b", r"\bi\s+do\s+not\s+know\s+but\b",
        r"\bi\s+don'?t\s+know\b", r"\bi\s+do\s+not\s+know\b",
        r"\bmaybe\b", r"\bprobably\b", r"\bperhaps\b",
        r"\bbasically\b", r"\bactually\b", r"\bto\s+be\s+honest\b",
        r"\b(?:about|approximately|roughly|around|nearly|almost)\b",
    ]

    NEGATION_WORDS = {"not", "no", "never", "neither", "nor", "nobody",
                      "nothing", "nowhere", "hardly", "barely", "scarcely",
                      "don't", "doesn't", "didn't", "won't", "wouldn't",
                      "can't", "cannot", "couldn't", "shouldn't", "isn't",
                      "aren't", "wasn't", "weren't", "hasn't", "haven't"}

    NEGATIVE_PREFIXES = {"un", "im", "in", "ir", "dis", "non"}

    def __init__(self):
        print("Loading SBERT model...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.spell = SpellChecker()
        # Cache normalised-key -> embedding. Answer keys repeat across a batch of
        # papers, so caching avoids re-encoding the same key every time.
        self._key_emb_cache = {}
        print("Grading Model Loaded Successfully!")

    # ================================================================
    #  LAYER 1: NORMALISATION
    # ================================================================

    def _clean(self, text):
        """Remove fillers, normalise text."""
        t = text.strip()
        for f in self.FILLERS:
            t = re.sub(f, " ", t, flags=re.IGNORECASE)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    # ================================================================
    #  LAYER 2a: SBERT SEMANTIC SIMILARITY (50%)
    # ================================================================

    def _encode_key(self, key_norm):
        """Encode an answer key, reusing a cached embedding when possible."""
        emb = self._key_emb_cache.get(key_norm)
        if emb is None:
            emb = self.model.encode(key_norm, convert_to_tensor=True)
            if len(self._key_emb_cache) < 2000:   # bound memory
                self._key_emb_cache[key_norm] = emb
        return emb

    def _sbert_score(self, student_norm, key_norm):
        """Cosine similarity between sentence embeddings."""
        s = self.model.encode(student_norm, convert_to_tensor=True)
        k = self._encode_key(key_norm)
        return max(0.0, min(1.0, float(cos_sim(s, k))))

    # ================================================================
    #  LAYER 2b: KEYWORD COVERAGE (40%)
    # ================================================================

    def _extract_key_concepts(self, key_norm, question_norm):
        """Extract important content words from key that aren't in the question."""
        q_doc = nlp(question_norm)
        q_words = {t.lemma_.lower() for t in q_doc
                   if not t.is_stop and not t.is_punct and len(t.text) > 1}
        q_raw = {t.text.lower() for t in q_doc
                 if not t.is_stop and not t.is_punct and len(t.text) > 1}
        q_all = q_words | q_raw

        k_doc = nlp(key_norm)
        concepts = []
        for tok in k_doc:
            if tok.is_stop or tok.is_punct or not tok.lemma_.strip():
                continue
            if len(tok.text) <= 1 and tok.pos_ != "NUM":
                continue
            lemma = tok.lemma_.lower()
            raw = tok.text.lower()

            # Skip if this word is just repeating the question
            in_question = (lemma in q_all or raw in q_all or
                           any(difflib.SequenceMatcher(None, lemma, qw).ratio() >= 0.85
                               for qw in q_all))

            weight = 0.3 if in_question else (5.0 if tok.pos_ in ("PROPN", "NUM") else 3.0)
            concepts.append({"lemma": lemma, "raw": raw, "pos": tok.pos_, "weight": weight})
        return concepts

    def _match_concept(self, concept, s_lemmas, s_raw_set, s_raw_list, s_doc):
        """Try to match a single concept against student answer. Returns 0-1."""
        lemma = concept["lemma"]
        raw = concept["raw"]

        # 1. Exact lemma/raw match
        if lemma in s_lemmas or raw in s_raw_set:
            return 1.0

        # 2. Common Synonyms (Class attribute)
        if lemma in self.COMMON_SYNONYMS:
            if any(syn in s_lemmas or syn in s_raw_set for syn in self.COMMON_SYNONYMS[lemma]):
                return 1.0
        # Check reverse mapping too
        for k, syns in self.COMMON_SYNONYMS.items():
            if lemma in syns and (k in s_lemmas or k in s_raw_set):
                return 1.0

        # 2. Numeric equivalence
        if raw.replace(".", "", 1).isdigit():
            try:
                tv = float(raw)
                for sr in s_raw_list:
                    if sr.replace(".", "", 1).isdigit():
                        sv = float(sr)
                        if tv != 0 and abs(tv - sv) / abs(tv) <= 0.05:
                            return 1.0
                        if abs(tv - sv) < 1e-7:
                            return 1.0
            except ValueError:
                pass

        # 3. Fuzzy match (typos)
        best = 0.0
        for sr in s_raw_list:
            r = difflib.SequenceMatcher(None, sr, raw).ratio()
            if r > best: best = r
            r2 = difflib.SequenceMatcher(None, sr, lemma).ratio()
            if r2 > best: best = r2
        if best >= 0.85:
            return best

        # 4. WordNet synonyms & negated antonyms
        syns = _get_synonyms(lemma)
        for sl in s_lemmas:
            if sl in syns:
                return 0.85
                
        # 4a. Negated antonym equivalence (e.g., 'hot' matched by 'not cold')
        antonyms = set()
        for ss in wordnet.synsets(lemma):
            for lem in ss.lemmas():
                for ant in lem.antonyms():
                    antonyms.add(ant.name().lower())
        
        if hasattr(self, 'COMMON_ANTONYMS'):
            for group in self.COMMON_ANTONYMS:
                if lemma in group:
                    antonyms.update(group - {lemma})
                    
        for ant in antonyms:
            if ant in s_lemmas or ant in s_raw_set:
                # Check if it's negated in the student answer
                for t in s_doc:
                    if t.lemma_.lower() == ant or t.text.lower() == ant:
                        if any(c.dep_ == 'neg' for c in t.children) or \
                           (t.i > 0 and s_doc[t.i-1].text in ('not', 'no')):
                            return 0.9  # "not cold" is an acceptable match for "hot"

        # 4b. Fraction/percentage equivalence
        # e.g., key has "0.5" and student has "half", or key has "0.25" and student has "quarter"
        _FRAC_EQUIV = {
            "0.5": {"half", "50"}, "50": {"half", "0.5"},
            "half": {"0.5", "50"}, "0.25": {"quarter", "25", "fourth"},
            "25": {"quarter", "0.25", "fourth"}, "quarter": {"0.25", "25"},
            "0.333333": {"third"}, "third": {"0.333333"},
            "0.75": {"three", "quarter"}, "75": {"0.75"},
        }
        if raw in _FRAC_EQUIV:
            for equiv in _FRAC_EQUIV[raw]:
                if equiv in s_raw_set or equiv in s_lemmas:
                    return 1.0

        # 5. Abbreviation matching
        for sw in s_raw_set | s_lemmas:
            if sw in ABBREVIATION_DB:
                expanded = set(ABBREVIATION_DB[sw].split())
                if lemma in expanded or raw in expanded:
                    return 1.0
        if raw in ABBREVIATION_DB:
            expanded = set(ABBREVIATION_DB[raw].split())
            for sw in s_raw_set | s_lemmas:
                if sw in expanded:
                    return 1.0

        return 0.0

    def _keyword_coverage(self, concepts, s_lemmas, s_raw_set, s_raw_list, s_doc):
        """Weighted coverage of key concepts found in student answer."""
        if not concepts:
            return 1.0
        total_w = sum(c["weight"] for c in concepts)
        if total_w == 0:
            return 1.0
        matched_w = 0.0
        for c in concepts:
            score = self._match_concept(c, s_lemmas, s_raw_set, s_raw_list, s_doc)
            matched_w += c["weight"] * score
        return min(1.0, matched_w / total_w)

    # ================================================================
    #  LAYER 2c: NUMBER/UNIT GATE
    # ================================================================

    def _number_check(self, student_norm, key_norm):
        """Check if numbers in key are correctly present in student answer.
        Handles unit conversions. Returns 0-1 multiplier."""
        k_nums = _extract_numbers_with_units(key_norm)
        if not k_nums:
            return 1.0  # No numbers to check

        s_nums = _extract_numbers_with_units(student_norm)
        if not s_nums:
            return 0.5  # Key has numbers, student has none

        _FRAC_EQUIV = {
            "0.5": {"50"}, "50": {"0.5"},
            "0.25": {"25"}, "25": {"0.25"},
            "0.75": {"75"}, "75": {"0.75"},
        }

        matched = 0
        for kv_str, ku in k_nums:
            kv = float(kv_str)
            best = 0.0
            for sv_str, su in s_nums:
                sv = float(sv_str)

                # Fraction/Percentage equivalence
                if kv_str in _FRAC_EQUIV and sv_str in _FRAC_EQUIV[kv_str]:
                    best = max(best, 1.0)
                    continue

                # Exact match
                if abs(kv - sv) < 1e-7:
                    if ku and su and ku != su:
                        kc, sc = _resolve_unit(ku), _resolve_unit(su)
                        if kc and sc and kc == sc:
                            best = max(best, 1.0)
                        elif not kc and not sc:
                            best = max(best, 1.0)
                        else:
                            best = max(best, 0.3)
                    else:
                        best = max(best, 1.0)
                    continue

                # Rounding tolerance (same or no units)
                if not ku or not su or ku == su:
                    if kv != 0:
                        err = abs(kv - sv) / abs(kv)
                        if err <= 0.05: best = max(best, 1.0); continue
                        if err <= 0.15: best = max(best, 0.8); continue

                # Unit conversion
                kc, sc = _resolve_unit(ku), _resolve_unit(su)
                if kc and sc and kc != sc:
                    kb = _convert_to_base(kv, kc)
                    sb = _convert_to_base(sv, sc)
                    if kb and sb and kb[0] == sb[0]:
                        if kb[1] == 0 and sb[1] == 0:
                            best = max(best, 1.0)
                        elif kb[1] != 0:
                            ratio = abs(kb[1] - sb[1]) / abs(kb[1])
                            if ratio <= 0.05: best = max(best, 1.0)
                            elif ratio <= 0.15: best = max(best, 0.8)

            matched += best

        return 0.1 + 0.9 * (matched / len(k_nums))

    # ================================================================
    #  LAYER 3: PENALTY GATES (only subtract, never add)
    # ================================================================

    # Words that are inherently negative in meaning
    NEGATIVE_ADJECTIVES = {"impossible", "optional", "unnecessary", "unlikely",
                           "incorrect", "wrong", "false", "absent"}
    POSITIVE_COUNTERPARTS = {"impossible": "possible", "optional": "mandatory",
                             "unnecessary": "necessary", "unlikely": "likely",
                             "incorrect": "correct", "wrong": "right",
                             "false": "true", "absent": "present"}

    def _negation_penalty(self, student_norm, key_norm):
        """Scope-aware negation detection. Returns 0-1."""
        s_doc = nlp(student_norm)
        k_doc = nlp(key_norm)

        # e.g., "not optional" = mandatory, "not impossible" = possible
        s_text = student_norm.lower()
        k_text = key_norm.lower()
        for neg_adj, pos_adj in self.POSITIVE_COUNTERPARTS.items():
            if re.search(r'\bnot\s+' + neg_adj, s_text) and pos_adj in k_text:
                return 1.0
            if re.search(r'\bnot\s+' + neg_adj, k_text) and pos_adj in s_text:
                return 1.0
            if re.search(r'\bnot\s+' + neg_adj, s_text) and re.search(r'\bnot\s+' + neg_adj, k_text):
                return 1.0

        # Handle "not + antonym = positive" (e.g., "not cold" = "hot")
        # Use simple string matching for reliability
        for group in self.COMMON_ANTONYMS:
            for w1 in group:
                for w2 in group:
                    if w1 != w2:
                        if re.search(r'\bnot\s+' + w1, s_text) and w2 in k_text:
                            return 1.0
                        if re.search(r'\bnot\s+' + w1, k_text) and w2 in s_text:
                            return 1.0

        # Handle WordNet antonyms similarly
        for kw in k_doc:
            if kw.pos_ in ('ADJ', 'NOUN', 'VERB'):
                for ss in wordnet.synsets(kw.lemma_.lower()):
                    for lem in ss.lemmas():
                        for ant in lem.antonyms():
                            if re.search(r'\bnot\s+' + ant.name().lower(), s_text):
                                return 1.0

        def _get_polarity(doc):
            # If the sentence starts with a rejection, the overall answer is negative.
            if any(tok.text == 'no' and tok.dep_ == 'intj' for tok in doc):
                return -1

            # Count grammatical negations (dep='neg') separately from negative adjectives.
            # Multiple negative adjectives ("false and incorrect") reinforce the same
            # polarity — they don't cancel each other like double negations.
            gram_negs = sum(1 for tok in doc if tok.dep_ == 'neg')
            has_neg_adj = any(tok.text in self.NEGATIVE_ADJECTIVES for tok in doc)
            if has_neg_adj and gram_negs == 0:
                return -1  # negative adjective, no grammatical negation
            if gram_negs % 2 == 1:
                return -1  # odd number of negations
            return 1

        s_pol = _get_polarity(s_doc)
        k_pol = _get_polarity(k_doc)

        if s_pol != k_pol:
            return 0.1
        return 1.0

    # Common grading antonyms that WordNet sometimes misses or classifies poorly
    COMMON_ANTONYMS = [
        {"cold", "warm"}, {"cold", "hot"}, 
        {"increase", "decrease"}, {"increase", "drop"}, {"rise", "drop"}, {"rise", "fall"},
        {"high", "low"}, {"fast", "slow"}, {"true", "false"}, 
        {"right", "wrong"}, {"correct", "incorrect"}, 
        {"positive", "negative"},
        {"absorb", "release"}, {"absorb", "emit"},
        {"consume", "generate"}, {"consume", "produce"},
        {"mandatory", "optional"}
    ]

    def _antonym_penalty(self, student_norm, key_norm):
        """Detect if student uses antonyms of key concepts. Returns 0-1."""
        s_doc = nlp(student_norm)
        k_doc = nlp(key_norm)

        s_content = {t.lemma_.lower() for t in s_doc
                     if not t.is_stop and not t.is_punct and t.pos_ in ("ADJ", "VERB", "NOUN")}
        k_content = {t.lemma_.lower() for t in k_doc
                     if not t.is_stop and not t.is_punct and t.pos_ in ("ADJ", "VERB", "NOUN")}

        for kw in k_content:
            k_antonyms = set()
            for ss in wordnet.synsets(kw):
                for lemma in ss.lemmas():
                    for ant in lemma.antonyms():
                        k_antonyms.add(ant.name().lower())
            
            # Add custom common antonyms
            for group in self.COMMON_ANTONYMS:
                if kw in group:
                    k_antonyms.update(group - {kw})

            overlap = k_antonyms & s_content
            if overlap:
                # ── CONVERSE VERB PROTECTION ──
                # If the key has "won" and student has "lost", this is an antonym 
                # in WordNet, but if they are part of a converse verb group (win/lose),
                # we SHOULD NOT penalize them as a contradiction, because the 
                # entity/role analysis will handle the truth value.
                is_converse = False
                for ant_word in overlap:
                    for pos_set, neg_set in self.CONVERSE_VERBS:
                        if (kw in pos_set and ant_word in neg_set) or (kw in neg_set and ant_word in pos_set):
                            is_converse = True
                            break
                    if is_converse: break
                
                if is_converse:
                    continue # Skip antonym penalty for converse verbs

                # Make sure the antonym isn't negated in context
                # e.g. "not cold" shouldn't trigger antonym of "hot"
                for ant_word in overlap:
                    negated = False
                    for tok in s_doc:
                        if tok.lemma_.lower() == ant_word or tok.text.lower() == ant_word:
                            for child in tok.children:
                                if child.dep_ == 'neg':
                                    negated = True
                            if tok.i > 0 and s_doc[tok.i - 1].text in ('not', 'no'):
                                negated = True
                    if not negated:
                        return 0.15  # Unnegated antonym = contradiction
        return 1.0

    def _gaming_penalty(self, student_text, student_norm, key_norm):
        """Detect keyword stuffing, gibberish, or 'I don't know'. Returns 0-1."""
        s_doc = nlp(student_norm)
        k_doc = nlp(key_norm)

        # Check for "I don't know" style answers
        idk = re.search(r"\b(i\s+don'?t\s+know|i\s+do\s+not\s+know|no\s+idea)\b",
                        student_text.lower())

        # Check for grammatical structure (has verbs?)
        has_verb = any(t.pos_ in ("VERB", "AUX") for t in s_doc)
        content_words = [t for t in s_doc if not t.is_stop and not t.is_punct]

        # Keyword stuffing: high content density with no grammar
        if len(content_words) >= 4 and not has_verb:
            content_ratio = len(content_words) / max(len(s_doc), 1)
            if content_ratio > 0.8:
                return 0.15  # Likely keyword stuffing

        # "I don't know" but has some content
        if idk:
            remaining = re.sub(r"\bi\s+don'?t\s+know\s*(but)?\b", "", student_text.lower()).strip()
            if len(remaining.split()) < 3:
                return 0.1  # Basically said nothing
            return 0.5  # Said IDK but added something

        # Keyword density check (gaming detection)
        # If student answer is long but has very few of the key concepts, it's likely fluff
        k_concepts = self._extract_key_concepts(key_norm, "")
        s_lemmas = {t.lemma_.lower() for t in s_doc if not t.is_stop}
        s_raw_set = {t.text.lower() for t in s_doc}
        matched_count = sum(1 for c in k_concepts if self._match_concept(c, s_lemmas, s_raw_set, student_norm.split(), s_doc) > 0.7)
        if len(s_doc) > 15 and matched_count < 2:
            return 0.3

        return 1.0

    # Common synonyms that WordNet might miss or categorize differently
    COMMON_SYNONYMS = {
        "subject": {"participant", "patient", "individual", "person"},
        "participant": {"subject", "member", "person"},
        "improvement": {"better", "increase", "advance", "betterment"},
        "improve": {"better", "enhance"},
        "boil": {"boiling", "heat", "evaporate"},
        "boiling": {"boil", "hot"},
        "co2": {"carbon dioxide"},
        # Unit abbreviations only — never collapse different magnitudes
        # (a kilometer is 1000 meters; the number gate handles magnitude).
        "kilometer": {"km"},
        "kilometers": {"km"},
        "meter": {"m"},
        "meters": {"m"},
        "km": {"kilometer", "kilometers"},
        "m": {"meter", "meters"},
        "cause": {"lead", "result", "trigger", "make"},
        "happen": {"occur", "take place"},
        "photosynthesis": {"plants", "process", "produce"},
        "byproduct": {"waste", "result", "side effect"},
        "erosion": {"erode", "washing away", "removal"},
        "topsoil": {"top layer", "surface soil"},
        "glucose": {"sugar", "food", "energy"},
        "feline": {"cat"},
        "floor covering": {"rug", "carpet"},
        "rug": {"floor covering", "carpet"},
        "span": {"be", "long", "measure"},
        "attendance": {"attend", "be there"},
        "win": {"won", "beat", "defeat", "success", "victory"},
        "won": {"win", "beat", "defeat", "success", "victory"},
        "lose": {"lost", "failure", "defeat"},
        "lost": {"lose", "failure", "defeat"},
    }

    # ── Converse verb groups: verbs where AGENT/PATIENT swap meaning ──
    # ... (rest same)
    # ── Converse verb groups: verbs where AGENT/PATIENT swap meaning ──
    # "A won from B" ↔ "B lost to A" ↔ "B was defeated by A"
    # Within each group, verbs in the first set are "agent-positive" (the nsubj benefits)
    # and verbs in the second set are "agent-negative" (the nsubj suffers)
    CONVERSE_VERBS = [
        ({"win", "won", "beat", "defeat", "defeated", "conquer", "conquered", "overcome", "overcame", "outperform", "outperformed"},
         {"lose", "lost", "fall", "fell", "surrender", "surrendered", "succumb", "succumbed"}),
        ({"teach", "taught", "instruct", "instructed", "educate", "educated"},
         {"learn", "learnt", "learned", "study", "studied"}),
        ({"sell", "sold", "export", "exported"},
         {"buy", "bought", "import", "imported", "purchase", "purchased"}),
        ({"give", "gave", "given", "donate", "donated", "lend", "lent"},
         {"receive", "received", "borrow", "borrowed", "accept", "accepted"}),
        ({"lead", "led", "guide", "guided"},
         {"follow", "followed"}),
    ]

    def _extract_semantic_roles(self, doc):
        """Extract AGENT (doer) and PATIENT (receiver) from a sentence
        using spaCy dependency parsing. Works for both active and passive voice.
        Falls back to positional heuristics when dep parse is incomplete.
        
        Returns: (agent_str, patient_str, root_verb_lemma, is_passive)
        """
        agent = []
        patient = []
        root_verb = None
        # Find the root verb (spaCy sometimes misclassifies verbs as NOUNs, e.g., "won")
        known_verbs = set()
        for pos_set, neg_set in self.CONVERSE_VERBS:
            known_verbs.update(pos_set)
            known_verbs.update(neg_set)
            
        # Add past tense forms since lemma of a misparsed verb is often the raw word
        known_verbs.update({"won", "lost", "defeated", "conquered", "overcame", 
                            "outperformed", "taught", "educated", "sold", "exported",
                            "bought", "imported", "purchased", "gave", "donated", "lent",
                            "received", "borrowed", "accepted", "guided", "followed"})

        for tok in doc:
            if tok.dep_ == "ROOT" and (tok.pos_ in ("VERB", "AUX") or tok.lemma_.lower() in known_verbs or tok.text.lower() in known_verbs):
                root_verb = tok
                break
        
        if not root_verb:
            for tok in doc:
                if tok.pos_ in ("VERB", "AUX") or tok.lemma_.lower() in known_verbs or tok.text.lower() in known_verbs:
                    root_verb = tok
                    break

        if not root_verb:
            return ("", "", "", False)

        is_passive = any(c.dep_ == "auxpass" for c in root_verb.children)

        def _collect_compound(tok):
            """Collect compound noun phrases, stripping punctuation."""
            parts = []
            for child in tok.children:
                if child.dep_ in ("compound", "flat", "flat:name"):
                    parts.extend(_collect_compound(child))
            clean = tok.text.lower().strip('.,!?;: ')
            if clean:
                parts.append(clean)
            return parts

        for child in root_verb.children:
            if child.dep_ == "nsubj":
                agent.extend(_collect_compound(child))
            elif child.dep_ == "nsubjpass":
                patient.extend(_collect_compound(child))
                is_passive = True
            elif child.dep_ == "dobj":
                patient.extend(_collect_compound(child))
            elif child.dep_ == "agent":
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        agent.extend(_collect_compound(grandchild))
            elif child.dep_ == "prep":
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        patient.extend(_collect_compound(grandchild))

        # ── Positional fallback ──
        if not agent or not patient:
            verb_idx = root_verb.i
            before_verb = []
            after_verb = []
            for tok in doc:
                if tok.i == verb_idx:
                    continue
                clean = tok.text.lower().strip('.,!?;: ')
                if not clean or tok.pos_ in ("AUX", "DET", "PUNCT", "ADP", "PART"):
                    # But keep single letters that look like entity labels
                    if len(clean) == 1 and clean.isalpha():
                        pass  # Keep it
                    else:
                        continue
                if tok.i < verb_idx:
                    before_verb.append(clean)
                else:
                    after_verb.append(clean)
            
            if is_passive:
                if not patient and before_verb:
                    patient = before_verb
                if not agent and after_verb:
                    agent = after_verb
            else:
                if not agent and before_verb:
                    agent = before_verb
                if not patient and after_verb:
                    patient = after_verb

        agent_str = " ".join(agent).strip()
        patient_str = " ".join(patient).strip()
        return (agent_str, patient_str, root_verb.lemma_.lower(), is_passive)

    def _get_verb_polarity(self, verb_lemma):
        """Determine if verb is 'agent-positive' (+1), 'agent-negative' (-1), or neutral (0)."""
        for pos_set, neg_set in self.CONVERSE_VERBS:
            if verb_lemma in pos_set:
                return 1
            if verb_lemma in neg_set:
                return -1
        return 0

    def _entity_penalty(self, student_text, key_text):
        """General semantic role analysis gate. Detects:
        1. Wrong proper nouns (Einstein vs Newton)
        2. Role reversals via dependency-based AGENT/PATIENT extraction
        3. Converse verb swaps (win ↔ lose)
        Returns 0-1."""
        s_doc = nlp(student_text.lower())
        k_doc = nlp(key_text.lower())

        # ── Check 1: Wrong proper nouns ──
        # Only consider multi-character proper nouns (single letters are unreliable)
        s_propns = {t.lemma_.lower() for t in s_doc if t.pos_ == "PROPN" and len(t.text) > 1}
        k_propns = {t.lemma_.lower() for t in k_doc if t.pos_ == "PROPN" and len(t.text) > 1}
        if k_propns and s_propns and not (k_propns & s_propns):
            return 0.1

        # ── Check 2: Semantic role analysis ──
        k_agent, k_patient, k_verb, k_passive = self._extract_semantic_roles(k_doc)
        s_agent, s_patient, s_verb, s_passive = self._extract_semantic_roles(s_doc)

        # Only proceed if both sentences have identifiable agent AND patient
        if not (k_agent and k_patient and s_agent and s_patient):
            return 1.0

        # Check if the same entities appear in both sentences
        # Create token sets to check if they share ANY entity words
        k_all_words = set(k_agent.split() + k_patient.split())
        s_all_words = set(s_agent.split() + s_patient.split())
        if not (k_all_words & s_all_words):
            return 1.0  # Different entities entirely, can't compare roles

        # ── Check 3: Copular / Symmetric Verbs ──
        # If the verb is 'be' or 'equal', check if roles are symmetric.
        # Identity (A is B == B is A) works for names/capitals, but not for relations.
        NON_SYMMETRIC_RELATIONS = {"father", "mother", "son", "daughter", "parent", "child", 
                                   "boss", "leader", "cause", "result", "source"}
        
        is_copular = k_verb in ("be", "equal", "mean", "represent") or s_verb in ("be", "equal", "mean", "represent")
        
        if is_copular:
            # If it's a non-symmetric relation, we MUST check direction
            has_relation = any(rel in key_text or rel in student_text for rel in NON_SYMMETRIC_RELATIONS)
            if not has_relation:
                return 1.0 # Safe to assume symmetric identity (e.g. Paris = Capital)

        # ── Check 4: Converse verb handling ──
        k_polarity = self._get_verb_polarity(k_verb)
        s_polarity = self._get_verb_polarity(s_verb)

        # If verbs are converses (win ↔ lose), swap student roles for comparison
        if k_polarity != 0 and s_polarity != 0 and k_polarity != s_polarity:
            s_agent, s_patient = s_patient, s_agent

        # ── Compare roles ──
        # Compare full phrases (e.g. "team a" == "team a")
        agent_match = (k_agent == s_agent) or (k_agent in s_agent) or (s_agent in k_agent)
        patient_match = (k_patient == s_patient) or (k_patient in s_patient) or (s_patient in k_patient)

        if agent_match and patient_match:
            # If structure changed (passive voice or converse verbs), SBERT/Keyword 
            # coverage often drop. We return a boost to compensate.
            structure_changed = (k_polarity != 0 and s_polarity != 0 and k_polarity != s_polarity) or \
                               (k_passive != s_passive)
            if structure_changed:
                return 1.4
            return 1.0  # Roles align correctly

        # Check if roles are swapped
        agent_as_patient = (k_agent == s_patient) or (k_agent in s_patient) or (s_patient in k_agent)
        patient_as_agent = (k_patient == s_agent) or (k_patient in s_agent) or (s_agent in k_patient)

        if agent_as_patient and patient_as_agent:
            return 0.1  # Clear role reversal

        if agent_match or patient_match:
            return 0.7  # Partial mismatch

        return 1.0

    # ================================================================
    #  SCORING: Mark Assignment
    # ================================================================

    @staticmethod
    def _to_marks(score):
        """Map 0.0-1.0 to 0-10 marks."""
        return max(0, min(10, round(score * 10)))

    # ================================================================
    #  PUBLIC API
    # ================================================================

    def grade_answer(self, student_answer, key_answer, question_text, preprocess_fn=None):
        """Grade a student answer against the key. Returns {"marks": int}."""

        # ── Layer 1: Normalise ──
        cleaned = self._clean(student_answer)
        student_norm = _normalise_text(cleaned)
        key_norm = _normalise_text(key_answer)
        question_norm = _normalise_text(question_text) if question_text else ""

        # ── Layer 2a: SBERT semantic similarity ──
        sbert = self._sbert_score(student_norm, key_norm)

        return self._score_pair(student_answer, key_answer, student_norm, key_norm, question_norm, sbert)

    def grade_answers_batch(self, items):
        """Grade many (student, key, question) triples in one shot.

        The SBERT encodes for every student answer and every key are computed in
        two batched forward passes (instead of 2 calls per question), which is
        the bulk of the cost. Everything else (spaCy parse, penalty gates) is
        per-item but cheap.

        items: list of dicts with keys student_answer, key_answer, question_text.
        Returns a list of {"marks": int} aligned with items.
        """
        prepared = []
        for it in items:
            raw_s = it.get('student_answer', '') or ''
            raw_k = it.get('key_answer', '') or ''
            cleaned = self._clean(raw_s)
            s_norm = _normalise_text(cleaned)
            k_norm = _normalise_text(raw_k)
            q_norm = _normalise_text(it.get('question_text', '')) if it.get('question_text') else ""
            prepared.append((raw_s, raw_k, s_norm, k_norm, q_norm))

        if not prepared:
            return []

        # Two batched encode calls — the whole point of this method.
        s_embs = self.model.encode([p[2] for p in prepared], convert_to_tensor=True)
        k_embs = self.model.encode([p[3] for p in prepared], convert_to_tensor=True)

        results = []
        for i, (raw_s, raw_k, s_norm, k_norm, q_norm) in enumerate(prepared):
            sbert = max(0.0, min(1.0, float(cos_sim(s_embs[i], k_embs[i]))))
            results.append(self._score_pair(raw_s, raw_k, s_norm, k_norm, q_norm, sbert))
        return results

    def _score_pair(self, student_answer, key_answer, student_norm, key_norm, question_norm, sbert):
        """Compute marks given normalised texts and a precomputed SBERT score.
        Shared by grade_answer (single) and grade_answers_batch (bulk)."""

        # Build token sets for keyword matching
        s_doc = nlp(student_norm)
        s_lemmas = {t.lemma_.lower() for t in s_doc
                    if not t.is_stop and not t.is_punct and t.lemma_.strip()}
        s_raw_list = get_raw_tokens(student_norm)
        s_raw_set = set(s_raw_list)

        # Rescue abbreviations that spaCy might strip
        for t in s_doc:
            w = t.text.lower().strip()
            if w and w in ABBREVIATION_DB:
                s_lemmas.add(w)
                s_raw_set.add(w)

        # ── Layer 2: Dual Scoring (SBERT score passed in) ──

        # 2b. Keyword coverage
        concepts = self._extract_key_concepts(key_norm, question_norm)
        coverage = self._keyword_coverage(concepts, s_lemmas, s_raw_set, s_raw_list, s_doc)

        # 2c. Number/unit check
        num_score = self._number_check(student_norm, key_norm)

        # Unit/number equivalence credit: the number gate already verifies numeric
        # values *including unit conversions* (e.g. 1.5 km == 1500 m). When it
        # passes, don't let numeric concepts the keyword layer couldn't
        # string-match (1.5 vs 1500) drag coverage down — credit them as covered.
        if num_score >= 0.95 and concepts:
            num_weight = sum(c["weight"] for c in concepts if c["pos"] == "NUM")
            total_weight = sum(c["weight"] for c in concepts)
            if total_weight > 0 and num_weight > 0:
                coverage = min(1.0, coverage + num_weight / total_weight)

        # Combine: SBERT 50% + Coverage 40% + Number accuracy 10%
        base_score = 0.50 * sbert + 0.40 * coverage + 0.10 * num_score

        # Hard floor: if both SBERT and coverage are near zero, it's wrong
        if sbert < 0.15 and coverage < 0.1:
            return {"marks": 0}

        # ── Layer 3: Penalties (computed before combining) ──
        neg = self._negation_penalty(student_norm, key_norm)
        ant = self._antonym_penalty(student_norm, key_norm)
        game = self._gaming_penalty(student_answer, student_norm, key_norm)
        ent = self._entity_penalty(student_answer, key_answer)

        # Worst-gate-wins: take the minimum penalty, BUT preserve entity boost if applicable
        penalty = min(neg, ant, game, min(ent, 1.0))

        # If no severe penalties applied and we earned a boost, apply it (capped at 1.15)
        if penalty >= 1.0 and ent > 1.0:
            penalty = min(ent, 1.15)

        # If a contradiction was detected, cap SBERT contribution
        if penalty < 0.5:
            sbert = min(sbert, 0.3)
            base_score = 0.50 * sbert + 0.40 * coverage + 0.10 * num_score

        # If numbers are present in key AND student, but student got them wrong,
        # apply a penalty (but don't penalize harshly if they just omitted a number)
        k_nums = _extract_numbers_with_units(key_norm)
        s_nums = _extract_numbers_with_units(student_norm)
        if k_nums and s_nums and num_score < 0.8:
            penalty = min(penalty, 0.6)  # Wrong numbers matter

        final = base_score * penalty
        return {"marks": self._to_marks(final)}
