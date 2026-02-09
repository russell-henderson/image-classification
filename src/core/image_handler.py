"""
Image handling utilities for loading, processing, and extracting metadata from images.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import hashlib

from PIL import Image, ImageTk, ExifTags
try:
    import exifread
except ImportError:
    exifread = None
try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

from .database import ImageMetadata


class ImageHandler:
    """Handles image loading, processing, and metadata extraction."""
    
    def __init__(self, thumbnail_size: int = 256, max_image_size: int = 2048):
        self.thumbnail_size = thumbnail_size
        self.max_image_size = max_image_size
        self.logger = logging.getLogger(__name__)
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.gif'}
        
        # Cache for thumbnails
        self._thumbnail_cache = {}
    
    def is_supported_image(self, file_path: str) -> bool:
        """Check if the file is a supported image format."""
        return Path(file_path).suffix.lower() in self.supported_formats
    
    def load_image(self, file_path: str) -> Optional[Image.Image]:
        """Load an image from file path."""
        try:
            if not self.is_supported_image(file_path):
                return None
            
            image = Image.open(file_path)
            
            # Convert to RGB if necessary
            if image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGB')
            
            return image
        except Exception as e:
            self.logger.error(f"Error loading image {file_path}: {e}")
            return None
    
    def create_thumbnail(self, file_path: str, size: Optional[int] = None) -> Optional[Image.Image]:
        """Create a thumbnail for the image."""
        try:
            if file_path in self._thumbnail_cache:
                return self._thumbnail_cache[file_path]
            
            image = self.load_image(file_path)
            if not image:
                return None
            
            thumbnail_size = size or self.thumbnail_size
            
            # Calculate thumbnail dimensions maintaining aspect ratio
            image.thumbnail((thumbnail_size, thumbnail_size), Image.Resampling.LANCZOS)
            
            # Cache the thumbnail
            self._thumbnail_cache[file_path] = image
            
            return image
        except Exception as e:
            self.logger.error(f"Error creating thumbnail for {file_path}: {e}")
            return None
    
    def get_image_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Extract basic image information."""
        try:
            path_obj = Path(file_path)
            
            if not path_obj.exists() or not self.is_supported_image(file_path):
                return None
            
            # Get file stats
            stat = path_obj.stat()
            
            # Load image to get dimensions
            with Image.open(file_path) as image:
                width, height = image.size
                format_name = image.format or 'Unknown'
            
            return {
                'file_path': str(path_obj.absolute()),
                'filename': path_obj.name,
                'file_size': stat.st_size,
                'width': width,
                'height': height,
                'format': format_name,
                'created_date': datetime.fromtimestamp(stat.st_ctime),
                'modified_date': datetime.fromtimestamp(stat.st_mtime)
            }
        except Exception as e:
            self.logger.error(f"Error getting image info for {file_path}: {e}")
            return None
    
    def extract_exif_data(self, file_path: str) -> Dict[str, Any]:
        """Extract EXIF data from image."""
        exif_data = {}
        
        try:
            # Try with PIL first
            with Image.open(file_path) as image:
                if hasattr(image, 'getexif'):
                    exif = image.getexif()
                    if exif:
                        for tag_id, value in exif.items():
                            tag = ExifTags.TAGS.get(tag_id, tag_id)
                            try:
                                # Convert to string if it's a bytes object
                                if isinstance(value, bytes):
                                    value = value.decode('utf-8', errors='ignore')
                                exif_data[str(tag)] = str(value)
                            except Exception:
                                continue
            
            # Fallback to exifread for more detailed data
            if exifread:
                try:
                    with open(file_path, 'rb') as f:
                        tags = exifread.process_file(f, details=False)
                        for tag, value in tags.items():
                            if not tag.startswith('JPEGThumbnail'):
                                exif_data[tag] = str(value)
                except Exception:
                    pass
            
        except Exception as e:
            self.logger.error(f"Error extracting EXIF data from {file_path}: {e}")
        
        return exif_data
    
    def create_metadata(self, file_path: str) -> Optional[ImageMetadata]:
        """Create complete metadata object for an image."""
        try:
            info = self.get_image_info(file_path)
            if not info:
                return None
            
            exif_data = self.extract_exif_data(file_path)
            
            return ImageMetadata(
                file_path=info['file_path'],
                filename=info['filename'],
                file_size=info['file_size'],
                width=info['width'],
                height=info['height'],
                format=info['format'],
                created_date=info['created_date'],
                modified_date=info['modified_date'],
                exif_data=exif_data,
                tags=[],
                categories=[],
                keywords=[],
                rating=0,
                description='',
                classification='',
                embedding=None,
                api_cached=False,
                cache_date=None
            )
        except Exception as e:
            self.logger.error(f"Error creating metadata for {file_path}: {e}")
            return None
    
    def resize_image(self, image: Image.Image, max_size: int) -> Image.Image:
        """Resize image while maintaining aspect ratio."""
        try:
            width, height = image.size
            
            if max(width, height) <= max_size:
                return image
            
            if width > height:
                new_width = max_size
                new_height = int((height * max_size) / width)
            else:
                new_height = max_size
                new_width = int((width * max_size) / height)
            
            return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        except Exception as e:
            self.logger.error(f"Error resizing image: {e}")
            return image
    
    def get_image_hash(self, file_path: str) -> Optional[str]:
        """Generate a hash for the image file."""
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5()
                for chunk in iter(lambda: f.read(4096), b""):
                    file_hash.update(chunk)
                return file_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Error generating hash for {file_path}: {e}")
            return None
    
    def batch_process_images(self, file_paths: List[str]) -> List[ImageMetadata]:
        """Process multiple images and return metadata list."""
        metadata_list = []
        
        for file_path in file_paths:
            if self.is_supported_image(file_path):
                metadata = self.create_metadata(file_path)
                if metadata:
                    metadata_list.append(metadata)
        
        return metadata_list
    
    def get_dominant_colors(self, image: Image.Image, num_colors: int = 5) -> List[Tuple[int, int, int]]:
        """Extract dominant colors from an image using K-means clustering."""
        try:
            if not cv2 or not np:
                # Fallback: return average color
                img_array = list(image.getdata())
                if len(img_array) == 0:
                    return []
                if len(img_array[0]) >= 3:
                    avg_color = (
                        int(sum(pixel[0] for pixel in img_array) / len(img_array)),
                        int(sum(pixel[1] for pixel in img_array) / len(img_array)),
                        int(sum(pixel[2] for pixel in img_array) / len(img_array))
                    )
                    return [avg_color]
                return []
            
            # Convert PIL image to OpenCV format
            opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Reshape the image to a 2D array of pixels
            data = opencv_image.reshape((-1, 3))
            data = np.float32(data)
            
            # Apply K-means clustering
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
            _, labels, centers = cv2.kmeans(data, num_colors, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            
            # Convert centers back to uint8 and BGR to RGB
            if cv2 is not None and np is not None:
                centers_list = np.uint8(centers).tolist()
                colors = [
                    (int(center[2]), int(center[1]), int(center[0]))
                    for center in centers_list
                ]
            else:
                colors = [(128, 128, 128)]  # Default gray
            
            return colors
        except Exception as e:
            self.logger.error(f"Error extracting dominant colors: {e}")
            return []
    
    def detect_blur(self, image: Image.Image) -> float:
        """Detect blur in an image using Laplacian variance."""
        try:
            if not cv2 or not np:
                return 0.0
                
            # Convert to grayscale
            gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
            
            # Calculate Laplacian variance
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            return float(laplacian_var)
        except Exception as e:
            self.logger.error(f"Error detecting blur: {e}")
            return 0.0
    
    def get_image_statistics(self, image: Image.Image) -> Dict[str, Any]:
        """Get various image statistics."""
        try:
            if np:
                np_image = np.array(image)
                
                stats = {
                    'mean_brightness': float(np.mean(np_image)),
                    'std_brightness': float(np.std(np_image)),
                    'min_brightness': int(np.min(np_image)),
                    'max_brightness': int(np.max(np_image)),
                    'aspect_ratio': image.width / image.height,
                    'file_size_mb': 0,  # Will be filled by caller
                    'blur_score': self.detect_blur(image),
                    'dominant_colors': self.get_dominant_colors(image)
                }
            else:
                # Fallback without numpy
                stats = {
                    'mean_brightness': 0.0,
                    'std_brightness': 0.0,
                    'min_brightness': 0,
                    'max_brightness': 255,
                    'aspect_ratio': image.width / image.height,
                    'file_size_mb': 0,
                    'blur_score': 0.0,
                    'dominant_colors': self.get_dominant_colors(image)
                }
            
            return stats
        except Exception as e:
            self.logger.error(f"Error calculating image statistics: {e}")
            return {}
    
    def clear_thumbnail_cache(self):
        """Clear the thumbnail cache to free memory."""
        self._thumbnail_cache.clear()
        self.logger.info("Thumbnail cache cleared")
    
    def scan_directory(self, directory: str, recursive: bool = True) -> List[str]:
        """Scan directory for supported images."""
        image_files = []
        
        try:
            path = Path(directory)
            if not path.exists():
                return image_files
            
            pattern = "**/*" if recursive else "*"
            
            for file_path in path.glob(pattern):
                if file_path.is_file() and self.is_supported_image(str(file_path)):
                    image_files.append(str(file_path.absolute()))
            
            self.logger.info(f"Found {len(image_files)} images in {directory}")
            
        except Exception as e:
            self.logger.error(f"Error scanning directory {directory}: {e}")
        
        return sorted(image_files)
