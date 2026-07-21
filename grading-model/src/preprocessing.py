import re
import spacy
from nltk.corpus import wordnet

nlp = spacy.load("en_core_web_sm")

# Common science/domain abbreviation expansions
ACRONYMS = {
    "dna": "deoxyribonucleic acid",
    "rna": "ribonucleic acid",
    "atp": "adenosine triphosphate",
    "co2": "carbon dioxide",
    "h2o": "water",
    "o2": "oxygen",
    "cpu": "central processing unit",
    "ram": "random access memory",
    "os": "operating system",
    "uv": "ultraviolet",
}

# ======================================================================
#  NUMBER-WORD → DIGIT CONVERSION
# ======================================================================

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SCALES = {
    "hundred": 100, "thousand": 1_000, "million": 1_000_000,
    "billion": 1_000_000_000, "trillion": 1_000_000_000_000,
}

# Words that are part of number expressions
_ALL_NUM_WORDS = set(_ONES) | set(_TENS) | set(_SCALES) | {"and", "a"}

# Fraction words → decimal value
_FRACTION_WORDS = {
    "half": 0.5, "halve": 0.5,
    "quarter": 0.25,
    "third": 1/3,
    "fourth": 0.25,
    "fifth": 0.2,
    "sixth": 1/6,
    "seventh": 1/7,
    "eighth": 0.125,
    "ninth": 1/9,
    "tenth": 0.1,
    "hundredth": 0.01,
    "thousandth": 0.001,
}


def _words_to_number(word_list):
    """Convert a list of number words to an integer.
    E.g. ['twenty', 'two'] → 22, ['one', 'hundred', 'and', 'five'] → 105.
    Returns None if the words don't form a valid number."""
    if not word_list:
        return None

    # Filter out 'and' and 'a'
    words = [w for w in word_list if w not in ("and", "a")]
    if not words:
        return None

    # All words must be recognised number words
    for w in words:
        if w not in _ONES and w not in _TENS and w not in _SCALES:
            return None

    current = 0
    result = 0

    for w in words:
        if w in _ONES:
            current += _ONES[w]
        elif w in _TENS:
            current += _TENS[w]
        elif w in _SCALES:
            scale = _SCALES[w]
            if current == 0:
                current = 1
            if scale >= 1000:
                result += current * scale
                current = 0
            else:
                current *= scale

    result += current
    return result if result > 0 or "zero" in word_list else None


def normalise_number_words(text):
    """Replace English number words with their digit equivalents.
    'twenty two' → '22', 'one hundred and five' → '105'."""
    words = text.lower().split()
    result = []
    i = 0

    while i < len(words):
        # Try to build a number-word sequence
        if words[i] in _ALL_NUM_WORDS and words[i] not in ("and", "a"):
            num_words = []
            j = i
            while j < len(words) and words[j] in _ALL_NUM_WORDS:
                num_words.append(words[j])
                j += 1

            number = _words_to_number(num_words)
            if number is not None:
                result.append(str(number))
                i = j
                continue

        # Check for fraction words
        if words[i] in _FRACTION_WORDS:
            val = _FRACTION_WORDS[words[i]]
            # Check if preceded by a number for "two thirds" etc.
            if result and result[-1].replace(".", "").replace("-", "").isdigit():
                multiplier = float(result[-1])
                result[-1] = str(round(multiplier * val, 6))
            elif i > 0 and words[i-1] in ("a", "an", "one"):
                # "a half", "one half"
                if result and result[-1] in ("a", "an", "one"):
                    result[-1] = str(round(val, 6))
                else:
                    result.append(str(round(val, 6)))
            else:
                result.append(str(round(val, 6)))
            i += 1
            continue

        result.append(words[i])
        i += 1

    return " ".join(result)


def normalise_numeric_formatting(text):
    """Normalise numeric formats:
    '1,000' → '1000', '1 000' → '1000'."""
    # Remove commas between digits: "1,000,000" → "1000000"
    text = re.sub(r'(\d),(\d)', r'\1\2', text)
    # Repeat for multi-comma numbers
    text = re.sub(r'(\d),(\d)', r'\1\2', text)
    return text


def normalise_fractions(text):
    """Convert fraction notation and percentages to decimal: 
    '1/2' → '0.5', '50%' → '0.5', '20 percent' → '0.2'."""
    
    # Simple fractions: digit/digit
    def _replace_fraction(m):
        num = float(m.group(1))
        den = float(m.group(2))
        if den == 0: return m.group(0)
        return str(round(num / den, 6))

    # Percentages: digit% or digit percent
    def _replace_percent(m):
        num = float(m.group(1))
        return str(round(num / 100.0, 6))

    text = re.sub(r'\b(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\b', _replace_fraction, text)
    text = re.sub(r'\b(\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)', _replace_percent, text)
    return text


# ======================================================================
#  BRITISH ↔ AMERICAN SPELLING NORMALISATION
# ======================================================================

# Map British spellings → American (we normalise everything to American)
_BRITISH_TO_AMERICAN = {
    # -our → -or
    "colour": "color", "colours": "colors",
    "honour": "honor", "honours": "honors",
    "behaviour": "behavior", "behaviours": "behaviors",
    "favour": "favor", "favours": "favors",
    "labour": "labor", "labours": "labors",
    "neighbour": "neighbor", "neighbours": "neighbors",
    "humour": "humor",
    "vapour": "vapor",
    "rumour": "rumor",
    "tumour": "tumor",
    "savour": "savor",
    "armour": "armor",
    "harbour": "harbor",
    # -ise → -ize
    "organise": "organize", "organised": "organized", "organising": "organizing",
    "organisation": "organization", "organisations": "organizations",
    "realise": "realize", "realised": "realized", "realising": "realizing",
    "recognise": "recognize", "recognised": "recognized",
    "specialise": "specialize", "specialised": "specialized",
    "centralise": "centralize", "centralised": "centralized",
    "utilise": "utilize", "utilised": "utilized",
    "maximise": "maximize", "minimise": "minimize",
    "optimise": "optimize", "optimised": "optimized",
    "characterise": "characterize",
    "summarise": "summarize",
    "analyse": "analyze",
    "paralyse": "paralyze",
    # -re → -er
    "centre": "center", "centres": "centers",
    "metre": "meter", "metres": "meters",
    "litre": "liter", "litres": "liters",
    "fibre": "fiber", "fibres": "fibers",
    "theatre": "theater", "theatres": "theaters",
    "kilometre": "kilometer", "kilometres": "kilometers",
    "centimetre": "centimeter", "centimetres": "centimeters",
    "millimetre": "millimeter", "millimetres": "millimeters",
    # -ence → -ense
    "defence": "defense",
    "offence": "offense",
    "licence": "license",
    # -ogue → -og
    "catalogue": "catalog",
    "dialogue": "dialog",
    "analogue": "analog",
    # Misc
    "grey": "gray",
    "tyre": "tire", "tyres": "tires",
    "plough": "plow",
    "aluminium": "aluminum",
    "aeroplane": "airplane",
    "programme": "program", "programmes": "programs",
    "maths": "math",
    "draught": "draft",
    "cheque": "check",
    "storey": "story", "storeys": "stories",
    "kerb": "curb",
    "manoeuvre": "maneuver",
    "sceptical": "skeptical",
    "ageing": "aging",
    "judgement": "judgment",
    "acknowledgement": "acknowledgment",
    "cancelled": "canceled",
    "travelling": "traveling",
    "modelling": "modeling",
    "labelling": "labeling",
    "focussed": "focused",
    "learnt": "learned",
    "burnt": "burned",
    "spelt": "spelled",
    "dreamt": "dreamed",
}

# Build reverse map too (American → use as-is, so we just need British → American)
# We also want to match "color" if key has "colour", so add American → American
_SPELLING_MAP = dict(_BRITISH_TO_AMERICAN)
# Add reverse so both directions normalise to the same canonical form
for brit, amer in _BRITISH_TO_AMERICAN.items():
    _SPELLING_MAP[brit] = amer
    # American spelling stays as-is (no mapping needed)


def normalise_spelling(text):
    """Normalise British spellings to American equivalents."""
    words = text.split()
    return " ".join(_SPELLING_MAP.get(w, w) for w in words)


# ======================================================================
#  EXISTING FUNCTIONS (updated)
# ======================================================================

def _expand_acronyms(text):
    """Replace known acronyms with their full form."""
    words = text.split()
    expanded = [ACRONYMS.get(w, w) for w in words]
    return " ".join(expanded)


def _get_wordnet_synonyms(lemma):
    """Return a set of synonyms for a word from WordNet (same POS only)."""
    synonyms = set()
    for syn in wordnet.synsets(lemma):
        for name in syn.lemma_names():
            cleaned = name.replace("_", " ").lower()
            if cleaned != lemma:
                synonyms.add(cleaned)
    return synonyms


def _detect_proper_nouns(text, key_text=None):
    """
    Detect proper nouns and entities. If key_text is provided, 
    use its casing as a gold standard for what should be protected.
    """
    protected = set()
    
    # Process the text provided (usually the student answer)
    doc = nlp(text)
    for token in doc:
        if token.pos_ == "PROPN":
            protected.add(token.text.lower())
    for ent in doc.ents:
        for word in ent.text.lower().split():
            protected.add(word)

    # If we have a key answer, protect EVERYTHING that is capitalized there
    if key_text:
        key_doc = nlp(key_text)
        for token in key_doc:
            # If word is capitalized and not at start of sentence (or if it's a PROPN)
            if token.text[0].isupper() or token.pos_ == "PROPN":
                protected.add(token.text.lower())
        for ent in key_doc.ents:
            for word in ent.text.lower().split():
                protected.add(word)

    # Manual protection for words that lemmatize poorly (e.g. 'mars' -> 'mar')
    for word in ["mars", "physics", "species", "series", "gas", "lens"]:
        if word in text.lower() or (key_text and word in key_text.lower()):
            protected.add(word)

    return protected


def preprocess(text, expand_synonyms=False, key_text=None):
    """
    Full preprocessing pipeline:
    (key_text is used to protect potential proper nouns via casing)
    """
    # Step 0a: Normalise numeric formatting (before anything strips commas)
    text = normalise_numeric_formatting(text)

    # Step 0b: Normalise fractions (1/2 → 0.5)
    text = normalise_fractions(text)

    # Step 1: Detect proper nouns
    protected = _detect_proper_nouns(text, key_text)

    # Step 2: Lowercase + clean
    text = text.lower()

    # Step 2a: Normalise number words BEFORE stripping non-alphanum
    # (needs spaces and words intact)
    text = normalise_number_words(text)

    # Step 2b: Normalise British→American spelling
    text = normalise_spelling(text)

    text = re.sub(r'[^a-z0-9.\s]', ' ', text)  # keep decimal points
    text = re.sub(r'(?<!\d)\.(?!\d)', ' ', text)  # remove non-numeric periods
    text = re.sub(r'\s+', ' ', text).strip()

    # Step 3: Expand acronyms
    text = _expand_acronyms(text)

    # Step 4: Lemmatize, but protect proper nouns
    doc = nlp(text)
    lemmas = []
    for token in doc:
        if not token.is_stop and not token.is_punct and token.lemma_.strip():
            if token.text in protected:
                # Keep the original word form, don't lemmatize
                lemmas.append(token.text)
            else:
                lemmas.append(token.lemma_)

    if not expand_synonyms:
        return " ".join(lemmas)

    # Synonym expansion: append WordNet synonyms for each lemma
    enriched = list(lemmas)
    for lemma in lemmas:
        syns = _get_wordnet_synonyms(lemma)
        for syn in list(syns)[:3]:
            if syn not in enriched and syn != lemma:
                enriched.append(syn)

    return " ".join(enriched)


def preprocess_key(text):
    """Preprocess an answer key without synonym expansion."""
    return preprocess(text, expand_synonyms=False)


def get_raw_tokens(text):
    """
    Extract raw content tokens (lowercased, no stop words, no punct)
    WITHOUT lemmatization. Used for fuzzy matching before lemmatization
    destroys typos.

    Now also normalises number words and fractions first.
    """
    text = normalise_numeric_formatting(text)
    text = normalise_fractions(text)
    text_clean = text.lower()
    text_clean = normalise_number_words(text_clean)
    text_clean = normalise_spelling(text_clean)
    text_clean = re.sub(r'[^a-z0-9.\s]', ' ', text_clean)
    text_clean = re.sub(r'(?<!\d)\.(?!\d)', ' ', text_clean)
    text_clean = re.sub(r'\s+', ' ', text_clean).strip()
    doc = nlp(text_clean)
    return [t.text for t in doc if not t.is_stop and not t.is_punct and t.text.strip()]
