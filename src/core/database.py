"""
Database management for image metadata storage and retrieval.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta


@dataclass
class ImageMetadata:
    """Data class for image metadata."""
    file_path: str
    filename: str
    file_size: int
    width: int
    height: int
    format: str
    created_date: datetime
    modified_date: datetime
    exif_data: Dict[str, Any]
    tags: List[str]
    categories: List[str]
    keywords: List[str]
    rating: int
    description: str
    classification: str
    ai_raw: str = ""
    ai_provider: str = ""
    ai_model: str = ""
    ai_timestamp: str = ""
    embedding: Optional[List[float]] = None
    api_cached: bool = False
    cache_date: Optional[datetime] = None


class DatabaseManager:
    """Manages SQLite database operations for image metadata."""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        self._init_database()

    @staticmethod
    def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _parse_datetime(value: Optional[Any]) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None
    
    def _init_database(self):
        """Initialize the database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS images (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT UNIQUE NOT NULL,
                        filename TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        width INTEGER NOT NULL,
                        height INTEGER NOT NULL,
                        format TEXT NOT NULL,
                        created_date TIMESTAMP NOT NULL,
                        modified_date TIMESTAMP NOT NULL,
                        exif_data TEXT,
                        tags TEXT,
                        categories TEXT,
                        keywords TEXT,
                        rating INTEGER DEFAULT 0,
                        description TEXT,
                        classification TEXT,
                        embedding TEXT,
                        ai_raw TEXT,
                        ai_provider TEXT,
                        ai_model TEXT,
                        ai_timestamp TEXT,
                        api_cached BOOLEAN DEFAULT FALSE,
                        cache_date TIMESTAMP,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                self._ensure_columns(conn)
                
                # Create indexes for better performance
                conn.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON images(file_path)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_filename ON images(filename)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_rating ON images(rating)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_format ON images(format)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_classification ON images(classification)')
                
                conn.commit()
                self.logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            self.logger.error(f"Database initialization error: {e}")
            raise

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        """Ensure optional columns exist for newer metadata fields."""
        existing = {row[1] for row in conn.execute("PRAGMA table_info(images)")}
        optional_columns = {
            "ai_raw": "TEXT",
            "ai_provider": "TEXT",
            "ai_model": "TEXT",
            "ai_timestamp": "TEXT",
        }
        for column, col_type in optional_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE images ADD COLUMN {column} {col_type}")
    
    def add_image(self, metadata: ImageMetadata) -> bool:
        """Add image metadata to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO images 
                    (file_path, filename, file_size, width, height, format, 
                     created_date, modified_date, exif_data, tags, categories, 
                     keywords, rating, description, classification, embedding, 
                     ai_raw, ai_provider, ai_model, ai_timestamp,
                     api_cached, cache_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metadata.file_path,
                    metadata.filename,
                    metadata.file_size,
                    metadata.width,
                    metadata.height,
                    metadata.format,
                    self._serialize_datetime(metadata.created_date),
                    self._serialize_datetime(metadata.modified_date),
                    json.dumps(metadata.exif_data),
                    json.dumps(metadata.tags),
                    json.dumps(metadata.categories),
                    json.dumps(metadata.keywords),
                    metadata.rating,
                    metadata.description,
                    metadata.classification,
                    json.dumps(metadata.embedding) if metadata.embedding else None,
                    metadata.ai_raw,
                    metadata.ai_provider,
                    metadata.ai_model,
                    metadata.ai_timestamp,
                    metadata.api_cached,
                    self._serialize_datetime(metadata.cache_date)
                ))
                conn.commit()
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Error adding image {metadata.file_path}: {e}")
            return False
    
    def get_image(self, file_path: str) -> Optional[ImageMetadata]:
        """Retrieve image metadata by file path."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM images WHERE file_path = ?', (file_path,)
                )
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_metadata(row)
                return None
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving image {file_path}: {e}")
            return None
    
    def get_all_images(self, limit: Optional[int] = None, offset: int = 0) -> List[ImageMetadata]:
        """Retrieve all images with optional pagination."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                query = 'SELECT * FROM images ORDER BY added_date DESC'
                params = []
                
                if limit:
                    query += ' LIMIT ? OFFSET ?'
                    params.extend([limit, offset])
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [self._row_to_metadata(row) for row in rows]
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving images: {e}")
            return []
    
    def search_images(self, 
                     tags: Optional[List[str]] = None,
                     categories: Optional[List[str]] = None,
                     keywords: Optional[List[str]] = None,
                     rating_min: Optional[int] = None,
                     classification: Optional[str] = None) -> List[ImageMetadata]:
        """Search images by various criteria."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                conditions = []
                params = []
                
                if tags:
                    for tag in tags:
                        conditions.append("tags LIKE ?")
                        params.append(f'%"{tag}"%')
                
                if categories:
                    for category in categories:
                        conditions.append("categories LIKE ?")
                        params.append(f'%"{category}"%')
                
                if keywords:
                    for keyword in keywords:
                        conditions.append("keywords LIKE ?")
                        params.append(f'%"{keyword}"%')
                
                if rating_min is not None:
                    conditions.append("rating >= ?")
                    params.append(rating_min)
                
                if classification:
                    conditions.append("classification LIKE ?")
                    params.append(f'%{classification}%')
                
                query = 'SELECT * FROM images'
                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)
                query += ' ORDER BY rating DESC, added_date DESC'
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [self._row_to_metadata(row) for row in rows]
        except sqlite3.Error as e:
            self.logger.error(f"Error searching images: {e}")
            return []
    
    def update_metadata(self, file_path: str, **kwargs) -> bool:
        """Update specific metadata fields for an image."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                set_clauses = []
                params = []
                
                for field, value in kwargs.items():
                    if field in ['tags', 'categories', 'keywords', 'exif_data', 'embedding']:
                        set_clauses.append(f"{field} = ?")
                        params.append(json.dumps(value))
                    else:
                        set_clauses.append(f"{field} = ?")
                        params.append(value)
                
                if not set_clauses:
                    return False
                
                params.append(file_path)
                query = f"UPDATE images SET {', '.join(set_clauses)} WHERE file_path = ?"
                
                conn.execute(query, params)
                conn.commit()
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Error updating metadata for {file_path}: {e}")
            return False
    
    def delete_image(self, file_path: str) -> bool:
        """Delete image metadata from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('DELETE FROM images WHERE file_path = ?', (file_path,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Error deleting image {file_path}: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM images')
                total_images = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) FROM images WHERE api_cached = TRUE')
                cached_images = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT AVG(rating) FROM images WHERE rating > 0')
                avg_rating = cursor.fetchone()[0] or 0
                
                cursor = conn.execute('SELECT format, COUNT(*) FROM images GROUP BY format')
                format_counts = dict(cursor.fetchall())
                
                return {
                    'total_images': total_images,
                    'cached_images': cached_images,
                    'average_rating': round(avg_rating, 2),
                    'format_distribution': format_counts
                }
        except sqlite3.Error as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}
    
    def _row_to_metadata(self, row: sqlite3.Row) -> ImageMetadata:
        """Convert database row to ImageMetadata object."""
        row_keys = set(row.keys())
        return ImageMetadata(
            file_path=row['file_path'],
            filename=row['filename'],
            file_size=row['file_size'],
            width=row['width'],
            height=row['height'],
            format=row['format'],
            created_date=self._parse_datetime(row['created_date']) or datetime.now(),
            modified_date=self._parse_datetime(row['modified_date']) or datetime.now(),
            exif_data=json.loads(row['exif_data']) if row['exif_data'] else {},
            tags=json.loads(row['tags']) if row['tags'] else [],
            categories=json.loads(row['categories']) if row['categories'] else [],
            keywords=json.loads(row['keywords']) if row['keywords'] else [],
            rating=row['rating'],
            description=row['description'] or '',
            classification=row['classification'] or '',
            ai_raw=row['ai_raw'] if 'ai_raw' in row_keys and row['ai_raw'] else '',
            ai_provider=row['ai_provider'] if 'ai_provider' in row_keys and row['ai_provider'] else '',
            ai_model=row['ai_model'] if 'ai_model' in row_keys and row['ai_model'] else '',
            ai_timestamp=row['ai_timestamp'] if 'ai_timestamp' in row_keys and row['ai_timestamp'] else '',
            embedding=json.loads(row['embedding']) if row['embedding'] else None,
            api_cached=bool(row['api_cached']),
            cache_date=self._parse_datetime(row['cache_date'])
        )
    
    def cleanup_cache(self, max_age_days: int = 30):
        """Remove old cached API responses."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cutoff_date = datetime.now() - timedelta(days=max_age_days)
                cursor = conn.execute(
                    'UPDATE images SET api_cached = FALSE, cache_date = NULL WHERE cache_date < ?',
                    (self._serialize_datetime(cutoff_date),)
                )
                conn.commit()
                self.logger.info(f"Cleaned up {cursor.rowcount} old cache entries")
        except sqlite3.Error as e:
            self.logger.error(f"Error cleaning up cache: {e}")
