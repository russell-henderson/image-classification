"""
Image browser component for displaying and navigating image collections.
"""

import asyncio
import logging
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from typing import List, Optional, Callable

try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    CTK_AVAILABLE = False
    ctk = tk

from PIL import Image, ImageTk

from core.database import DatabaseManager, ImageMetadata
from core.image_handler import ImageHandler
from core.classifier import ClassificationEngine


class ImageThumbnail:
    """Represents a single image thumbnail in the browser."""

    def __init__(self, metadata: ImageMetadata,
                 thumbnail_image: Optional[Image.Image] = None):
        self.metadata = metadata
        self.thumbnail_image = thumbnail_image
        self.tk_image = None
        self.widget = None
        self.selected = False

    def create_tk_image(self, size: int = 150):
        """Create Tkinter-compatible image."""
        if self.thumbnail_image and not self.tk_image:
            # Resize to fit in the thumbnail frame without mutating source
            thumb_copy = self.thumbnail_image.copy()
            thumb_copy.thumbnail((size, size), Image.Resampling.LANCZOS)
            self.tk_image = ImageTk.PhotoImage(thumb_copy)
        return self.tk_image


class ImageBrowser(tk.Frame):
    """Main image browser widget with grid/list view and navigation."""

    def __init__(self, parent, db_manager: DatabaseManager,
                 image_handler: ImageHandler,
                 classifier: ClassificationEngine, grid_columns: int = 4,
                 on_selection_change: Optional[Callable[[str], None]] = None):
        super().__init__(parent)

        self.db_manager = db_manager
        self.image_handler = image_handler
        self.classifier = classifier
        self.grid_columns = grid_columns
        self.on_selection_change = on_selection_change
        self.logger = logging.getLogger(__name__)

        # State
        self.current_images: List[ImageThumbnail] = []
        self.selected_image: Optional[str] = None
        self.current_folder: Optional[str] = None
        self.view_mode = "grid"  # "grid" or "list"
        self.thumbnail_size = 150
        self._size_change_after_id = None
        self._last_thumb_size = self.thumbnail_size
        self._resize_after_id = None

        # Threading for async operations
        self.executor = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup the user interface."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar
        self._create_toolbar()

        # Main content area with scrolling
        self._create_content_area()

        # Status bar
        self._create_status_bar()

    def _create_toolbar(self):
        """Create the toolbar with controls."""
        toolbar = tk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        toolbar.grid_columnconfigure(2, weight=1)

        # View mode buttons
        view_frame = tk.Frame(toolbar)
        view_frame.grid(row=0, column=0, sticky="w")

        grid_btn = tk.Button(view_frame, text="Grid",
                             command=lambda: self._set_view_mode("grid"))
        grid_btn.pack(side=tk.LEFT, padx=2)

        list_btn = tk.Button(view_frame, text="List",
                             command=lambda: self._set_view_mode("list"))
        list_btn.pack(side=tk.LEFT, padx=2)

        # Thumbnail size slider
        size_frame = tk.Frame(toolbar)
        size_frame.grid(row=0, column=1, sticky="w", padx=20)

        tk.Label(size_frame, text="Size:").pack(side=tk.LEFT)
        self.size_var = tk.IntVar(value=self.thumbnail_size)
        size_scale = tk.Scale(
            size_frame, from_=100, to=500, orient=tk.HORIZONTAL,
            variable=self.size_var, command=self._on_size_change
        )
        size_scale.pack(side=tk.LEFT, padx=5)

        # Search box
        search_frame = tk.Frame(toolbar)
        search_frame.grid(row=0, column=2, sticky="e")

        tk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._on_search_change)
        search_entry = tk.Entry(
            search_frame, textvariable=self.search_var, width=20
        )
        search_entry.pack(side=tk.LEFT, padx=5)

        # Folder button
        folder_btn = tk.Button(toolbar, text="Open Folder",
                               command=self._open_folder_dialog)
        folder_btn.grid(row=0, column=3, sticky="e", padx=5)

    def _create_content_area(self):
        """Create the scrollable content area."""
        # Create frame with scrollbars
        canvas_frame = tk.Frame(self)
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(0, weight=1)

        # Canvas and scrollbars
        self.canvas = tk.Canvas(canvas_frame, bg="white")
        v_scrollbar = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(
            canvas_frame, orient="horizontal", command=self.canvas.xview)

        self.canvas.configure(yscrollcommand=v_scrollbar.set,
                              xscrollcommand=h_scrollbar.set)

        # Grid layout
        self.canvas.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        # Content frame inside canvas
        self.content_frame = tk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.content_frame, anchor="nw")

        # Bind events
        self.content_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

    def _create_status_bar(self):
        """Create the status bar."""
        self.status_bar = tk.Frame(self)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=5, pady=2)

        self.status_label = tk.Label(self.status_bar, text="Ready", anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress = ttk.Progressbar(self.status_bar, length=200)
        self.progress.pack(side=tk.RIGHT, padx=5)

    def _set_view_mode(self, mode: str):
        """Set the view mode (grid or list)."""
        self.view_mode = mode
        self._refresh_display()

    def _on_size_change(self, value):
        """Handle thumbnail size change."""
        new_size = int(float(value))
        if new_size == self.thumbnail_size:
            return

        self.thumbnail_size = new_size

        if self._size_change_after_id is not None:
            try:
                self.after_cancel(self._size_change_after_id)
            except Exception:
                pass
            self._size_change_after_id = None

        self._size_change_after_id = self.after(
            150, self._apply_thumbnail_size_change
        )

    def _apply_thumbnail_size_change(self):
        """Apply thumbnail size change and force grid refresh."""
        self._size_change_after_id = None

        if self._last_thumb_size != self.thumbnail_size:
            for method_name in ("clear_thumbnail_cache", "clear_cache", "reset_cache"):
                if hasattr(self.image_handler, method_name):
                    try:
                        getattr(self.image_handler, method_name)()
                    except Exception:
                        pass
                    break

        self._last_thumb_size = self.thumbnail_size
        if not self.current_images:
            self._refresh_display()
            return

        self.status_label.config(text="Resizing thumbnails...")
        threading.Thread(target=self._reload_thumbnails_async,
                         daemon=True).start()

    def _reload_thumbnails_async(self):
        """Reload thumbnails for the current images at the new size."""
        total = len(self.current_images)
        for i, thumbnail in enumerate(list(self.current_images)):
            try:
                image_path = thumbnail.metadata.file_path
                thumbnail_image = self.image_handler.create_thumbnail(
                    image_path, self.thumbnail_size
                )
                if thumbnail_image:
                    thumbnail.thumbnail_image = thumbnail_image
                    thumbnail.tk_image = None

                progress = int((i + 1) / total * 100)
                self.after(0, lambda p=progress: self.progress.config(value=p))
            except Exception as e:
                self.logger.error(
                    f"Error resizing thumbnail for {image_path}: {e}")
                continue

        self.after(0, self._on_thumbnail_resize_complete)

    def _on_thumbnail_resize_complete(self):
        """Finalize thumbnail resize updates."""
        self.progress.config(value=0)
        if self.current_folder:
            self.status_label.config(
                text=f"Loaded {len(self.current_images)} images"
            )
        else:
            self.status_label.config(text="Ready")
        self._refresh_display()

    def _on_search_change(self, *args):
        """Handle search text change."""
        search_text = self.search_var.get().lower()
        if search_text:
            self._filter_images(search_text)
        else:
            self._refresh_display()

    def _filter_images(self, search_text: str):
        """Filter images based on search text."""
        filtered_images = []
        for thumbnail in self.current_images:
            metadata = thumbnail.metadata
            if (search_text in metadata.filename.lower() or
                search_text in metadata.description.lower() or
                any(search_text in tag.lower() for tag in metadata.tags) or
                    any(search_text in keyword.lower() for keyword in metadata.keywords)):
                filtered_images.append(thumbnail)

        self._display_images(filtered_images)

    def _on_frame_configure(self, event):
        """Handle content frame size change."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Handle canvas size change."""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    def _on_canvas_resize(self, event):
        """Handle canvas resize for grid reflow."""
        self.canvas.itemconfigure(self.canvas_window, width=event.width)
        if getattr(self, "view_mode", "grid") != "grid":
            return

        if self._resize_after_id is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except Exception:
                pass

        self._resize_after_id = self.after(100, self._refresh_display)

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _open_folder_dialog(self):
        """Open folder selection dialog."""
        folder = filedialog.askdirectory(title="Select Image Folder")
        if folder:
            self.load_folder(folder)

    def load_folder(self, folder_path: str):
        """Load images from a folder."""
        self.current_folder = folder_path
        self.status_label.config(text=f"Scanning folder: {folder_path}")

        # Scan folder in background thread
        threading.Thread(target=self._scan_folder_async,
                         args=(folder_path,), daemon=True).start()

    def _scan_folder_async(self, folder_path: str):
        """Scan folder for images asynchronously."""
        try:
            # Get image files
            image_files = self.image_handler.scan_directory(
                folder_path, recursive=True)

            # Update UI in main thread
            self.after(0, lambda: self._on_folder_scanned(image_files))

        except Exception as e:
            self.logger.error(f"Error scanning folder {folder_path}: {e}")
            self.after(0, lambda: self.status_label.config(
                text=f"Error scanning folder: {e}"))

    def _on_folder_scanned(self, image_files: List[str]):
        """Handle completion of folder scanning."""
        self.status_label.config(
            text=f"Found {len(image_files)} images. Loading...")

        # Load thumbnails in background
        threading.Thread(target=self._load_thumbnails_async,
                         args=(image_files,), daemon=True).start()

    def _load_thumbnails_async(self, image_files: List[str]):
        """Load thumbnails asynchronously."""
        thumbnails = []
        total = len(image_files)

        for i, image_path in enumerate(image_files):
            try:
                # Get or create metadata
                metadata = self.db_manager.get_image(image_path)
                if not metadata:
                    metadata = self.image_handler.create_metadata(image_path)
                    if metadata:
                        self.db_manager.add_image(metadata)

                if metadata:
                    # Create thumbnail
                    thumbnail_image = self.image_handler.create_thumbnail(
                        image_path, self.thumbnail_size)
                    thumbnail = ImageThumbnail(metadata, thumbnail_image)
                    thumbnails.append(thumbnail)

                # Update progress
                progress = int((i + 1) / total * 100)
                self.after(0, lambda p=progress: self.progress.config(value=p))

            except Exception as e:
                self.logger.error(
                    f"Error loading thumbnail for {image_path}: {e}")
                continue

        # Update UI in main thread
        self.after(0, lambda: self._on_thumbnails_loaded(thumbnails))

    def _on_thumbnails_loaded(self, thumbnails: List[ImageThumbnail]):
        """Handle completion of thumbnail loading."""
        self.current_images = thumbnails
        self.progress.config(value=0)
        self.status_label.config(text=f"Loaded {len(thumbnails)} images")
        self._refresh_display()

    def load_images(self, image_paths: List[str]):
        """Load specific images."""
        self.status_label.config(text=f"Loading {len(image_paths)} images...")
        threading.Thread(target=self._load_thumbnails_async,
                         args=(image_paths,), daemon=True).start()

    def _refresh_display(self):
        """Refresh the image display."""
        self._display_images(self.current_images)

    def _display_images(self, thumbnails: List[ImageThumbnail]):
        """Display images in the current view mode."""
        # Clear existing widgets
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        if not thumbnails:
            tk.Label(self.content_frame, text="No images to display",
                     font=("Arial", 12), fg="gray").pack(expand=True)
            return

        if self.view_mode == "grid":
            self._display_grid(thumbnails)
        else:
            self._display_list(thumbnails)

    def _display_grid(self, thumbnails: List[ImageThumbnail]):
        """Display images in grid layout."""
        # Force geometry/layout to settle so width readings are accurate
        try:
            self.update_idletasks()
        except Exception:
            pass

        # Always use the current canvas width (post-layout)
        canvas_width = self.canvas.winfo_width()

        # If we're in a "canvas with embedded frame" pattern, force the embedded frame
        # to match the canvas width so we don't get phantom unused space.
        if hasattr(self, "canvas_window"):
            try:
                self.canvas.itemconfigure(self.canvas_window, width=canvas_width)
                self.update_idletasks()
                canvas_width = self.canvas.winfo_width()
            except Exception:
                pass

        # Guard
        if canvas_width <= 1:
            canvas_width = 800

        tile_pad_x = 12  # keep current assumption for now
        desired_columns = 3
        max_thumb_size = (canvas_width - (tile_pad_x * desired_columns)) // desired_columns
        effective_thumb_size = self.thumbnail_size
        if max_thumb_size > 0 and effective_thumb_size > max_thumb_size:
            effective_thumb_size = max_thumb_size

        tile_width = effective_thumb_size + tile_pad_x
        actual_columns = max(1, min(desired_columns, canvas_width // tile_width))

        used_width = actual_columns * tile_width
        left_margin = max(0, (canvas_width - used_width) // 2)

        for i, thumbnail in enumerate(thumbnails):
            row = i // actual_columns
            col = i % actual_columns

            # Create thumbnail widget
            self._create_thumbnail_widget(
                thumbnail,
                row,
                col,
                left_margin=left_margin if col == 0 else 0,
                thumb_size=effective_thumb_size
            )

    def _display_list(self, thumbnails: List[ImageThumbnail]):
        """Display images in list layout."""
        for i, thumbnail in enumerate(thumbnails):
            self._create_list_widget(thumbnail, i)

    def _create_thumbnail_widget(
        self,
        thumbnail: ImageThumbnail,
        row: int,
        col: int,
        left_margin: int = 0,
        thumb_size: Optional[int] = None
    ):
        """Create a thumbnail widget for grid view."""
        frame = tk.Frame(self.content_frame, relief=tk.RAISED, borderwidth=1)
        padx = (left_margin, 5) if left_margin else 5
        frame.grid(row=row, column=col, padx=padx, pady=5, sticky="nsew")

        # Create Tkinter image
        tk_image = thumbnail.create_tk_image(thumb_size or self.thumbnail_size)

        # Image label
        if tk_image:
            img_label = tk.Label(frame, image=tk_image, cursor="hand2")
            img_label.pack(pady=2)
            img_label.bind("<Button-1>", lambda e,
                           path=thumbnail.metadata.file_path: self._on_image_click(path))

        # Filename label
        filename = Path(thumbnail.metadata.filename).stem
        if len(filename) > 20:
            filename = filename[:17] + "..."

        name_label = tk.Label(
            frame,
            text=filename,
            font=("Arial", 8),
            wraplength=thumb_size or self.thumbnail_size
        )
        name_label.pack()

        # Rating and info
        info_text = f"★{thumbnail.metadata.rating}" if thumbnail.metadata.rating > 0 else ""
        if thumbnail.metadata.classification:
            info_text += " 🤖"

        if info_text:
            info_label = tk.Label(frame, text=info_text,
                                  font=("Arial", 7), fg="blue")
            info_label.pack()

        thumbnail.widget = frame

        # Double-click to classify
        frame.bind("<Double-Button-1>", lambda e,
                   path=thumbnail.metadata.file_path: self._classify_image(path))

    def _create_list_widget(self, thumbnail: ImageThumbnail, row: int):
        """Create a list widget for list view."""
        frame = tk.Frame(self.content_frame, relief=tk.RAISED, borderwidth=1)
        frame.grid(row=row, column=0, sticky="ew", padx=5, pady=2)
        frame.grid_columnconfigure(1, weight=1)

        # Small thumbnail
        tk_image = thumbnail.create_tk_image(64)
        if tk_image:
            img_label = tk.Label(frame, image=tk_image, cursor="hand2")
            img_label.grid(row=0, column=0, rowspan=2, padx=5, pady=5)
            img_label.bind("<Button-1>", lambda e,
                           path=thumbnail.metadata.file_path: self._on_image_click(path))

        # File info
        info_frame = tk.Frame(frame)
        info_frame.grid(row=0, column=1, sticky="ew", padx=5)
        info_frame.grid_columnconfigure(0, weight=1)

        # Filename and size
        name_text = f"{thumbnail.metadata.filename} ({thumbnail.metadata.width}x{thumbnail.metadata.height})"
        name_label = tk.Label(info_frame, text=name_text,
                              font=("Arial", 10, "bold"), anchor="w")
        name_label.grid(row=0, column=0, sticky="ew")

        # Description
        desc_text = thumbnail.metadata.description or "No description"
        if len(desc_text) > 100:
            desc_text = desc_text[:97] + "..."

        desc_label = tk.Label(info_frame, text=desc_text,
                              font=("Arial", 9), anchor="w", fg="gray")
        desc_label.grid(row=1, column=0, sticky="ew")

        # Tags and rating
        tags_text = ", ".join(
            thumbnail.metadata.tags[:3]) if thumbnail.metadata.tags else "No tags"
        rating_text = f"Rating: {thumbnail.metadata.rating}/5" if thumbnail.metadata.rating > 0 else "Not rated"

        meta_label = tk.Label(info_frame, text=f"{tags_text} | {rating_text}",
                              font=("Arial", 8), anchor="w", fg="blue")
        meta_label.grid(row=2, column=0, sticky="ew")

        thumbnail.widget = frame

        # Double-click to classify
        frame.bind("<Double-Button-1>", lambda e,
                   path=thumbnail.metadata.file_path: self._classify_image(path))

    def _on_image_click(self, image_path: str):
        """Handle image selection."""
        # Update selection
        self._clear_selection()
        self.selected_image = image_path

        # Highlight selected image
        for thumbnail in self.current_images:
            if thumbnail.metadata.file_path == image_path and thumbnail.widget:
                thumbnail.widget.config(bg="lightblue", relief=tk.SUNKEN)
                thumbnail.selected = True
                break

        # Notify callback
        if self.on_selection_change:
            self.on_selection_change(image_path)

    def _clear_selection(self):
        """Clear current selection."""
        for thumbnail in self.current_images:
            if thumbnail.widget and thumbnail.selected:
                thumbnail.widget.config(
                    bg="SystemButtonFace", relief=tk.RAISED)
                thumbnail.selected = False

    def _classify_image(self, image_path: str):
        """Classify a single image."""
        self.status_label.config(text=f"Classifying image...")

        # Run classification in background
        threading.Thread(target=self._classify_image_async,
                         args=(image_path,), daemon=True).start()

    def _classify_image_async(self, image_path: str):
        """Classify image asynchronously."""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Process the image
            metadata = loop.run_until_complete(
                self.classifier.process_image(image_path, force_refresh=True))

            # Update UI in main thread
            self.after(0, lambda: self._on_classification_complete(
                image_path, metadata))

        except Exception as e:
            self.logger.error(f"Error classifying image {image_path}: {e}")
            self.after(0, lambda: self.status_label.config(
                text=f"Classification error: {e}"))
        finally:
            loop.close()

    def _on_classification_complete(self, image_path: str, metadata: Optional[ImageMetadata]):
        """Handle completion of image classification."""
        if metadata:
            # Update the thumbnail in current view
            for thumbnail in self.current_images:
                if thumbnail.metadata.file_path == image_path:
                    thumbnail.metadata = metadata
                    break

            self.status_label.config(text="Classification complete")

            # Refresh the current selection if it's the classified image
            if self.selected_image == image_path and self.on_selection_change:
                self.on_selection_change(image_path)
        else:
            self.status_label.config(text="Classification failed")

    def get_selected_image(self) -> Optional[str]:
        """Get the currently selected image path."""
        return self.selected_image

    def refresh_current_view(self):
        """Refresh the current view (used after metadata changes)."""
        self._refresh_display()

    def show_search_results(self, search_results: List[ImageMetadata]):
        """Show search results."""
        # Convert metadata to thumbnails
        result_thumbnails = []
        for metadata in search_results:
            thumbnail_image = self.image_handler.create_thumbnail(
                metadata.file_path, self.thumbnail_size)
            thumbnail = ImageThumbnail(metadata, thumbnail_image)
            result_thumbnails.append(thumbnail)

        self._display_images(result_thumbnails)
        self.status_label.config(
            text=f"Search results: {len(result_thumbnails)} images")
