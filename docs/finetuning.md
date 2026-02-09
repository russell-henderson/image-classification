**Better: support both formats (new slot format preferred, fallback to the old format).**

Reason: you get the improved descriptions immediately, without breaking anything that already works (tests, older DB rows, cached metadata, or any other callers). You can roll it out safely and still accept older structured outputs.

Here’s the exact plan.

---

## Step 1: Add the slot prompt (preferred) and keep the old prompt (fallback)

In `src/core/classifier.py` define both:

```python
OLLAMA_SLOT_PROMPT = """
Output EXACTLY these 7 lines. No extra text.

SUBJECT: <main subject(s) in 3-10 words>
SETTING: <where it is / environment in 6-14 words>
COLORS: <2-5 color words, comma-separated>
LIGHTING: <lighting in 3-10 words>
MOOD: <mood in 2-8 words>
STYLE: <art style in 2-10 words>
TAGS: <6-10 comma-separated nouns, no colors>
""".strip()

OLLAMA_OLD_PROMPT = """
Output EXACTLY 5 lines. No extra text.

CAPTION: <max 20 words>
DESCRIPTION: <2-4 sentences. Include: setting, lighting, dominant colors (name 2-4), mood, style>
TAGS: <6-10 comma-separated nouns, no colors>
KEYWORDS: <8-15 comma-separated, include style+environment+lighting, allow colors here>
CATEGORIES: <1-3 comma-separated broad buckets>
""".strip()
```

---

## Step 2: Parse slots first; if missing, fallback to old parser

Add a slot parser:

```python
import re

def parse_llava_slots(text: str) -> dict:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]

    def get_value(prefix: str) -> str:
        p = prefix.upper() + ":"
        for ln in lines:
            if ln.upper().startswith(p):
                return ln.split(":", 1)[1].strip()
        return ""

    subject = get_value("SUBJECT")
    setting = get_value("SETTING")
    colors_raw = get_value("COLORS")
    lighting = get_value("LIGHTING")
    mood = get_value("MOOD")
    style = get_value("STYLE")
    tags_raw = get_value("TAGS")

    colors = [c.strip().lower() for c in (colors_raw or "").split(",") if c.strip()]
    tags = [t.strip().lower() for t in (tags_raw or "").split(",") if t.strip()]

    # caps
    colors = colors[:5]
    tags = tags[:10]

    return {
        "subject": subject,
        "setting": setting,
        "colors": colors,
        "lighting": lighting,
        "mood": mood,
        "style": style,
        "tags": tags,
    }

def slots_present(slots: dict) -> bool:
    # Require at least these three to avoid garbage
    return bool(slots.get("subject") and slots.get("setting") and slots.get("style"))
```

(Keep your existing `parse_llava_structured()` for the old format.)

---

## Step 3: Build a “guaranteed rich” description from slots

```python
def build_description_from_slots(slots: dict) -> str:
    parts = []
    if slots.get("subject"):
        parts.append(f"Subject: {slots['subject']}.")
    if slots.get("setting"):
        parts.append(f"Setting: {slots['setting']}.")
    if slots.get("colors"):
        parts.append(f"Colors: {', '.join(slots['colors'])}.")
    if slots.get("lighting"):
        parts.append(f"Lighting: {slots['lighting']}.")
    if slots.get("mood"):
        parts.append(f"Mood: {slots['mood']}.")
    if slots.get("style"):
        parts.append(f"Style: {slots['style']}.")
    return " ".join(parts).strip()
```

---

## Step 4: Wire it into `process_image()` (slot-first, fallback)

In `process_image()`:

1. Call Ollama with the slot prompt.
2. Parse slots.
3. If slots are good, populate metadata from slots.
4. If not, call Ollama with old prompt and use your old parser.

Pseudo-code (drop-in shape):

```python
raw = ollama_llava_describe_image(...prompt=OLLAMA_SLOT_PROMPT...)
slots = parse_llava_slots(raw)

if slots_present(slots):
    metadata.description = build_description_from_slots(slots)
    metadata.tags = slots.get("tags", [])

    # keywords derived from slots (reliable)
    kw = []
    kw += slots.get("colors", [])
    for k in [slots.get("lighting"), slots.get("mood"), slots.get("style"), slots.get("setting")]:
        if k:
            kw.append(k)
    # dedupe preserve order
    seen = set()
    metadata.keywords = [x for x in kw if not (x in seen or seen.add(x))][:12]

    # categories simple derivation
    cats = []
    style_l = (slots.get("style") or "").lower()
    subj_l = (slots.get("subject") or "").lower()
    if "pixel" in style_l:
        cats.append("pixel art")
    if any(w in subj_l for w in ["castle", "tower", "temple", "building", "city"]):
        cats.append("architecture")
    if not cats:
        cats.append("art")
    metadata.categories = cats[:3]

else:
    raw = ollama_llava_describe_image(...prompt=OLLAMA_OLD_PROMPT...)
    parsed = parse_llava_structured(raw)
    metadata.description = parsed.get("description") or parsed.get("caption") or ""
    metadata.tags = parsed.get("tags", [])
    metadata.keywords = parsed.get("keywords", [])
    metadata.categories = parsed.get("categories", [])
```

Keep your AI panel storage exactly as-is (`ai_raw`, provider/model/timestamp). It will now show whichever raw output was used.

---

## Why this is the best option

* You get **richer descriptions every time** (because you assemble them).
* You don’t risk breaking current behavior.
* You can gradually tune slot rules without touching tags/keywords UI.

---
