Got it. Below is the **fully complete** version adjusted for `ImageMetadata` attribute access.

---

# Part 1: Engine (Ollama prompt + parser + mapping to ImageMetadata)

File: `src/core/classifier.py`

## 1) Use this exact structured prompt

Add near the top of the file:

```python
OLLAMA_STRUCTURED_PROMPT = """
Return exactly this format (no extra text):

CAPTION: <one sentence, max 20 words>
TAGS: <6-10 comma-separated nouns/subjects, no colors>
KEYWORDS: <8-15 comma-separated, may include style + environment, no camera terms>
CATEGORIES: <1-3 comma-separated broad buckets>

Rules:
- Use commas only as separators inside TAGS/KEYWORDS/CATEGORIES.
- Do not number items.
- Do not include any other lines besides the four above.
""".strip()
```

## 2) Add this parser (drop-in)

Add these imports (if not already present):

```python
import re
from typing import Dict, List
```

Add this parser code:

```python
_STOP_WORDS = {
    "image", "picture", "scene", "shows", "showing", "depicts", "depicting",
    "beautiful", "stunning", "detailed", "highly", "quality",
    "photo", "photograph", "artwork"
}

_COLOR_WORDS = {
    "red","orange","yellow","green","blue","purple","pink","brown","black","white","gray","grey",
    "teal","cyan","magenta","violet","indigo","gold","silver","neon"
}

_CAMERA_WORDS = {
    "bokeh","lens","focal","aperture","iso","shutter","depth of field","dof","exposure"
}

def _split_csv_items(s: str) -> List[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]

def _normalize_item(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\s\-]", "", s)  # remove punctuation except hyphen
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _filter_items(items: List[str], *, exclude_colors: bool, exclude_camera: bool) -> List[str]:
    out = []
    seen = set()
    for raw in items:
        norm = _normalize_item(raw)
        if not norm:
            continue
        if norm in _STOP_WORDS:
            continue
        if exclude_colors and norm in _COLOR_WORDS:
            continue
        if exclude_camera and (norm in _CAMERA_WORDS or any(w in norm for w in _CAMERA_WORDS)):
            continue
        if norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out

def parse_llava_structured(text: str) -> Dict[str, object]:
    """
    Expects exactly:
      CAPTION: ...
      TAGS: ...
      KEYWORDS: ...
      CATEGORIES: ...
    Returns dict: caption(str), tags(list[str]), keywords(list[str]), categories(list[str])
    """
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]

    def get_value(prefix: str) -> str:
        prefix_upper = prefix.upper()
        for ln in lines:
            if ln.upper().startswith(prefix_upper + ":"):
                return ln.split(":", 1)[1].strip()
        return ""

    caption = get_value("CAPTION")
    tags_raw = get_value("TAGS")
    keywords_raw = get_value("KEYWORDS")
    categories_raw = get_value("CATEGORIES")

    tags = _filter_items(_split_csv_items(tags_raw), exclude_colors=True, exclude_camera=True)[:8]
    keywords = _filter_items(_split_csv_items(keywords_raw), exclude_colors=True, exclude_camera=True)[:12]
    categories = _filter_items(_split_csv_items(categories_raw), exclude_colors=True, exclude_camera=False)[:3]

    return {"caption": caption.strip(), "tags": tags, "keywords": keywords, "categories": categories}
```

## 3) Call Ollama with the prompt and map into ImageMetadata

Where you already call `ollama_llava_describe_image(...)` inside `process_image()`, set:

```python
raw = ollama_llava_describe_image(
    image_path=image_path,
    base_url=ollama_cfg.get("base_url", "http://localhost:11434"),
    model=ollama_cfg.get("model", "llava:latest"),
    prompt=OLLAMA_STRUCTURED_PROMPT,
    timeout_seconds=int(ollama_cfg.get("timeout_seconds", 120)),
)

parsed = parse_llava_structured(raw)

# ImageMetadata attribute assignment
metadata.description = parsed["caption"]
metadata.tags = parsed["tags"]
metadata.keywords = parsed["keywords"]
metadata.categories = parsed["categories"]

# If you keep raw AI text somewhere for the AI panel, pick one:
# metadata.ai_raw = raw              # if ImageMetadata has this field
# metadata.ai_provider = "ollama"     # optional
# metadata.ai_model = ollama_cfg.get("model", "llava:latest")
```

If `ImageMetadata` does NOT have `categories` yet, add it to the model (next section).

---

## 4) If ImageMetadata is missing `categories`

Find the dataclass/model definition (commonly `src/core/models.py` or `src/core/metadata.py`) and add:

```python
categories: list[str] = field(default_factory=list)
```

(Use whatever style the model already uses for tags/keywords.)

---

# Part 2: GUI (populate Tags/Keywords/Categories + Technical Information)

File: `src/ui/metadata_panel.py`

## 1) Ensure the UI refresh runs after classification

At the end of your `_on_classify_complete(...)`, ensure it calls:

```python
self._populate_fields_from_metadata(self.current_metadata)
```

(Whatever object you store in `self.current_metadata`.)

## 2) Update `_populate_fields_from_metadata` for ImageMetadata object

Because `current_metadata` is an `ImageMetadata` object, use attribute access.

Replace or add this block:

```python
def _populate_fields_from_metadata(self, metadata):
    # ... existing UI loads above ...

    def _set_entry(entry, value):
        entry.delete(0, "end")
        if isinstance(value, list):
            entry.insert(0, ", ".join(value))
        else:
            entry.insert(0, value or "")

    _set_entry(self.tags_entry, getattr(metadata, "tags", []))
    _set_entry(self.keywords_entry, getattr(metadata, "keywords", []))
    _set_entry(self.categories_entry, getattr(metadata, "categories", []))

    # Technical info uses filepath (confirmed)
    image_path = getattr(metadata, "filepath", None)
    tech_text = self._build_technical_info(image_path) if image_path else "No file selected"
    self._set_exif_text(tech_text)
```

## 3) Add `_set_exif_text()`

Add inside `MetadataPanel`:

```python
def _set_exif_text(self, text: str) -> None:
    self.exif_text.configure(state="normal")
    self.exif_text.delete("1.0", "end")
    self.exif_text.insert("1.0", text or "")
    self.exif_text.configure(state="disabled")
```

## 4) Add `_build_technical_info()` (EXIF + fallback)

Add imports at top of file:

```python
import os
from PIL import Image, ExifTags
```

Add inside `MetadataPanel`:

```python
def _build_technical_info(self, image_path: str) -> str:
    if not image_path or not os.path.exists(image_path):
        return "No EXIF data available"

    lines = []
    try:
        size_bytes = os.path.getsize(image_path)
        lines.append(f"Path: {image_path}")
        lines.append(f"File size: {size_bytes:,} bytes")

        with Image.open(image_path) as img:
            lines.append(f"Format: {img.format or 'Unknown'}")
            lines.append(f"Mode: {img.mode}")
            lines.append(f"Dimensions: {img.size[0]} x {img.size[1]}")

            dpi = img.info.get("dpi")
            if dpi:
                lines.append(f"DPI: {dpi[0]} x {dpi[1]}")

            exif = None
            try:
                exif = img.getexif()
            except Exception:
                exif = None

            if exif and len(exif) > 0:
                lines.append("")
                lines.append("EXIF:")

                tag_map = {v: k for k, v in ExifTags.TAGS.items()}

                def exif_get(tag_name: str):
                    tag_id = tag_map.get(tag_name)
                    return exif.get(tag_id) if tag_id else None

                fields = [
                    ("DateTimeOriginal", "DateTimeOriginal"),
                    ("Make", "Make"),
                    ("Model", "Model"),
                    ("LensModel", "LensModel"),
                    ("ISO", "ISOSpeedRatings"),
                    ("ExposureTime", "ExposureTime"),
                    ("FNumber", "FNumber"),
                    ("FocalLength", "FocalLength"),
                ]

                for label, key in fields:
                    val = exif_get(key)
                    if val is not None:
                        lines.append(f"- {label}: {val}")
            else:
                lines.append("")
                lines.append("No EXIF data available")

    except Exception as e:
        return f"Technical information error: {e}"

    return "\n".join(lines)
```

---

# Part 3: Validate (expected behavior)

1. Launch app
2. Select an image
3. Click **Classify Image**
4. After completion:

* `Description` becomes the `CAPTION` line
* `Tags` entry gets parsed tags (comma-separated)
* `Keywords` entry gets parsed keywords
* `Categories` entry gets parsed categories
* `Technical Information` fills with file stats and EXIF if present

---

### Final checklist (apply in this exact order)

## 1) `src/core/classifier.py`

1. Add `OLLAMA_STRUCTURED_PROMPT` constant.
2. Add the parser helpers (`parse_llava_structured`, `_split_csv_items`, `_filter_items`, etc.).
3. In `process_image()`, call Ollama using `prompt=OLLAMA_STRUCTURED_PROMPT`.
4. Map results into the `ImageMetadata` object:

```python
metadata.description = parsed["caption"]
metadata.tags = parsed["tags"]
metadata.keywords = parsed["keywords"]
metadata.categories = parsed["categories"]
```

## 2) `src/ui/metadata_panel.py`

1. In `_populate_fields_from_metadata(self, metadata)` (object-based), set:

* `self.tags_entry` from `metadata.tags`
* `self.keywords_entry` from `metadata.keywords`
* `self.categories_entry` from `metadata.categories`

2. Add `_set_exif_text()` and `_build_technical_info()` and call them using:

```python
image_path = getattr(metadata, "filepath", None)
tech_text = self._build_technical_info(image_path) if image_path else "No file selected"
self._set_exif_text(tech_text)
```

3. Ensure `_on_classify_complete()` ends by calling:

```python
self._populate_fields_from_metadata(self.current_metadata)
```

### Quick verification commands

* Run the app, select an image, click **Classify Image**.
* Confirm the three entry fields (Tags/Keywords/Categories) fill immediately after classification.
* Confirm “Technical Information” shows file stats even when EXIF is missing.

If you paste the current `process_image()` section where the Ollama call happens (about 30–60 lines), I’ll sanity-check the integration for the two common failure points: prompt not being passed through, and UI refresh not calling the updated populate method.
