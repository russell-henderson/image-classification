"""
Metadata panel component for editing image metadata and tags.
"""

import asyncio
import json
import logging
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime

try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    CTK_AVAILABLE = False
    ctk = tk

from PIL import Image, ImageTk, ExifTags

from core.database import DatabaseManager, ImageMetadata
from core.classifier import ClassificationEngine


class MetadataPanel(tk.Frame):
    """Panel for viewing and editing image metadata."""
    
    def __init__(self, parent, classifier: ClassificationEngine, db_manager: DatabaseManager,
                 on_metadata_change: Optional[Callable[[str, str, Any], None]] = None):
        super().__init__(parent)
        
        self.classifier = classifier
        self.db_manager = db_manager
        self.on_metadata_change = on_metadata_change
        self.logger = logging.getLogger(__name__)
        
        # Current metadata
        self.current_metadata: Optional[ImageMetadata] = None
        
        # Variables for form fields
        self.rating_var = tk.IntVar()
        self.description_var = tk.StringVar()
        self.tags_var = tk.StringVar()
        self.keywords_var = tk.StringVar()
        self.categories_var = tk.StringVar()
        
        # Bind change events
        self.rating_var.trace('w', self._on_rating_change)
        self.description_var.trace('w', self._on_description_change)
        self.tags_var.trace('w', self._on_tags_change)
        self.keywords_var.trace('w', self._on_keywords_change)
        self.categories_var.trace('w', self._on_categories_change)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the user interface."""
        self.grid_columnconfigure(0, weight=1)
        
        # Create scrollable frame
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack scrolling components
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Main content frame
        self.content_frame = scrollable_frame
        self.content_frame.grid_columnconfigure(0, weight=1)
        
        # Create sections
        self._create_preview_section()
        self._create_basic_info_section()
        self._create_rating_section()
        self._create_description_section()
        self._create_tags_section()
        self._create_classification_section()
        self._create_technical_info_section()
        self._create_action_buttons()
    
    def _create_section_header(self, parent, text: str, row: int) -> int:
        """Create a section header and return the next row."""
        header_frame = tk.Frame(parent, bg="lightgray", height=25)
        header_frame.grid(row=row, column=0, sticky="ew", pady=(10, 5))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)
        
        tk.Label(header_frame, text=text, font=("Arial", 10, "bold"), 
                bg="lightgray").grid(row=0, column=0, sticky="w", padx=5)
        
        return row + 1
    
    def _create_preview_section(self):
        """Create image preview section."""
        row = 0
        row = self._create_section_header(self.content_frame, "Preview", row)
        
        # Preview frame
        preview_frame = tk.Frame(self.content_frame, relief=tk.SUNKEN, borderwidth=2, 
                                height=200, bg="white")
        preview_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
        preview_frame.grid_propagate(False)
        preview_frame.grid_columnconfigure(0, weight=1)
        preview_frame.grid_rowconfigure(0, weight=1)
        
        self.preview_label = tk.Label(preview_frame, text="No image selected", 
                                     bg="white", fg="gray")
        self.preview_label.grid(row=0, column=0)
        
        self.current_row = row + 1
    
    def _create_basic_info_section(self):
        """Create basic information section."""
        row = self._create_section_header(self.content_frame, "Basic Information", self.current_row)
        
        info_frame = tk.Frame(self.content_frame)
        info_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
        info_frame.grid_columnconfigure(1, weight=1)
        
        # File information labels
        self.info_labels = {}
        info_fields = [
            ("Filename:", "filename"),
            ("Size:", "size"),
            ("Dimensions:", "dimensions"),
            ("Format:", "format"),
            ("Created:", "created"),
            ("Modified:", "modified")
        ]
        
        for i, (label_text, field_name) in enumerate(info_fields):
            tk.Label(info_frame, text=label_text, font=("Arial", 9, "bold")).grid(
                row=i, column=0, sticky="w", padx=5, pady=2)
            
            label = tk.Label(info_frame, text="", font=("Arial", 9), anchor="w")
            label.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            self.info_labels[field_name] = label
        
        self.current_row = row + 1
    
    def _create_rating_section(self):
        """Create rating section."""
        row = self._create_section_header(self.content_frame, "Rating", self.current_row)
        
        rating_frame = tk.Frame(self.content_frame)
        rating_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
        
        tk.Label(rating_frame, text="Rating:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        # Star rating buttons
        self.star_buttons = []
        for i in range(1, 6):
            btn = tk.Button(rating_frame, text="☆", font=("Arial", 16), 
                           command=lambda r=i: self._set_rating(r),
                           relief=tk.FLAT, borderwidth=0)
            btn.pack(side=tk.LEFT, padx=2)
            self.star_buttons.append(btn)
        
        # Clear rating button
        tk.Button(rating_frame, text="Clear", command=lambda: self._set_rating(0)).pack(side=tk.LEFT, padx=10)
        
        self.current_row = row + 1
    
    def _create_description_section(self):
        """Create description section."""
        row = self._create_section_header(self.content_frame, "Description", self.current_row)
        
        desc_frame = tk.Frame(self.content_frame)
        desc_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
        desc_frame.grid_columnconfigure(0, weight=1)
        
        # Description text area
        self.description_text = tk.Text(desc_frame, height=4, wrap=tk.WORD, font=("Arial", 9))
        desc_scrollbar = ttk.Scrollbar(desc_frame, orient="vertical", command=self.description_text.yview)
        self.description_text.configure(yscrollcommand=desc_scrollbar.set)
        
        self.description_text.grid(row=0, column=0, sticky="ew", pady=2)
        desc_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Bind text change
        self.description_text.bind('<KeyRelease>', self._on_description_text_change)
        
        self.current_row = row + 1
    
    def _create_tags_section(self):
        """Create tags and keywords section."""
        row = self._create_section_header(self.content_frame, "Tags & Keywords", self.current_row)
        
        tags_frame = tk.Frame(self.content_frame)
        tags_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
        tags_frame.grid_columnconfigure(1, weight=1)
        
        # Tags
        tk.Label(tags_frame, text="Tags:", font=("Arial", 9, "bold")).grid(
            row=0, column=0, sticky="nw", padx=5, pady=2)
        self.tags_entry = tk.Entry(tags_frame, textvariable=self.tags_var, font=("Arial", 9))
        self.tags_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        
        # Keywords
        tk.Label(tags_frame, text="Keywords:", font=("Arial", 9, "bold")).grid(
            row=1, column=0, sticky="nw", padx=5, pady=2)
        self.keywords_entry = tk.Entry(tags_frame, textvariable=self.keywords_var, font=("Arial", 9))
        self.keywords_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        
        # Categories
        tk.Label(tags_frame, text="Categories:", font=("Arial", 9, "bold")).grid(
            row=2, column=0, sticky="nw", padx=5, pady=2)
        self.categories_entry = tk.Entry(tags_frame, textvariable=self.categories_var, font=("Arial", 9))
        self.categories_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        
        # Help text
        help_text = tk.Label(tags_frame, text="Separate multiple items with commas", 
                            font=("Arial", 8), fg="gray")
        help_text.grid(row=3, column=1, sticky="ew", padx=5, pady=2)
        
        self.current_row = row + 1
    
    def _create_classification_section(self):
        """Create AI classification section."""
        row = self._create_section_header(self.content_frame, "AI Classification", self.current_row)
        
        class_frame = tk.Frame(self.content_frame)
        class_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
        class_frame.grid_columnconfigure(0, weight=1)
        
        # Classification result text area
        self.classification_text = tk.Text(class_frame, height=6, wrap=tk.WORD, 
                                          font=("Arial", 9), state=tk.DISABLED)
        class_scrollbar = ttk.Scrollbar(class_frame, orient="vertical", 
                                       command=self.classification_text.yview)
        self.classification_text.configure(yscrollcommand=class_scrollbar.set)
        
        self.classification_text.grid(row=0, column=0, sticky="ew", pady=2)
        class_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Classification buttons
        btn_frame = tk.Frame(class_frame)
        btn_frame.grid(row=1, column=0, sticky="ew", pady=5)
        
        tk.Button(btn_frame, text="Classify Image", 
                 command=self._classify_current_image).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Clear Classification", 
                 command=self._clear_classification).pack(side=tk.LEFT, padx=5)
        
        self.current_row = row + 1
    
    def _create_technical_info_section(self):
        """Create technical information section."""
        row = self._create_section_header(self.content_frame, "Technical Information", self.current_row)
        
        tech_frame = tk.Frame(self.content_frame)
        tech_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
        tech_frame.grid_columnconfigure(0, weight=1)
        
        # EXIF data text area
        self.exif_text = tk.Text(tech_frame, height=8, wrap=tk.WORD, 
                                font=("Courier", 8), state=tk.DISABLED)
        exif_scrollbar = ttk.Scrollbar(tech_frame, orient="vertical", command=self.exif_text.yview)
        self.exif_text.configure(yscrollcommand=exif_scrollbar.set)
        
        self.exif_text.grid(row=0, column=0, sticky="ew", pady=2)
        exif_scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.current_row = row + 1
    
    def _create_action_buttons(self):
        """Create action buttons."""
        row = self._create_section_header(self.content_frame, "Actions", self.current_row)
        
        btn_frame = tk.Frame(self.content_frame)
        btn_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
        
        tk.Button(btn_frame, text="Save Changes", command=self._save_changes).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Revert Changes", command=self._revert_changes).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Export Metadata", command=self._export_metadata).pack(side=tk.LEFT, padx=5)
    
    def load_metadata(self, metadata: ImageMetadata):
        """Load metadata into the panel."""
        self.current_metadata = metadata
        
        # Update preview image
        self._update_preview()
        
        # Update basic information
        self._update_basic_info()
        
        # Update editable fields
        self._updating_ui = True  # Flag to prevent change events
        try:
            self.rating_var.set(metadata.rating)
            self.description_text.delete(1.0, tk.END)
            self.description_text.insert(1.0, metadata.description)
            self._populate_fields_from_metadata(metadata)
            
            # Update star display
            self._update_star_display()
            
            # Update classification display
            self._update_classification_display()
        finally:
            self._updating_ui = False

    def _populate_fields_from_metadata(self, metadata: ImageMetadata):
        """Populate tags/keywords/categories and technical info."""
        was_updating = getattr(self, "_updating_ui", False)
        self._updating_ui = True

        def _set_entry(entry, value):
            entry.delete(0, "end")
            if isinstance(value, list):
                entry.insert(0, ", ".join(value))
            else:
                entry.insert(0, value or "")

        _set_entry(self.tags_entry, getattr(metadata, "tags", []))
        _set_entry(self.keywords_entry, getattr(metadata, "keywords", []))
        _set_entry(self.categories_entry, getattr(metadata, "categories", []))

        image_path = getattr(metadata, "file_path", None)
        tech_text = self._build_technical_info(image_path) if image_path else "No file selected"
        self._set_exif_text(tech_text)

        self._set_classification_text(metadata)

        self._updating_ui = was_updating

    def _set_classification_text(self, metadata: ImageMetadata) -> None:
        ai_provider = getattr(metadata, "ai_provider", "")
        ai_model = getattr(metadata, "ai_model", "")
        ai_ts = getattr(metadata, "ai_timestamp", "")
        ai_raw = getattr(metadata, "ai_raw", "")

        header_lines = []
        if ai_provider or ai_model:
            header_lines.append(f"Classified using: {ai_provider} / {ai_model}".strip())
        if ai_ts:
            header_lines.append(f"Timestamp: {ai_ts}".strip())

        panel_text = ""
        if header_lines:
            panel_text += "\n".join(header_lines) + "\n\n"
        panel_text += ai_raw or "(No AI output stored)"

        self.classification_text.configure(state="normal")
        self.classification_text.delete("1.0", "end")
        self.classification_text.insert("1.0", panel_text)
        self.classification_text.configure(state="disabled")

    def _set_exif_text(self, text: str) -> None:
        self.exif_text.configure(state="normal")
        self.exif_text.delete("1.0", "end")
        self.exif_text.insert("1.0", text or "")
        self.exif_text.configure(state="disabled")

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
    
    def _update_preview(self):
        """Update the preview image."""
        if not self.current_metadata:
            return
        
        try:
            from core.image_handler import ImageHandler
            handler = ImageHandler()
            
            # Create thumbnail
            thumbnail = handler.create_thumbnail(self.current_metadata.file_path, 180)
            if thumbnail:
                tk_image = ImageTk.PhotoImage(thumbnail)
                self.preview_label.config(image=tk_image, text="")
                self.preview_label.image = tk_image  # Keep reference
            else:
                self.preview_label.config(image="", text="Preview not available")
                
        except Exception as e:
            self.logger.error(f"Error updating preview: {e}")
            self.preview_label.config(image="", text="Preview error")
    
    def _update_basic_info(self):
        """Update basic information display."""
        if not self.current_metadata:
            return
        
        metadata = self.current_metadata
        
        # Format file size
        size_mb = metadata.file_size / (1024 * 1024)
        size_text = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{metadata.file_size} bytes"
        
        # Update labels
        self.info_labels["filename"].config(text=metadata.filename)
        self.info_labels["size"].config(text=size_text)
        self.info_labels["dimensions"].config(text=f"{metadata.width} × {metadata.height}")
        self.info_labels["format"].config(text=metadata.format)
        self.info_labels["created"].config(text=metadata.created_date.strftime("%Y-%m-%d %H:%M"))
        self.info_labels["modified"].config(text=metadata.modified_date.strftime("%Y-%m-%d %H:%M"))
    
    def _update_star_display(self):
        """Update star rating display."""
        rating = self.rating_var.get()
        for i, btn in enumerate(self.star_buttons):
            if i < rating:
                btn.config(text="★", fg="gold")
            else:
                btn.config(text="☆", fg="black")
    
    def _update_classification_display(self):
        """Update classification display."""
        if self.current_metadata:
            self._set_classification_text(self.current_metadata)
            return

        self.classification_text.config(state=tk.NORMAL)
        self.classification_text.delete(1.0, tk.END)
        
        if self.current_metadata and self.current_metadata.classification:
            try:
                classification = json.loads(self.current_metadata.classification)
                
                # Format classification data
                text_lines = []
                if 'description' in classification:
                    text_lines.append(f"Description: {classification['description']}")
                if 'subjects' in classification:
                    text_lines.append(f"Subjects: {classification['subjects']}")
                if 'scene' in classification:
                    text_lines.append(f"Scene: {classification['scene']}")
                if 'mood' in classification:
                    text_lines.append(f"Mood: {classification['mood']}")
                if 'quality' in classification:
                    text_lines.append(f"Quality: {classification['quality']}")
                if 'api_used' in classification:
                    text_lines.append(f"\\nClassified using: {classification['api_used']}")
                if 'timestamp' in classification:
                    text_lines.append(f"Timestamp: {classification['timestamp']}")
                
                self.classification_text.insert(1.0, "\\n".join(text_lines))
                
            except json.JSONDecodeError:
                self.classification_text.insert(1.0, "Classification data format error")
        else:
            self.classification_text.insert(1.0, "No classification available")
        
        self.classification_text.config(state=tk.DISABLED)
    
    def _update_exif_display(self):
        """Update EXIF data display."""
        self.exif_text.config(state=tk.NORMAL)
        self.exif_text.delete(1.0, tk.END)
        
        if self.current_metadata and self.current_metadata.exif_data:
            # Format EXIF data
            exif_lines = []
            for key, value in self.current_metadata.exif_data.items():
                # Truncate very long values
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                exif_lines.append(f"{key}: {value_str}")
            
            self.exif_text.insert(1.0, "\\n".join(exif_lines))
        else:
            self.exif_text.insert(1.0, "No EXIF data available")
        
        self.exif_text.config(state=tk.DISABLED)
    
    def _set_rating(self, rating: int):
        """Set the rating value."""
        self.rating_var.set(rating)
        self._update_star_display()
    
    def _on_rating_change(self, *args):
        """Handle rating change."""
        if hasattr(self, '_updating_ui') and self._updating_ui:
            return
        if self.current_metadata and self.on_metadata_change:
            self.on_metadata_change(self.current_metadata.file_path, 'rating', self.rating_var.get())
    
    def _on_description_change(self, *args):
        """Handle description change."""
        if hasattr(self, '_updating_ui') and self._updating_ui:
            return
        if self.current_metadata and self.on_metadata_change:
            self.on_metadata_change(self.current_metadata.file_path, 'description', self.description_var.get())
    
    def _on_description_text_change(self, event):
        """Handle description text area change."""
        if hasattr(self, '_updating_ui') and self._updating_ui:
            return
        if self.current_metadata and self.on_metadata_change:
            text = self.description_text.get(1.0, tk.END).strip()
            self.on_metadata_change(self.current_metadata.file_path, 'description', text)
    
    def _on_tags_change(self, *args):
        """Handle tags change."""
        if hasattr(self, '_updating_ui') and self._updating_ui:
            return
        if self.current_metadata and self.on_metadata_change:
            tags = [tag.strip() for tag in self.tags_var.get().split(',') if tag.strip()]
            self.on_metadata_change(self.current_metadata.file_path, 'tags', tags)
    
    def _on_keywords_change(self, *args):
        """Handle keywords change."""
        if hasattr(self, '_updating_ui') and self._updating_ui:
            return
        if self.current_metadata and self.on_metadata_change:
            keywords = [kw.strip() for kw in self.keywords_var.get().split(',') if kw.strip()]
            self.on_metadata_change(self.current_metadata.file_path, 'keywords', keywords)
    
    def _on_categories_change(self, *args):
        """Handle categories change."""
        if hasattr(self, '_updating_ui') and self._updating_ui:
            return
        if self.current_metadata and self.on_metadata_change:
            categories = [cat.strip() for cat in self.categories_var.get().split(',') if cat.strip()]
            self.on_metadata_change(self.current_metadata.file_path, 'categories', categories)
    
    def _classify_current_image(self):
        """Classify the current image."""
        if not self.current_metadata:
            messagebox.showwarning("No Image", "No image selected for classification.")
            return

        if not self.classifier:
            messagebox.showerror("Classification Error", "Classifier is not available.")
            return

        image_path = getattr(self.current_metadata, "file_path", None)
        if not image_path:
            messagebox.showwarning("No Path", "Selected image has no filepath.")
            return

        threading.Thread(
            target=self._classify_current_image_async,
            args=(image_path,),
            daemon=True,
        ).start()

    def _classify_current_image_async(self, image_path: str):
        """Runs classification off the UI thread and schedules UI updates."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            metadata = loop.run_until_complete(
                self.classifier.process_image(image_path, force_refresh=True)
            )

            self.after(0, lambda: self._on_classify_complete(image_path, metadata))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Classification Error", str(e)))
        finally:
            try:
                loop.close()
            except Exception:
                pass

    def _on_classify_complete(self, image_path: str, metadata: Optional[ImageMetadata]):
        """Apply returned metadata to the panel fields."""
        if metadata:
            self.load_metadata(metadata)
            self._populate_fields_from_metadata(self.current_metadata)
        else:
            messagebox.showerror("Classification Error", "Classification failed.")
    
    def _clear_classification(self):
        """Clear the classification data."""
        if self.current_metadata and self.on_metadata_change:
            self.on_metadata_change(self.current_metadata.file_path, 'classification', '')
            self.on_metadata_change(self.current_metadata.file_path, 'api_cached', False)
            self._update_classification_display()
    
    def _save_changes(self):
        """Save all changes."""
        if not self.current_metadata:
            return
        
        try:
            # Get current values from UI
            description = self.description_text.get(1.0, tk.END).strip()
            tags = [tag.strip() for tag in self.tags_var.get().split(',') if tag.strip()]
            keywords = [kw.strip() for kw in self.keywords_var.get().split(',') if kw.strip()]
            categories = [cat.strip() for cat in self.categories_var.get().split(',') if cat.strip()]
            rating = self.rating_var.get()
            
            # Update database
            updates = {
                'description': description,
                'tags': tags,
                'keywords': keywords,
                'categories': categories,
                'rating': rating
            }
            
            success = self.db_manager.update_metadata(self.current_metadata.file_path, **updates)
            
            if success:
                messagebox.showinfo("Success", "Changes saved successfully.")
                # Update local metadata object
                self.current_metadata.description = description
                self.current_metadata.tags = tags
                self.current_metadata.keywords = keywords
                self.current_metadata.categories = categories
                self.current_metadata.rating = rating
            else:
                messagebox.showerror("Error", "Failed to save changes.")
                
        except Exception as e:
            self.logger.error(f"Error saving changes: {e}")
            messagebox.showerror("Error", f"Error saving changes: {e}")
    
    def _revert_changes(self):
        """Revert all changes to original values."""
        if self.current_metadata:
            # Reload metadata from database
            fresh_metadata = self.db_manager.get_image(self.current_metadata.file_path)
            if fresh_metadata:
                self.load_metadata(fresh_metadata)
    
    def _export_metadata(self):
        """Export metadata to file."""
        if not self.current_metadata:
            return
        
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            title="Export Metadata",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                # Prepare metadata for export
                export_data = {
                    'filename': self.current_metadata.filename,
                    'file_path': self.current_metadata.file_path,
                    'dimensions': f"{self.current_metadata.width}x{self.current_metadata.height}",
                    'format': self.current_metadata.format,
                    'file_size': self.current_metadata.file_size,
                    'created_date': self.current_metadata.created_date.isoformat(),
                    'modified_date': self.current_metadata.modified_date.isoformat(),
                    'rating': self.current_metadata.rating,
                    'description': self.current_metadata.description,
                    'tags': self.current_metadata.tags,
                    'keywords': self.current_metadata.keywords,
                    'categories': self.current_metadata.categories,
                    'exif_data': self.current_metadata.exif_data,
                    'classification': self.current_metadata.classification,
                    'api_cached': self.current_metadata.api_cached
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                messagebox.showinfo("Success", f"Metadata exported to {filename}")
                
            except Exception as e:
                self.logger.error(f"Error exporting metadata: {e}")
                messagebox.showerror("Error", f"Error exporting metadata: {e}")
