"""
ML classification engine for image analysis using Ollama LLaVA and local models.
"""

import asyncio
import base64
import io
import json
import logging
import time
import urllib.request
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable

from PIL import Image

from .database import DatabaseManager, ImageMetadata
from .image_handler import ImageHandler

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

_STOP_WORDS = {
    "image", "picture", "scene", "shows", "showing", "depicts", "depicting",
    "beautiful", "stunning", "detailed", "highly", "quality",
    "photo", "photograph", "artwork"
}

_COLOR_WORDS = {
    "red", "orange", "yellow", "green", "blue", "purple", "pink", "brown", "black", "white", "gray", "grey",
    "teal", "cyan", "magenta", "violet", "indigo", "gold", "silver", "neon"
}

_CAMERA_WORDS = {
    "bokeh", "lens", "focal", "aperture", "iso", "shutter", "depth of field", "dof", "exposure"
}


def _split_csv_items(value: str) -> List[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _normalize_item(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\s\-]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _filter_items(items: List[str], *, exclude_colors: bool, exclude_camera: bool) -> List[str]:
    filtered = []
    seen = set()
    for raw in items:
        norm = _normalize_item(raw)
        if not norm:
            continue
        if norm in _STOP_WORDS:
            continue
        if exclude_colors and norm in _COLOR_WORDS:
            continue
        if exclude_camera and (norm in _CAMERA_WORDS or any(word in norm for word in _CAMERA_WORDS)):
            continue
        if norm in seen:
            continue
        seen.add(norm)
        filtered.append(norm)
    return filtered


def parse_llava_slots(text: str) -> Dict[str, object]:
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

    colors = [c.strip().lower() for c in (colors_raw or "").split(",") if c.strip()][:5]
    tags = [t.strip().lower() for t in (tags_raw or "").split(",") if t.strip()][:10]

    return {
        "subject": subject,
        "setting": setting,
        "colors": colors,
        "lighting": lighting,
        "mood": mood,
        "style": style,
        "tags": tags,
    }


def slots_present(slots: Dict[str, object]) -> bool:
    return bool(slots.get("subject") and slots.get("setting") and slots.get("style"))


def build_description_from_slots(slots: Dict[str, object]) -> str:
    parts = []
    subject = slots.get("subject") or ""
    setting = slots.get("setting") or ""
    colors = slots.get("colors") or []
    lighting = slots.get("lighting") or ""
    mood = slots.get("mood") or ""
    style = slots.get("style") or ""

    if subject:
        parts.append(f"Subject: {subject}.")
    if setting:
        parts.append(f"Setting: {setting}.")
    if colors:
        parts.append(f"Colors: {', '.join(colors)}.")
    if lighting:
        parts.append(f"Lighting: {lighting}.")
    if mood:
        parts.append(f"Mood: {mood}.")
    if style:
        parts.append(f"Style: {style}.")
    return " ".join(parts).strip()


def parse_llava_structured(text: str) -> Dict[str, object]:
    """
    Expects:
      CAPTION: ...
      DESCRIPTION: ...
      TAGS: ...
      KEYWORDS: ...
      CATEGORIES: ...
    Returns dict: caption(str), description(str), tags(list[str]), keywords(list[str]), categories(list[str])
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]

    def _get_value(prefix: str) -> str:
        prefix_upper = prefix.upper()
        for line in lines:
            if line.upper().startswith(prefix_upper + ":"):
                return line.split(":", 1)[1].strip()
        return ""

    caption = _get_value("CAPTION")
    description = _get_value("DESCRIPTION")
    tags_raw = _get_value("TAGS")
    keywords_raw = _get_value("KEYWORDS")
    categories_raw = _get_value("CATEGORIES")

    tags = _filter_items(_split_csv_items(tags_raw), exclude_colors=True, exclude_camera=True)[:10]
    keywords = _filter_items(_split_csv_items(keywords_raw), exclude_colors=False, exclude_camera=True)[:15]
    categories = _filter_items(_split_csv_items(categories_raw), exclude_colors=True, exclude_camera=False)[:3]

    return {
        "caption": caption.strip(),
        "description": description.strip(),
        "tags": tags,
        "keywords": keywords,
        "categories": categories,
    }


_STOP_WORDS = {
    "image", "picture", "scene", "shows", "showing", "depicts", "depicting",
    "beautiful", "stunning", "detailed", "highly", "quality",
    "photo", "photograph", "artwork"
}

_COLOR_WORDS = {
    "red", "orange", "yellow", "green", "blue", "purple", "pink", "brown", "black", "white", "gray", "grey",
    "teal", "cyan", "magenta", "violet", "indigo", "gold", "silver", "neon"
}

_CAMERA_WORDS = {
    "bokeh", "lens", "focal", "aperture", "iso", "shutter", "depth of field", "dof", "exposure"
}


def _split_csv_items(value: str) -> List[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _normalize_item(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\s\-]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _filter_items(items: List[str], *, exclude_colors: bool, exclude_camera: bool) -> List[str]:
    filtered = []
    seen = set()
    for raw in items:
        norm = _normalize_item(raw)
        if not norm:
            continue
        if norm in _STOP_WORDS:
            continue
        if exclude_colors and norm in _COLOR_WORDS:
            continue
        if exclude_camera and (norm in _CAMERA_WORDS or any(word in norm for word in _CAMERA_WORDS)):
            continue
        if norm in seen:
            continue
        seen.add(norm)
        filtered.append(norm)
    return filtered


def parse_llava_structured(text: str) -> Dict[str, object]:
    """
    Expects:
      CAPTION: ...
      DESCRIPTION: ...
      TAGS: ...
      KEYWORDS: ...
      CATEGORIES: ...
    Returns dict: caption(str), description(str), tags(list[str]), keywords(list[str]), categories(list[str])
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]

    def _get_value(prefix: str) -> str:
        prefix_upper = prefix.upper()
        for line in lines:
            if line.upper().startswith(prefix_upper + ":"):
                return line.split(":", 1)[1].strip()
        return ""

    caption = _get_value("CAPTION")
    description = _get_value("DESCRIPTION")
    tags_raw = _get_value("TAGS")
    keywords_raw = _get_value("KEYWORDS")
    categories_raw = _get_value("CATEGORIES")

    tags = _filter_items(_split_csv_items(tags_raw), exclude_colors=True, exclude_camera=True)[:10]
    keywords = _filter_items(_split_csv_items(keywords_raw), exclude_colors=False, exclude_camera=True)[:15]
    categories = _filter_items(_split_csv_items(categories_raw), exclude_colors=True, exclude_camera=False)[:3]

    return {
        "caption": caption.strip(),
        "description": description.strip(),
        "tags": tags,
        "keywords": keywords,
        "categories": categories,
    }


def ollama_llava_describe_image(
    *,
    image_path: str,
    base_url: str,
    model: str,
    prompt: str = "Describe this image. Provide concise tags/keywords and a short caption.",
    timeout_seconds: int = 120,
) -> str:
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [img_b64],
        "stream": False,
    }

    req = urllib.request.Request(
        url=f"{base_url.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return (data.get("response") or "").strip()


class ClassificationEngine:
    """Handles ML-based image classification and description generation."""
    
    def __init__(self, config: Dict[str, Any], db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.image_handler = ImageHandler(
            thumbnail_size=config.get('thumbnail_size', 256),
            max_image_size=config.get('max_image_size', 2048)
        )
        self.logger = logging.getLogger(__name__)
        
        # Rate limiting
        self.last_api_call = 0
        self.rate_limit_delay = config.get('rate_limit_delay', 1.0)
        
        # Cache settings
        self.cache_duration = timedelta(days=config.get('cache_duration', 86400) // 86400)
    
    def _rate_limit(self):
        """Apply rate limiting to API calls."""
        now = time.time()
        elapsed = now - self.last_api_call
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_api_call = time.time()
    
    def _is_cache_valid(self, metadata: ImageMetadata) -> bool:
        """Check if cached classification is still valid."""
        if not metadata.api_cached or not metadata.cache_date:
            return False
        
        age = datetime.now() - metadata.cache_date
        return age < self.cache_duration
    
    def _encode_image_for_api(self, image_path: str) -> Optional[str]:
        """Encode image to base64 for API submission."""
        try:
            # Load and resize image if necessary
            image = self.image_handler.load_image(image_path)
            if not image:
                return None
            
            # Resize if too large
            max_size = self.config.get('max_image_size', 2048)
            image = self.image_handler.resize_image(image, max_size)
            
            # Convert to base64
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85)
            image_data = buffer.getvalue()
            
            return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Error encoding image {image_path}: {e}")
            return None
    
    async def classify_image_ollama(self, image_path: str, custom_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Call Ollama and return raw output."""
        try:
            ollama_cfg = self.config.get("providers", {}).get("ollama", {})
            if not ollama_cfg.get("enabled", False):
                return {"error": "Ollama provider is disabled in settings.json"}

            self._rate_limit()

            prompt = custom_prompt or OLLAMA_SLOT_PROMPT

            raw = await asyncio.to_thread(
                ollama_llava_describe_image,
                image_path=image_path,
                base_url=ollama_cfg.get("base_url", "http://localhost:11434"),
                model=ollama_cfg.get("model", "llava:latest"),
                prompt=prompt,
                timeout_seconds=int(ollama_cfg.get("timeout_seconds", 120)),
            )

            return {
                "raw": raw,
                "api_used": "ollama",
                "model": ollama_cfg.get("model", "llava:latest"),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Ollama classification error for {image_path}: {e}")
            return {"error": str(e)}
    
    def classify_image_local(self, image_path: str) -> Dict[str, Any]:
        """Classify image using local methods (fallback)."""
        try:
            image = self.image_handler.load_image(image_path)
            if not image:
                return {'error': 'Failed to load image'}
            
            # Get basic image statistics
            stats = self.image_handler.get_image_statistics(image)
            
            # Simple heuristic classification based on image properties
            classification = self._heuristic_classification(image, stats)
            
            return {
                'description': classification['description'],
                'subjects': classification['subjects'],
                'scene': classification['scene'],
                'colors': ', '.join([f"RGB{color}" for color in stats.get('dominant_colors', [])]),
                'mood': classification['mood'],
                'quality': classification['quality'],
                'api_used': 'local',
                'model': 'heuristic',
                'timestamp': datetime.now().isoformat(),
                'statistics': stats
            }
            
        except Exception as e:
            self.logger.error(f"Local classification error for {image_path}: {e}")
            return {'error': str(e)}
    
    def _heuristic_classification(self, image: Image.Image, stats: Dict[str, Any]) -> Dict[str, str]:
        """Simple heuristic classification based on image properties."""
        width, height = image.size
        aspect_ratio = stats.get('aspect_ratio', 1.0)
        
        # Basic scene classification
        if aspect_ratio > 1.5:
            scene = "landscape/panoramic"
        elif aspect_ratio < 0.7:
            scene = "portrait/vertical"
        else:
            scene = "standard/square"
        
        # Quality assessment
        blur_score = stats.get('blur_score', 0)
        if blur_score > 500:
            quality = "high"
        elif blur_score > 100:
            quality = "medium"
        else:
            quality = "low/blurry"
        
        # Simple mood based on brightness
        brightness = stats.get('mean_brightness', 128)
        if brightness > 180:
            mood = "bright/cheerful"
        elif brightness > 100:
            mood = "neutral"
        else:
            mood = "dark/moody"
        
        return {
            'description': f"A {scene} image with {quality} quality and {mood} lighting",
            'subjects': "unknown",
            'scene': scene,
            'mood': mood,
            'quality': quality
        }

    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract simple keywords from a description string."""
        if not text:
            return []

        stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "into", "over", "under",
            "image", "photo", "picture", "scene", "view", "showing", "shows", "shown",
            "there", "their", "then", "than", "them", "they", "were", "when", "where",
            "what", "which", "while", "your", "you", "a", "an", "of", "in", "on", "at",
            "by", "to", "is", "are", "was", "were", "be", "as", "it", "its", "or", "if",
        }

        words = re.findall(r"[a-zA-Z0-9]+", text.lower())
        keywords = []
        for word in words:
            if len(word) < 3 or word in stopwords:
                continue
            if word not in keywords:
                keywords.append(word)
            if len(keywords) >= max_keywords:
                break
        return keywords
    
    async def process_image(self, image_path: str, force_refresh: bool = False) -> Optional[ImageMetadata]:
        """Process a single image with classification."""
        try:
            # Check if image exists in database
            existing_metadata = self.db_manager.get_image(image_path)
            
            # Use cache if valid and not forcing refresh
            if existing_metadata and not force_refresh and self._is_cache_valid(existing_metadata):
                self.logger.info(f"Using cached classification for {image_path}")
                return existing_metadata
            
            # Create or update metadata
            if existing_metadata:
                metadata = existing_metadata
            else:
                metadata = self.image_handler.create_metadata(image_path)
                if not metadata:
                    return None
            
            # Try Ollama slot prompt first
            classification_result = await self.classify_image_ollama(
                image_path,
                custom_prompt=OLLAMA_SLOT_PROMPT,
            )

            if not classification_result or "error" in classification_result:
                self.logger.info(f"Using local classification for {image_path}")
                classification_result = self.classify_image_local(image_path)
            else:
                raw = classification_result.get("raw", "")
                slots = parse_llava_slots(raw)
                if slots_present(slots):
                    description = build_description_from_slots(slots)
                    metadata.description = description
                    metadata.tags = slots.get("tags", [])

                    kw = []
                    kw += slots.get("colors", [])
                    for value in [slots.get("lighting"), slots.get("mood"), slots.get("style"), slots.get("setting")]:
                        if value:
                            kw.append(value)
                    seen = set()
                    metadata.keywords = [x for x in kw if not (x in seen or seen.add(x))][:12]

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

                    metadata.ai_raw = raw
                    metadata.ai_provider = "ollama"
                    metadata.ai_model = classification_result.get("model", "")
                    metadata.ai_timestamp = classification_result.get("timestamp", "")

                    metadata.classification = json.dumps(
                        {**classification_result, "format": "slots", "slots": slots}
                    )
                else:
                    fallback_result = await self.classify_image_ollama(
                        image_path,
                        custom_prompt=OLLAMA_OLD_PROMPT,
                    )
                    if not fallback_result or "error" in fallback_result:
                        self.logger.info(f"Using local classification for {image_path}")
                        classification_result = self.classify_image_local(image_path)
                    else:
                        raw_old = fallback_result.get("raw", "")
                        parsed = parse_llava_structured(raw_old)
                        metadata.description = parsed.get("description") or parsed.get("caption") or ""
                        metadata.tags = parsed.get("tags", [])
                        metadata.keywords = parsed.get("keywords", [])
                        metadata.categories = parsed.get("categories", [])

                        metadata.ai_raw = raw_old
                        metadata.ai_provider = "ollama"
                        metadata.ai_model = fallback_result.get("model", "")
                        metadata.ai_timestamp = fallback_result.get("timestamp", "")

                        metadata.classification = json.dumps(
                            {**fallback_result, "format": "legacy", "parsed": parsed}
                        )
            
            # Update metadata with classification results (local fallback path)
            if classification_result and 'error' not in classification_result and classification_result.get("api_used") != "ollama":
                description = classification_result.get('description', '')
                metadata.description = description
                metadata.tags = []
                metadata.keywords = []
                metadata.categories = []
                metadata.ai_raw = ""
                metadata.ai_provider = ""
                metadata.ai_model = ""
                metadata.ai_timestamp = ""

                if description:
                    extracted = self._extract_keywords(description)
                    metadata.keywords = list(extracted)
                    metadata.tags = list(extracted)

                scene = classification_result.get('scene', '')
                if scene:
                    metadata.categories.append(scene)

                metadata.classification = json.dumps(classification_result)
                
                metadata.api_cached = True
                metadata.cache_date = datetime.now()
            
            # Save to database
            self.db_manager.add_image(metadata)
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error processing image {image_path}: {e}")
            return None
    
    async def batch_process_images(self, image_paths: List[str], 
                                  progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[ImageMetadata]:
        """Process multiple images in batch."""
        results = []
        total = len(image_paths)
        
        for i, image_path in enumerate(image_paths):
            try:
                metadata = await self.process_image(image_path)
                if metadata:
                    results.append(metadata)
                
                if progress_callback:
                    progress_callback(i + 1, total, image_path)
                
                # Small delay to prevent overwhelming the API
                if i < total - 1:
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"Error in batch processing {image_path}: {e}")
                continue
        
        return results
    
    def search_similar_images(self, reference_path: str, threshold: float = 0.8) -> List[ImageMetadata]:
        """Search for similar images based on classification."""
        try:
            reference_metadata = self.db_manager.get_image(reference_path)
            if not reference_metadata or not reference_metadata.classification:
                return []
            
            reference_classification = json.loads(reference_metadata.classification)
            reference_subjects = set(reference_classification.get('subjects', '').lower().split(','))
            reference_scene = reference_classification.get('scene', '').lower()
            
            # Get all images and compare
            all_images = self.db_manager.get_all_images()
            similar_images = []
            
            for image_metadata in all_images:
                if image_metadata.file_path == reference_path:
                    continue
                
                if not image_metadata.classification:
                    continue
                
                try:
                    classification = json.loads(image_metadata.classification)
                    subjects = set(classification.get('subjects', '').lower().split(','))
                    scene = classification.get('scene', '').lower()
                    
                    # Calculate similarity score
                    subject_overlap = len(reference_subjects.intersection(subjects)) / max(len(reference_subjects), 1)
                    scene_match = 1.0 if reference_scene == scene else 0.0
                    
                    similarity_score = (subject_overlap * 0.7) + (scene_match * 0.3)
                    
                    if similarity_score >= threshold:
                        similar_images.append((image_metadata, similarity_score))
                        
                except json.JSONDecodeError:
                    continue
            
            # Sort by similarity score
            similar_images.sort(key=lambda x: x[1], reverse=True)
            
            return [img[0] for img in similar_images]
            
        except Exception as e:
            self.logger.error(f"Error searching similar images: {e}")
            return []
    
    def get_classification_stats(self) -> Dict[str, Any]:
        """Get classification statistics."""
        try:
            stats = self.db_manager.get_statistics()
            
            # Add classification-specific stats
            all_images = self.db_manager.get_all_images()
            classified_count = sum(1 for img in all_images if img.classification)
            
            api_usage = {}
            for image in all_images:
                if image.classification:
                    try:
                        classification = json.loads(image.classification)
                        api = classification.get('api_used', 'unknown')
                        api_usage[api] = api_usage.get(api, 0) + 1
                    except json.JSONDecodeError:
                        continue
            
            stats.update({
                'classified_images': classified_count,
                'classification_rate': classified_count / max(stats.get('total_images', 1), 1),
                'api_usage': api_usage
            })
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting classification stats: {e}")
            return {}
