"""
Metadata panel component for editing image metadata and tags.
"""

import asyncio
import json
import logging
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
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

    STATUS_IDLE = "idle"
    STATUS_RECEIVED = "received"
    STATUS_WORKING = "working"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    
    def __init__(self, parent, classifier: ClassificationEngine, db_manager: DatabaseManager,
                 on_metadata_change: Optional[Callable[[str, str, Any], None]] = None,
                 on_file_request: Optional[Callable[..., Dict[str, Any]]] = None):
        super().__init__(parent)
        
        self.classifier = classifier
        self.db_manager = db_manager
        self.on_metadata_change = on_metadata_change
        self.on_file_request = on_file_request
        self.logger = logging.getLogger(__name__)
        
        # Current metadata
        self.current_metadata: Optional[ImageMetadata] = None
        
        # Variables for form fields
        self.rating_var = tk.IntVar()
        self.description_var = tk.StringVar()
        self.tags_var = tk.StringVar()
        self.keywords_var = tk.StringVar()
        self.categories_var = tk.StringVar()
        self.story_complexity_var = tk.StringVar(value="Simple")
        self.story_chaos_var = tk.BooleanVar(value=False)
        self.preview_lightbox_window = None
        self.preview_lightbox_label = None
        self.preview_lightbox_source = None
        self.preview_lightbox_image = None
        self._delete_dialog = None
        self.realtime_log_lines: List[str] = []
        self.saved_stories_expanded = False
        
        # Bind change events
        self.rating_var.trace('w', self._on_rating_change)
        self.description_var.trace('w', self._on_description_change)
        self.tags_var.trace('w', self._on_tags_change)
        self.keywords_var.trace('w', self._on_keywords_change)
        self.categories_var.trace('w', self._on_categories_change)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the user interface."""
        self.configure(bg="#eef1f4")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.content_frame = tk.Frame(self, bg="#eef1f4")
        self.content_frame.grid(row=0, column=0, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(2, weight=1)
        self.content_frame.grid_rowconfigure(4, weight=1)

        self._build_dashboard()

    def _build_dashboard(self):
        """Create the fixed-height dashboard layout."""
        top_panel = self._make_panel(self.content_frame, row=0, title="Preview & Status")
        top_panel.grid_columnconfigure(0, weight=1, uniform="top")
        top_panel.grid_columnconfigure(1, weight=1, uniform="top")
        top_panel.grid_rowconfigure(0, weight=1)

        self._build_status_panel(top_panel)
        self._build_preview_panel(top_panel)

        action_panel = self._make_panel(self.content_frame, row=1, title="Actions")
        action_panel.grid_columnconfigure(0, weight=1)
        self._build_action_panel(action_panel)

        results_panel = self._make_panel(self.content_frame, row=2, title="Classification Results", sticky="nsew")
        results_panel.grid_columnconfigure(0, weight=1)
        results_panel.grid_rowconfigure(1, weight=1)
        self._build_results_panel(results_panel)

        story_panel = self._make_panel(self.content_frame, row=3, title="Saved Stories")
        story_panel.grid_columnconfigure(0, weight=1)
        self._build_story_panel(story_panel)

        footer = tk.Frame(self.content_frame, bg="#eef1f4")
        footer.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))
        footer.grid_columnconfigure(0, weight=1, uniform="footer")
        footer.grid_columnconfigure(1, weight=1, uniform="footer")
        footer.grid_rowconfigure(0, weight=1)

        basic_panel = self._make_panel(footer, row=0, title="Basic Information", column=0, sticky="nsew", padx=(0, 5), pady=0)
        basic_panel.grid_columnconfigure(1, weight=1)
        self._build_basic_info_panel(basic_panel)

        tech_panel = self._make_panel(footer, row=0, title="Technical Information", column=1, sticky="nsew", padx=(5, 0), pady=0)
        tech_panel.grid_columnconfigure(0, weight=1)
        tech_panel.grid_rowconfigure(0, weight=1)
        self._build_technical_panel(tech_panel)

    def _make_panel(self, parent, row: int, title: str, column: int = 0, sticky: str = "ew", padx=10, pady=(10, 0)):
        """Create a labeled panel with consistent spacing."""
        panel = tk.LabelFrame(
            parent,
            text=title,
            font=("Arial", 10, "bold"),
            bg="white",
            fg="#1f2933",
            bd=1,
            relief=tk.GROOVE,
            padx=10,
            pady=10,
        )
        panel.grid(row=row, column=column, sticky=sticky, padx=padx, pady=pady)
        return panel

    def _make_entry(self, parent, variable) -> tk.Entry:
        """Create a standard entry widget."""
        return tk.Entry(parent, textvariable=variable, font=("Arial", 9), relief=tk.SOLID, bd=1)

    def _build_status_panel(self, parent):
        """Build the left-side status and live log area."""
        status_frame = tk.Frame(parent, bg="white")
        status_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        status_frame.grid_columnconfigure(0, weight=1)

        tk.Label(
            status_frame,
            text="Classification Status",
            font=("Arial", 10, "bold"),
            bg="white",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.status_steps = {}
        for idx, (key, label_text) in enumerate((
            ("received", "1. Command received"),
            ("working", "2. Running LLaVA"),
            ("completed", "3. Completed"),
        ), start=1):
            row_frame = tk.Frame(status_frame, bg="white")
            row_frame.grid(row=idx, column=0, sticky="ew", pady=3)
            row_frame.grid_columnconfigure(1, weight=1)

            indicator = tk.Label(row_frame, width=2, height=1, bg="#d9d9d9", relief=tk.FLAT)
            indicator.grid(row=0, column=0, sticky="w")
            label = tk.Label(row_frame, text=label_text, font=("Arial", 9), bg="white", fg="#666666", anchor="w")
            label.grid(row=0, column=1, sticky="ew", padx=(8, 0))
            self.status_steps[key] = (indicator, label)

        self.status_message_label = tk.Label(
            status_frame,
            text="Waiting for a classification request.",
            font=("Arial", 8),
            bg="white",
            fg="#666666",
            anchor="w",
            justify=tk.LEFT,
            wraplength=240,
        )
        self.status_message_label.grid(row=4, column=0, sticky="ew", pady=(8, 10))

        tk.Label(
            status_frame,
            text="Real-time Log",
            font=("Arial", 9, "bold"),
            bg="white",
            anchor="w",
        ).grid(row=5, column=0, sticky="ew", pady=(0, 4))

        self.realtime_log_text = tk.Text(
            status_frame,
            height=3,
            wrap=tk.WORD,
            font=("Consolas", 8),
            relief=tk.SOLID,
            bd=1,
            state=tk.DISABLED,
        )
        self.realtime_log_text.grid(row=6, column=0, sticky="ew")

    def _build_preview_panel(self, parent):
        """Build the top-right image preview panel."""
        self.preview_container = tk.Frame(parent, bg="white", height=280)
        self.preview_container.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.preview_container.grid_columnconfigure(0, weight=1)
        self.preview_container.grid_rowconfigure(0, weight=1)
        self.preview_container.grid_propagate(False)

        self.preview_label = tk.Label(
            self.preview_container,
            text="No image selected",
            bg="white",
            fg="gray",
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew")
        self.preview_label.bind("<Double-Button-1>", self._open_preview_lightbox)

        self._set_classification_status(self.STATUS_IDLE)

    def _build_action_panel(self, parent):
        """Build the primary action row and story controls."""
        button_row = tk.Frame(parent, bg="white")
        button_row.grid(row=0, column=0, sticky="ew")

        tk.Button(button_row, text="Classify", command=self._classify_current_image).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(button_row, text="Clear", command=self._clear_classification).pack(side=tk.LEFT, padx=6)
        tk.Button(button_row, text="Create", command=self._launch_sidecar).pack(side=tk.LEFT, padx=6)
        tk.Button(button_row, text="Save", command=self._save_changes, bg="#1f6feb", fg="white").pack(side=tk.LEFT, padx=6)
        tk.Button(button_row, text="Delete", command=self._confirm_delete_current_image, bg="#c0392b", fg="white").pack(side=tk.LEFT, padx=6)

        story_row = tk.Frame(parent, bg="white")
        story_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        story_row.grid_columnconfigure(5, weight=1)

        tk.Label(story_row, text="Story Mode", font=("Arial", 9, "bold"), bg="white").grid(row=0, column=0, sticky="w", padx=(0, 6))
        tk.Checkbutton(
            story_row,
            text="Chaos / Spicy",
            variable=self.story_chaos_var,
            onvalue=True,
            offvalue=False,
            bg="white",
        ).grid(row=0, column=1, sticky="w", padx=(0, 12))
        tk.Label(story_row, text="Complexity", font=("Arial", 9, "bold"), bg="white").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.story_complexity_combo = ttk.Combobox(
            story_row,
            textvariable=self.story_complexity_var,
            values=["Simple", "Complex"],
            state="readonly",
            width=10,
        )
        self.story_complexity_combo.grid(row=0, column=3, sticky="w")

    def _build_results_panel(self, parent):
        """Build the classification results area."""
        tk.Label(parent, text="Description", font=("Arial", 9, "bold"), bg="white").grid(row=0, column=0, sticky="w")

        desc_frame = tk.Frame(parent, bg="white")
        desc_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 10))
        desc_frame.grid_columnconfigure(0, weight=1)
        desc_frame.grid_rowconfigure(0, weight=1)
        self.description_text = tk.Text(desc_frame, height=4, wrap=tk.WORD, font=("Arial", 9), relief=tk.SOLID, bd=1)
        desc_scrollbar = ttk.Scrollbar(desc_frame, orient="vertical", command=self.description_text.yview)
        self.description_text.configure(yscrollcommand=desc_scrollbar.set)
        self.description_text.grid(row=0, column=0, sticky="nsew")
        desc_scrollbar.grid(row=0, column=1, sticky="ns")
        self.description_text.bind('<KeyRelease>', self._on_description_text_change)

        meta_grid = tk.Frame(parent, bg="white")
        meta_grid.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        meta_grid.grid_columnconfigure(1, weight=1, uniform="meta")
        meta_grid.grid_columnconfigure(3, weight=1, uniform="meta")

        tk.Label(meta_grid, text="Tags", font=("Arial", 9, "bold"), bg="white").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        self.tags_entry = self._make_entry(meta_grid, self.tags_var)
        self.tags_entry.grid(row=0, column=1, sticky="ew", pady=4)

        tk.Label(meta_grid, text="Keywords", font=("Arial", 9, "bold"), bg="white").grid(row=0, column=2, sticky="w", padx=(12, 6), pady=4)
        self.keywords_entry = self._make_entry(meta_grid, self.keywords_var)
        self.keywords_entry.grid(row=0, column=3, sticky="ew", pady=4)

        tk.Label(meta_grid, text="Categories", font=("Arial", 9, "bold"), bg="white").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=4)
        self.categories_entry = self._make_entry(meta_grid, self.categories_var)
        self.categories_entry.grid(row=1, column=1, sticky="ew", pady=4)

        tk.Label(meta_grid, text="Rating", font=("Arial", 9, "bold"), bg="white").grid(row=1, column=2, sticky="w", padx=(12, 6), pady=4)
        rating_frame = tk.Frame(meta_grid, bg="white")
        rating_frame.grid(row=1, column=3, sticky="w", pady=4)
        self.star_buttons = []
        for i in range(1, 6):
            btn = tk.Button(
                rating_frame,
                text="☆",
                font=("Arial", 14),
                command=lambda r=i: self._set_rating(r),
                relief=tk.FLAT,
                borderwidth=0,
                bg="white",
            )
            btn.pack(side=tk.LEFT, padx=1)
            self.star_buttons.append(btn)
        tk.Button(rating_frame, text="Clear", command=lambda: self._set_rating(0)).pack(side=tk.LEFT, padx=(8, 0))

        tk.Label(parent, text="AI Output", font=("Arial", 9, "bold"), bg="white").grid(row=3, column=0, sticky="w")
        ai_frame = tk.Frame(parent, bg="white")
        ai_frame.grid(row=4, column=0, sticky="nsew", pady=(4, 0))
        ai_frame.grid_columnconfigure(0, weight=1)
        ai_frame.grid_rowconfigure(0, weight=1)
        self.classification_text = tk.Text(ai_frame, height=8, wrap=tk.WORD, font=("Arial", 9), state=tk.DISABLED, relief=tk.SOLID, bd=1)
        class_scrollbar = ttk.Scrollbar(ai_frame, orient="vertical", command=self.classification_text.yview)
        self.classification_text.configure(yscrollcommand=class_scrollbar.set)
        self.classification_text.grid(row=0, column=0, sticky="nsew")
        class_scrollbar.grid(row=0, column=1, sticky="ns")

    def _build_story_panel(self, parent):
        """Build the collapsible saved stories panel."""
        self.story_toggle_button = tk.Button(
            parent,
            text="Show Saved Stories",
            command=self._toggle_saved_stories,
            anchor="w",
        )
        self.story_toggle_button.grid(row=0, column=0, sticky="ew")

        self.story_body = tk.Frame(parent, bg="white")
        self.story_body.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.story_body.grid_columnconfigure(0, weight=1)

        self.story_listbox = tk.Listbox(self.story_body, height=4, exportselection=False)
        self.story_listbox.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.story_listbox.bind("<<ListboxSelect>>", self._on_story_select)

        preview_frame = tk.Frame(self.story_body, bg="white")
        preview_frame.grid(row=1, column=0, sticky="ew")
        preview_frame.grid_columnconfigure(0, weight=1)
        self.story_preview_text = tk.Text(preview_frame, height=5, wrap=tk.WORD, font=("Arial", 9), state=tk.DISABLED, relief=tk.SOLID, bd=1)
        story_preview_scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self.story_preview_text.yview)
        self.story_preview_text.configure(yscrollcommand=story_preview_scrollbar.set)
        self.story_preview_text.grid(row=0, column=0, sticky="ew")
        story_preview_scrollbar.grid(row=0, column=1, sticky="ns")

        story_btn_frame = tk.Frame(self.story_body, bg="white")
        story_btn_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        tk.Button(story_btn_frame, text="Refresh Stories", command=self._refresh_story_history).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(story_btn_frame, text="Copy Story", command=self._copy_selected_story).pack(side=tk.LEFT, padx=5)

        self.story_records: List[Dict[str, Any]] = []
        self._toggle_saved_stories(force=False)

    def _build_basic_info_panel(self, parent):
        """Build the lower-left reference information panel."""
        self.info_labels = {}
        info_fields = [
            ("Filename", "filename"),
            ("Size", "size"),
            ("Dimensions", "dimensions"),
            ("Format", "format"),
            ("Created", "created"),
            ("Modified", "modified"),
        ]
        for row_index, (label_text, field_name) in enumerate(info_fields):
            tk.Label(parent, text=f"{label_text}:", font=("Arial", 9, "bold"), bg="white").grid(
                row=row_index, column=0, sticky="nw", padx=(0, 6), pady=2
            )
            label = tk.Label(parent, text="", font=("Arial", 9), bg="white", anchor="w", justify=tk.LEFT, wraplength=260)
            label.grid(row=row_index, column=1, sticky="ew", pady=2)
            self.info_labels[field_name] = label

        file_button_frame = tk.Frame(parent, bg="white")
        file_button_frame.grid(row=len(info_fields), column=0, columnspan=2, sticky="w", pady=(10, 0))
        tk.Button(file_button_frame, text="Rename", command=self._rename_current_image).pack(side=tk.LEFT)

    def _build_technical_panel(self, parent):
        """Build the lower-right technical metadata panel."""
        exif_frame = tk.Frame(parent, bg="white")
        exif_frame.grid(row=0, column=0, sticky="nsew")
        exif_frame.grid_columnconfigure(0, weight=1)
        exif_frame.grid_rowconfigure(0, weight=1)

        self.exif_text = tk.Text(exif_frame, height=10, wrap=tk.WORD, font=("Courier", 8), state=tk.DISABLED, relief=tk.SOLID, bd=1)
        exif_scrollbar = ttk.Scrollbar(exif_frame, orient="vertical", command=self.exif_text.yview)
        self.exif_text.configure(yscrollcommand=exif_scrollbar.set)
        self.exif_text.grid(row=0, column=0, sticky="nsew")
        exif_scrollbar.grid(row=0, column=1, sticky="ns")

        tech_button_frame = tk.Frame(parent, bg="white")
        tech_button_frame.grid(row=1, column=0, sticky="w", pady=(10, 0))
        tk.Button(tech_button_frame, text="Move to Folder", command=self._move_current_image).pack(side=tk.LEFT)

    def _toggle_saved_stories(self, force: Optional[bool] = None):
        """Expand or collapse the saved stories section."""
        self.saved_stories_expanded = (not self.saved_stories_expanded) if force is None else force
        if self.saved_stories_expanded:
            self.story_body.grid()
            self.story_toggle_button.config(text="Hide Saved Stories")
        else:
            self.story_body.grid_remove()
            self.story_toggle_button.config(text="Show Saved Stories")

    def _append_realtime_log(self, message: str):
        """Append a short line to the three-line realtime console."""
        if not message:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.realtime_log_lines.append(f"[{timestamp}] {message}")
        self.realtime_log_lines = self.realtime_log_lines[-3:]
        self.realtime_log_text.configure(state="normal")
        self.realtime_log_text.delete("1.0", "end")
        self.realtime_log_text.insert("1.0", "\n".join(self.realtime_log_lines))
        self.realtime_log_text.configure(state="disabled")

    def _handle_sidecar_event(self, event: Dict[str, Any]):
        """Receive sidecar status events and mirror them into the live log."""
        message = event.get("message", "").strip()
        if not message:
            return
        source = event.get("source", "bridge")
        self.after(0, lambda: self._append_realtime_log(f"{source}: {message}"))
    
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
        self.preview_container = tk.Frame(self.content_frame, relief=tk.SUNKEN, borderwidth=2,
                                bg="white")
        self.preview_container.grid(row=row, column=0, sticky="ew", padx=(5, 25), pady=5)
        self.preview_container.grid_columnconfigure(1, weight=1)
        self.preview_container.grid_rowconfigure(0, weight=1)

        # Dynamic height constraint for container (max ~40% of typical panel height)
        self.preview_container.configure(height=300) 
        self.preview_container.grid_propagate(False)

        status_frame = tk.Frame(self.preview_container, bg="white", width=170)
        status_frame.grid(row=0, column=0, sticky="nsw", padx=(18, 8), pady=14)
        status_frame.grid_propagate(False)
        status_frame.grid_columnconfigure(0, weight=1)

        tk.Label(
            status_frame,
            text="Classification Status",
            font=("Arial", 9, "bold"),
            bg="white",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.status_steps = {}
        status_rows = [
            ("received", "1. Command received"),
            ("working", "2. Running LLaVA"),
            ("completed", "3. Completed"),
        ]
        for idx, (key, label_text) in enumerate(status_rows, start=1):
            row_frame = tk.Frame(status_frame, bg="white")
            row_frame.grid(row=idx, column=0, sticky="ew", pady=5)
            row_frame.grid_columnconfigure(1, weight=1)

            indicator = tk.Label(
                row_frame,
                width=2,
                height=1,
                bg="#d9d9d9",
                relief=tk.FLAT,
            )
            indicator.grid(row=0, column=0, sticky="w")

            label = tk.Label(
                row_frame,
                text=label_text,
                font=("Arial", 9),
                bg="white",
                fg="#666666",
                anchor="w",
            )
            label.grid(row=0, column=1, sticky="ew", padx=(8, 0))
            self.status_steps[key] = (indicator, label)

        self.status_message_label = tk.Label(
            status_frame,
            text="Waiting for a classification request.",
            font=("Arial", 8),
            bg="white",
            fg="#666666",
            anchor="w",
            justify=tk.LEFT,
            wraplength=150,
        )
        self.status_message_label.grid(row=4, column=0, sticky="ew", pady=(10, 0))

        top_button_frame = tk.Frame(status_frame, bg="white")
        top_button_frame.grid(row=5, column=0, sticky="w", pady=(18, 0))
        tk.Button(
            top_button_frame,
            text="Classify Image",
            command=self._classify_current_image,
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(
            top_button_frame,
            text="Clear Classification",
            command=self._clear_classification,
        ).pack(side=tk.LEFT)

        self.preview_label = tk.Label(self.preview_container, text="No image selected", 
                                     bg="white", fg="gray")
        self.preview_label.grid(row=0, column=1, sticky="nsew")
        self.preview_label.bind("<Double-Button-1>", self._open_preview_lightbox)

        self._set_classification_status(self.STATUS_IDLE)
        
        self.current_row = row + 1

    def _set_classification_status(self, status: str, detail: str = "") -> None:
        """Update the visible classification status steps in the preview area."""
        palette = {
            self.STATUS_IDLE: {
                "received": "#d9d9d9",
                "working": "#d9d9d9",
                "completed": "#d9d9d9",
                "message": detail or "Waiting for a classification request.",
            },
            self.STATUS_RECEIVED: {
                "received": "#38b000",
                "working": "#d9d9d9",
                "completed": "#d9d9d9",
                "message": detail or "Command received. Preparing the classification request.",
            },
            self.STATUS_WORKING: {
                "received": "#38b000",
                "working": "#f4b400",
                "completed": "#d9d9d9",
                "message": detail or "LLaVA is processing the image now.",
            },
            self.STATUS_COMPLETED: {
                "received": "#38b000",
                "working": "#38b000",
                "completed": "#38b000",
                "message": detail or "Classification completed successfully.",
            },
            self.STATUS_FAILED: {
                "received": "#38b000",
                "working": "#db4437",
                "completed": "#db4437",
                "message": detail or "Classification failed.",
            },
        }
        active = palette.get(status, palette[self.STATUS_IDLE])

        for key, (indicator, label) in self.status_steps.items():
            indicator.config(bg=active.get(key, "#d9d9d9"))
            label.config(
                fg="#111111" if active.get(key, "#d9d9d9") != "#d9d9d9" else "#666666"
            )

        self.status_message_label.config(text=active["message"])

    def _handle_classifier_status(self, stage: str, detail: str) -> None:
        """Receive classifier progress updates from the worker thread."""
        self.after(0, lambda: self._set_classification_status(stage, detail))
        self.after(0, lambda: self._append_realtime_log(f"llava:latest: {detail}"))
    
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

        file_button_frame = tk.Frame(info_frame)
        file_button_frame.grid(row=len(info_fields), column=0, columnspan=2, sticky="w", padx=5, pady=(8, 0))
        tk.Button(
            file_button_frame,
            text="Rename",
            command=self._rename_current_image,
        ).pack(side=tk.LEFT, padx=(0, 8))
        
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
        
        tk.Button(btn_frame, text="Create", 
                 command=self._launch_sidecar).pack(side=tk.LEFT, padx=5)

        story_controls = tk.Frame(class_frame)
        story_controls.grid(row=2, column=0, sticky="ew", pady=(2, 4))
        story_controls.grid_columnconfigure(4, weight=1)

        tk.Label(story_controls, text="Story Mode:", font=("Arial", 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=(5, 4)
        )
        tk.Checkbutton(
            story_controls,
            text="Chaos / Spicy",
            variable=self.story_chaos_var,
            onvalue=True,
            offvalue=False,
        ).grid(row=0, column=1, sticky="w", padx=(0, 12))

        tk.Label(story_controls, text="Complexity:", font=("Arial", 9, "bold")).grid(
            row=0, column=2, sticky="w", padx=(0, 4)
        )
        self.story_complexity_combo = ttk.Combobox(
            story_controls,
            textvariable=self.story_complexity_var,
            values=["Simple", "Complex"],
            state="readonly",
            width=10,
        )
        self.story_complexity_combo.grid(row=0, column=3, sticky="w")

        story_help = tk.Label(
            class_frame,
            text="Story controls apply when launching the sidecar with Create.",
            font=("Arial", 8),
            fg="gray",
        )
        story_help.grid(row=3, column=0, sticky="w", padx=5)
        
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

        tech_button_frame = tk.Frame(tech_frame)
        tech_button_frame.grid(row=1, column=0, sticky="w", pady=(8, 0))
        tk.Button(
            tech_button_frame,
            text="Move to Folder",
            command=self._move_current_image,
        ).pack(side=tk.LEFT)
        
        self.current_row = row + 1

    def _create_story_history_section(self):
        """Create saved story history section."""
        row = self._create_section_header(self.content_frame, "Saved Stories", self.current_row)

        story_frame = tk.Frame(self.content_frame)
        story_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
        story_frame.grid_columnconfigure(0, weight=1)

        self.story_listbox = tk.Listbox(story_frame, height=5, exportselection=False)
        self.story_listbox.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.story_listbox.bind("<<ListboxSelect>>", self._on_story_select)

        self.story_preview_text = tk.Text(
            story_frame,
            height=6,
            wrap=tk.WORD,
            font=("Arial", 9),
            state=tk.DISABLED,
        )
        story_preview_scrollbar = ttk.Scrollbar(
            story_frame,
            orient="vertical",
            command=self.story_preview_text.yview,
        )
        self.story_preview_text.configure(yscrollcommand=story_preview_scrollbar.set)
        self.story_preview_text.grid(row=1, column=0, sticky="ew", pady=2)
        story_preview_scrollbar.grid(row=1, column=1, sticky="ns")

        story_btn_frame = tk.Frame(story_frame)
        story_btn_frame.grid(row=2, column=0, sticky="ew", pady=4)
        tk.Button(
            story_btn_frame,
            text="Refresh Stories",
            command=self._refresh_story_history,
        ).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(
            story_btn_frame,
            text="Copy Story",
            command=self._copy_selected_story,
        ).pack(side=tk.LEFT, padx=5)

        self.story_records: List[Dict[str, Any]] = []
        self.current_row = row + 1
    
    def _create_action_buttons(self):
        """Create action buttons."""
        row = self._create_section_header(self.content_frame, "Actions", self.current_row)
        
        btn_frame = tk.Frame(self.content_frame)
        btn_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
        
        tk.Button(
            btn_frame,
            text="Save",
            command=self._save_changes,
            bg="#1f6feb",
            fg="white",
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            btn_frame,
            text="Delete",
            command=self._confirm_delete_current_image,
            bg="#c0392b",
            fg="white",
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Revert Changes", command=self._revert_changes).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Export Metadata", command=self._export_metadata).pack(side=tk.LEFT, padx=5)

    def clear_metadata(self):
        """Clear the panel after file removal or when no selection remains."""
        self.current_metadata = None
        self.preview_label.config(image="", text="No image selected")
        self.preview_label.image = None
        for label in self.info_labels.values():
            label.config(text="")
        self.rating_var.set(0)
        self._update_star_display()
        self.description_text.delete(1.0, tk.END)
        for entry in (self.tags_entry, self.keywords_entry, self.categories_entry):
            entry.delete(0, tk.END)
        self.classification_text.configure(state="normal")
        self.classification_text.delete("1.0", "end")
        self.classification_text.insert("1.0", "(No AI output stored)")
        self.classification_text.configure(state="disabled")
        self._set_exif_text("No file selected")
        self.story_listbox.config(state=tk.NORMAL)
        self.story_listbox.delete(0, tk.END)
        self.story_records = []
        self._set_story_preview_text("")
        self._set_classification_status(self.STATUS_IDLE)
    
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

        if metadata.classification:
            self._set_classification_status(self.STATUS_COMPLETED)
        else:
            self._set_classification_status(self.STATUS_IDLE)

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
        self._refresh_story_history()

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

    def _set_story_preview_text(self, text: str) -> None:
        self.story_preview_text.configure(state="normal")
        self.story_preview_text.delete("1.0", "end")
        self.story_preview_text.insert("1.0", text or "")
        self.story_preview_text.configure(state="disabled")

    def _open_preview_lightbox(self, _event=None):
        """Open the right-panel preview image in a larger lightbox."""
        image_path = getattr(self.current_metadata, "file_path", None)
        if not image_path:
            return

        try:
            image = Image.open(image_path)
            image.load()
        except Exception as e:
            self.logger.error(f"Error opening preview lightbox {image_path}: {e}")
            messagebox.showerror("Preview Error", f"Unable to open image preview: {e}")
            return

        if self.preview_lightbox_window and self.preview_lightbox_window.winfo_exists():
            self.preview_lightbox_window.destroy()

        self.preview_lightbox_source = image
        self.preview_lightbox_window = tk.Toplevel(self)
        self.preview_lightbox_window.title(self.current_metadata.filename)
        self.preview_lightbox_window.configure(bg="black")
        self.preview_lightbox_window.geometry("1280x860")
        self.preview_lightbox_window.minsize(640, 480)
        self.preview_lightbox_window.transient(self.winfo_toplevel())
        self.preview_lightbox_window.bind("<Escape>", lambda _e: self._close_preview_lightbox())
        self.preview_lightbox_window.bind("<Configure>", self._on_preview_lightbox_resize)

        self.preview_lightbox_label = tk.Label(self.preview_lightbox_window, bg="black")
        self.preview_lightbox_label.pack(fill="both", expand=True, padx=20, pady=(20, 8))
        self.preview_lightbox_label.bind("<Button-1>", lambda _e: self._close_preview_lightbox())

        caption = tk.Label(
            self.preview_lightbox_window,
            text=f"{self.current_metadata.filename}  |  Esc or click image to close",
            bg="black",
            fg="white",
            font=("Arial", 10),
        )
        caption.pack(fill="x", padx=20, pady=(0, 16))

        self._render_preview_lightbox()

    def _render_preview_lightbox(self):
        if not self.preview_lightbox_window or not self.preview_lightbox_source:
            return
        if not self.preview_lightbox_window.winfo_exists():
            return

        self.preview_lightbox_window.update_idletasks()
        max_w = max(200, self.preview_lightbox_window.winfo_width() - 80)
        max_h = max(200, self.preview_lightbox_window.winfo_height() - 120)

        img = self.preview_lightbox_source.copy()
        img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        self.preview_lightbox_image = ImageTk.PhotoImage(img)
        self.preview_lightbox_label.config(image=self.preview_lightbox_image)

    def _on_preview_lightbox_resize(self, event):
        if event.widget is self.preview_lightbox_window:
            self.after(10, self._render_preview_lightbox)

    def _close_preview_lightbox(self):
        if self.preview_lightbox_window and self.preview_lightbox_window.winfo_exists():
            self.preview_lightbox_window.destroy()
        self.preview_lightbox_window = None
        self.preview_lightbox_label = None
        self.preview_lightbox_source = None
        self.preview_lightbox_image = None

    def _refresh_story_history(self) -> None:
        """Reload saved stories for the selected image."""
        self.story_listbox.config(state=tk.NORMAL)
        self.story_listbox.delete(0, tk.END)
        self.story_records = []
        self._set_story_preview_text("")

        if not self.current_metadata:
            return

        try:
            self.story_records = self.db_manager.get_stories(self.current_metadata.file_path)
            if not self.story_records:
                self.story_listbox.insert(tk.END, "No saved stories yet")
                self.story_listbox.config(state=tk.DISABLED)
                return

            self.story_listbox.config(state=tk.NORMAL)
            for story in self.story_records:
                created = story.get("created_date", "")
                mode = story.get("mode", "Unknown")
                hook = (story.get("selected_hook") or "").strip().replace("\n", " ")
                hook_label = hook[:38] + "..." if len(hook) > 38 else hook
                self.story_listbox.insert(tk.END, f"{created} | {mode} | {hook_label}")

            self.story_listbox.selection_clear(0, tk.END)
            self.story_listbox.selection_set(0)
            self._show_story_record(0)
        except Exception as e:
            self.logger.error(f"Error loading story history: {e}")
            self.story_listbox.insert(tk.END, "Story history unavailable")
            self.story_listbox.config(state=tk.DISABLED)

    def _show_story_record(self, index: int) -> None:
        if index < 0 or index >= len(self.story_records):
            self._set_story_preview_text("")
            return

        record = self.story_records[index]
        preview = [
            f"Mode: {record.get('mode', 'Unknown')}",
            f"Created: {record.get('created_date', '')}",
            "",
            f"Hook: {record.get('selected_hook', '')}",
            "",
            record.get("full_story", ""),
        ]
        self._set_story_preview_text("\n".join(preview).strip())

    def _on_story_select(self, _event=None) -> None:
        selection = self.story_listbox.curselection()
        if not selection:
            return
        self._show_story_record(selection[0])

    def _copy_selected_story(self) -> None:
        selection = self.story_listbox.curselection()
        if not selection or not self.story_records:
            messagebox.showinfo("Copy Story", "No saved story is selected.")
            return

        record = self.story_records[selection[0]]
        story_text = record.get("full_story", "")
        if not story_text:
            messagebox.showinfo("Copy Story", "The selected story is empty.")
            return

        self.clipboard_clear()
        self.clipboard_append(story_text)
        messagebox.showinfo("Copy Story", "Selected story copied to clipboard.")

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
        """Update the preview image with dynamic scaling."""
        if not self.current_metadata:
            return
        
        try:
            from core.image_handler import ImageHandler
            handler = ImageHandler()
            
            # Calculate dynamic size based on container
            self.update_idletasks()
            container_width = self.preview_container.winfo_width() - 24
            container_height = self.preview_container.winfo_height() - 24
            
            # Target size: max-height 40% of panel or use container's current size
            # The panel's total height isn't easily known here, so we'll use the container's 
            # height which is constrained.
            
            max_w = max(100, container_width)
            max_h = max(100, container_height)

            # Create thumbnail with dynamic scaling
            thumbnail = handler.create_thumbnail(self.current_metadata.file_path, max(max_w, max_h))
            if thumbnail:
                # Further resize to fit exactly while maintaining aspect ratio
                thumbnail.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
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
    
    def _launch_sidecar(self):
        """Launch the persistent Electron sidecar window."""
        if not self.current_metadata:
            messagebox.showwarning("No Image", "Please select an image first.")
            return
        
        description = self.description_text.get(1.0, tk.END).strip()
        tags = self.tags_var.get()
        is_chaos = bool(self.story_chaos_var.get())
        complexity = self.story_complexity_var.get().strip() or "Simple"

        try:
            from core.sidecar_manager import SidecarManager
            if not hasattr(self, 'sidecar_manager') or not self.sidecar_manager.is_alive():
                self.sidecar_manager = SidecarManager(
                    self.db_manager,
                    self.classifier.config,
                    event_callback=self._handle_sidecar_event,
                )
            
            self._append_realtime_log("bridge: sending description and tags to Electron")
            self.sidecar_manager.launch(self.current_metadata, description, tags, complexity, is_chaos)
        except Exception as e:
            self.logger.error(f"Failed to launch sidecar: {e}")
            messagebox.showerror("Sidecar Error", f"Failed to launch sidecar: {e}")

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

        # Immediate feedback
        self._set_classification_status(
            self.STATUS_RECEIVED,
            "Command received. Queuing this image for classification.",
        )
        self.update_idletasks() # Force UI update before threading

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
                self.classifier.process_image(
                    image_path,
                    force_refresh=True,
                    status_callback=self._handle_classifier_status,
                )
            )

            self.after(0, lambda: self._on_classify_complete(image_path, metadata))
        except Exception as e:
            self.after(
                0,
                lambda: self._set_classification_status(
                    self.STATUS_FAILED,
                    f"Classification failed: {e}",
                ),
            )
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
            self._set_classification_status(
                self.STATUS_COMPLETED,
                "Classification complete. Metadata fields have been updated.",
            )
        else:
            self._set_classification_status(
                self.STATUS_FAILED,
                "Classification failed before metadata could be updated.",
            )
            messagebox.showerror("Classification Error", "Classification failed.")
    
    def _clear_classification(self):
        """Clear the classification data."""
        if self.current_metadata and self.on_metadata_change:
            self.on_metadata_change(self.current_metadata.file_path, 'classification', '')
            self.on_metadata_change(self.current_metadata.file_path, 'api_cached', False)
            self._update_classification_display()
            self._set_classification_status(self.STATUS_IDLE)
    
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

    def _rename_current_image(self):
        """Rename the currently selected image."""
        if not self.current_metadata:
            messagebox.showwarning("Rename Image", "No image is selected.")
            return

        new_name = simpledialog.askstring(
            "Rename Image",
            "Enter the new filename:",
            initialvalue=self.current_metadata.filename,
            parent=self,
        )
        if new_name is None:
            return

        self._run_file_request("rename", self.current_metadata.file_path, new_name=new_name)

    def _move_current_image(self):
        """Move the currently selected image to another folder."""
        if not self.current_metadata:
            messagebox.showwarning("Move Image", "No image is selected.")
            return

        destination = filedialog.askdirectory(title="Move Image To Folder")
        if not destination:
            return

        self._run_file_request("move", self.current_metadata.file_path, destination_folder=destination)

    def _confirm_delete_current_image(self):
        """Show a non-blocking delete confirmation dialog."""
        if not self.current_metadata:
            messagebox.showwarning("Delete Image", "No image is selected.")
            return

        if self._delete_dialog and self._delete_dialog.winfo_exists():
            self._delete_dialog.destroy()

        dialog = tk.Toplevel(self)
        dialog.title("Delete Image")
        dialog.transient(self.winfo_toplevel())
        dialog.resizable(False, False)
        dialog.geometry("+%d+%d" % (self.winfo_rootx() + 140, self.winfo_rooty() + 180))

        tk.Label(
            dialog,
            text=f"Delete {self.current_metadata.filename}?\nThis removes the file and its database entry.",
            justify=tk.LEFT,
            padx=18,
            pady=16,
        ).pack(fill="both", expand=True)

        button_row = tk.Frame(dialog)
        button_row.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(button_row, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        tk.Button(
            button_row,
            text="Delete",
            bg="#c0392b",
            fg="white",
            command=lambda: self._execute_delete_current_image(dialog),
        ).pack(side=tk.RIGHT)

        self._delete_dialog = dialog

    def _execute_delete_current_image(self, dialog):
        dialog.destroy()
        if self.current_metadata:
            self._run_file_request("delete", self.current_metadata.file_path)

    def _run_file_request(self, action: str, image_path: str, **kwargs):
        """Dispatch a file operation request through the application controller."""
        if not self.on_file_request:
            messagebox.showerror("File Operation Error", "File management is not configured.")
            return

        result = self.on_file_request(action, image_path, **kwargs)
        if not result.get("success"):
            messagebox.showerror("File Operation Error", result.get("error", "File operation failed."))
    
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
