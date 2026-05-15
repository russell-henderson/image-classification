"""
Image browser component for displaying and navigating image collections.
"""

import asyncio
import logging
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any

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
                 on_selection_change: Optional[Callable[[str], None]] = None,
                 on_file_request: Optional[Callable[..., Dict[str, Any]]] = None):
        super().__init__(parent)

        self.db_manager = db_manager
        self.image_handler = image_handler
        self.classifier = classifier
        self.grid_columns = grid_columns
        self.on_selection_change = on_selection_change
        self.on_file_request = on_file_request
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
        self.lightbox_window = None
        self.lightbox_label = None
        self.lightbox_caption = None
        self.lightbox_source_image = None
        self.lightbox_tk_image = None
        self.lightbox_index: Optional[int] = None
        self._grid_column_count = 0
        self._delete_dialog = None

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

    def _bind_file_menu(self, widget, image_path: str):
        """Bind right-click context actions to a widget."""
        widget.bind("<Button-3>", lambda e, path=image_path: self._show_context_menu(e, path))
        widget.bind("<Button-2>", lambda e, path=image_path: self._show_context_menu(e, path))

    def _show_context_menu(self, event, image_path: str):
        """Show the file action context menu for a thumbnail."""
        self._on_image_click(image_path)

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Rename", command=lambda: self._rename_image(image_path))
        menu.add_command(label="Move to Folder", command=lambda: self._move_image(image_path))
        menu.add_separator()
        menu.add_command(label="Delete", command=lambda: self._confirm_delete_image(image_path))

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

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

        tile_pad_x = 12
        max_thumb_size = canvas_width - (tile_pad_x * 2)
        effective_thumb_size = self.thumbnail_size
        if max_thumb_size > 0 and effective_thumb_size > max_thumb_size:
            effective_thumb_size = max_thumb_size

        tile_width = effective_thumb_size + (tile_pad_x * 2)
        actual_columns = max(1, canvas_width // max(tile_width, 1))
        for col in range(max(self._grid_column_count, actual_columns)):
            self.content_frame.grid_columnconfigure(col, weight=0, uniform="")
        for col in range(actual_columns):
            self.content_frame.grid_columnconfigure(col, weight=1, uniform="thumb")
        self._grid_column_count = actual_columns

        for i, thumbnail in enumerate(thumbnails):
            row = i // actual_columns
            col = i % actual_columns

            # Create thumbnail widget
            self._create_thumbnail_widget(
                thumbnail,
                row,
                col,
                left_margin=0,
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
            img_label.bind("<Double-Button-1>", lambda e,
                           path=thumbnail.metadata.file_path: self._open_lightbox(path))

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
        name_label.bind("<Button-1>", lambda e,
                        path=thumbnail.metadata.file_path: self._on_image_click(path))

        # Rating and info
        info_text = f"★{thumbnail.metadata.rating}" if thumbnail.metadata.rating > 0 else ""
        if thumbnail.metadata.classification:
            info_text += " 🤖"

        if info_text:
            info_label = tk.Label(frame, text=info_text,
                                  font=("Arial", 7), fg="blue")
            info_label.pack()
            info_label.bind("<Button-1>", lambda e,
                            path=thumbnail.metadata.file_path: self._on_image_click(path))

        thumbnail.widget = frame

        frame.bind("<Button-1>", lambda e,
                   path=thumbnail.metadata.file_path: self._on_image_click(path))
        frame.bind("<Double-Button-1>", lambda e,
                   path=thumbnail.metadata.file_path: self._open_lightbox(path))
        self._bind_file_menu(frame, thumbnail.metadata.file_path)
        if tk_image:
            self._bind_file_menu(img_label, thumbnail.metadata.file_path)
        self._bind_file_menu(name_label, thumbnail.metadata.file_path)
        if info_text:
            self._bind_file_menu(info_label, thumbnail.metadata.file_path)

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
            img_label.bind("<Double-Button-1>", lambda e,
                           path=thumbnail.metadata.file_path: self._open_lightbox(path))

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

        frame.bind("<Button-1>", lambda e,
                   path=thumbnail.metadata.file_path: self._on_image_click(path))
        frame.bind("<Double-Button-1>", lambda e,
                   path=thumbnail.metadata.file_path: self._open_lightbox(path))
        self._bind_file_menu(frame, thumbnail.metadata.file_path)
        if tk_image:
            self._bind_file_menu(img_label, thumbnail.metadata.file_path)
        self._bind_file_menu(name_label, thumbnail.metadata.file_path)
        self._bind_file_menu(desc_label, thumbnail.metadata.file_path)
        self._bind_file_menu(meta_label, thumbnail.metadata.file_path)

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

    def _open_lightbox(self, image_path: str):
        """Open a large lightbox view for the clicked image."""
        try:
            image = Image.open(image_path)
            image.load()
        except Exception as e:
            self.logger.error(f"Error opening lightbox image {image_path}: {e}")
            self.status_label.config(text=f"Lightbox error: {e}")
            return

        if self.lightbox_window and self.lightbox_window.winfo_exists():
            self.lightbox_window.destroy()

        self.lightbox_source_image = image
        self.lightbox_index = self._get_image_index(image_path)
        self.lightbox_window = tk.Toplevel(self)
        self.lightbox_window.title(Path(image_path).name)
        self.lightbox_window.configure(bg="black")
        self.lightbox_window.geometry("1280x860")
        self.lightbox_window.minsize(640, 480)
        self.lightbox_window.transient(self.winfo_toplevel())
        self.lightbox_window.bind("<Escape>", lambda _e: self._close_lightbox())
        self.lightbox_window.bind("<Left>", lambda _e: self._show_adjacent_lightbox(-1))
        self.lightbox_window.bind("<Right>", lambda _e: self._show_adjacent_lightbox(1))
        self.lightbox_window.bind("<Configure>", self._on_lightbox_resize)
        self.lightbox_window.focus_set()

        self.lightbox_label = tk.Label(self.lightbox_window, bg="black")
        self.lightbox_label.pack(fill="both", expand=True, padx=20, pady=(20, 8))
        self.lightbox_label.bind("<Button-1>", lambda _e: self._close_lightbox())

        self.lightbox_caption = tk.Label(
            self.lightbox_window,
            text=f"{Path(image_path).name}  |  Left/Right to browse, Esc or click image to close",
            bg="black",
            fg="white",
            font=("Arial", 10),
        )
        self.lightbox_caption.pack(fill="x", padx=20, pady=(0, 16))

        self._render_lightbox_image()

    def _render_lightbox_image(self):
        if not self.lightbox_window or not self.lightbox_source_image or not self.lightbox_label:
            return
        if not self.lightbox_window.winfo_exists():
            return

        self.lightbox_window.update_idletasks()
        max_w = max(200, self.lightbox_window.winfo_width() - 80)
        max_h = max(200, self.lightbox_window.winfo_height() - 120)

        img = self.lightbox_source_image.copy()
        img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        self.lightbox_tk_image = ImageTk.PhotoImage(img)
        self.lightbox_label.config(image=self.lightbox_tk_image)

    def _get_image_index(self, image_path: str) -> Optional[int]:
        """Return the index of an image in the current gallery ordering."""
        for index, thumbnail in enumerate(self.current_images):
            if thumbnail.metadata.file_path == image_path:
                return index
        return None

    def _show_adjacent_lightbox(self, delta: int):
        """Move to the previous or next image in the lightbox."""
        if self.lightbox_index is None or not self.current_images:
            return
        self.lightbox_index = (self.lightbox_index + delta) % len(self.current_images)
        next_path = self.current_images[self.lightbox_index].metadata.file_path
        try:
            image = Image.open(next_path)
            image.load()
        except Exception as e:
            self.logger.error(f"Error opening lightbox image {next_path}: {e}")
            self.status_label.config(text=f"Lightbox error: {e}")
            return

        self.lightbox_source_image = image
        if self.lightbox_window and self.lightbox_window.winfo_exists():
            self.lightbox_window.title(Path(next_path).name)
        if self.lightbox_caption:
            self.lightbox_caption.config(
                text=f"{Path(next_path).name}  |  Left/Right to browse, Esc or click image to close"
            )
        self._render_lightbox_image()

    def _on_lightbox_resize(self, event):
        if event.widget is self.lightbox_window:
            self.after(10, self._render_lightbox_image)

    def _close_lightbox(self):
        if self.lightbox_window and self.lightbox_window.winfo_exists():
            self.lightbox_window.destroy()
        self.lightbox_window = None
        self.lightbox_label = None
        self.lightbox_caption = None
        self.lightbox_source_image = None
        self.lightbox_tk_image = None
        self.lightbox_index = None

    def _rename_image(self, image_path: str):
        """Prompt for a new filename and request a rename."""
        current_name = Path(image_path).name
        new_name = simpledialog.askstring(
            "Rename Image",
            "Enter the new filename:",
            initialvalue=current_name,
            parent=self,
        )
        if new_name is None:
            return

        result = self._dispatch_file_request("rename", image_path, new_name=new_name)
        self._handle_file_result(result)

    def _move_image(self, image_path: str):
        """Prompt for a destination folder and request a move."""
        destination = filedialog.askdirectory(title="Move Image To Folder")
        if not destination:
            return

        result = self._dispatch_file_request("move", image_path, destination_folder=destination)
        self._handle_file_result(result)

    def _confirm_delete_image(self, image_path: str):
        """Show a non-blocking delete confirmation dialog."""
        if self._delete_dialog and self._delete_dialog.winfo_exists():
            self._delete_dialog.destroy()

        dialog = tk.Toplevel(self)
        dialog.title("Delete Image")
        dialog.transient(self.winfo_toplevel())
        dialog.resizable(False, False)
        dialog.geometry("+%d+%d" % (self.winfo_rootx() + 140, self.winfo_rooty() + 140))

        tk.Label(
            dialog,
            text=f"Delete {Path(image_path).name}?\nThis removes the file and its database entry.",
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
            command=lambda: self._execute_delete_image(dialog, image_path),
        ).pack(side=tk.RIGHT)

        self._delete_dialog = dialog

    def _execute_delete_image(self, dialog, image_path: str):
        dialog.destroy()
        result = self._dispatch_file_request("delete", image_path)
        self._handle_file_result(result)

    def _dispatch_file_request(self, action: str, image_path: str, **kwargs) -> Dict[str, Any]:
        """Send a file action request to the application controller."""
        if not self.on_file_request:
            return {"success": False, "action": action, "error": "File management is not configured."}
        return self.on_file_request(action, image_path, **kwargs)

    def _handle_file_result(self, result: Dict[str, Any]):
        """Surface the outcome of a file request in the browser UI."""
        if not result.get("success"):
            error = result.get("error", "File operation failed.")
            self.status_label.config(text=error)
            messagebox.showerror("File Operation Error", error)
            return

    def apply_file_action_result(self, result: Dict[str, Any]):
        """Apply a successful file action result to the gallery state."""
        action = result.get("action")
        old_path = result.get("old_path")
        new_path = result.get("new_path")

        if action == "rename" and old_path and new_path:
            self._replace_thumbnail_path(old_path, new_path)
            self.status_label.config(text=f"Renamed to {Path(new_path).name}")
            self._on_image_click(new_path)
            return

        if action == "move" and old_path:
            self._remove_thumbnail_and_select_next(old_path)
            self.status_label.config(text=f"Moved {Path(old_path).name}")
            return

        if action == "delete" and old_path:
            self._remove_thumbnail_and_select_next(old_path)
            self.status_label.config(text=f"Deleted {Path(old_path).name}")
            return

        if action == "scan_missing":
            removed_paths = result.get("removed_paths", [])
            if removed_paths:
                self.remove_images(removed_paths)
                self.status_label.config(text=f"Removed {len(removed_paths)} missing file entries")
            else:
                self.status_label.config(text="No missing file entries found")

    def _replace_thumbnail_path(self, old_path: str, new_path: str):
        """Update a thumbnail's metadata after a rename."""
        fresh_metadata = self.db_manager.get_image(new_path)
        for thumbnail in self.current_images:
            if thumbnail.metadata.file_path == old_path:
                if fresh_metadata:
                    thumbnail.metadata = fresh_metadata
                else:
                    thumbnail.metadata.file_path = new_path
                    thumbnail.metadata.filename = Path(new_path).name
                thumbnail.thumbnail_image = self.image_handler.create_thumbnail(new_path, self.thumbnail_size)
                thumbnail.tk_image = None
                break
        if self.selected_image == old_path:
            self.selected_image = new_path
        self._refresh_display()

    def _remove_thumbnail_and_select_next(self, image_path: str):
        """Remove an image from the gallery and select the next available item."""
        removed_index = None
        for index, thumbnail in enumerate(self.current_images):
            if thumbnail.metadata.file_path == image_path:
                removed_index = index
                break

        if removed_index is None:
            return

        del self.current_images[removed_index]
        if self.selected_image == image_path:
            self.selected_image = None

        self._refresh_display()

        if not self.current_images:
            return

        next_index = min(removed_index, len(self.current_images) - 1)
        self._on_image_click(self.current_images[next_index].metadata.file_path)

    def remove_images(self, image_paths: List[str]):
        """Remove multiple images from the current gallery and preserve selection when possible."""
        if not image_paths:
            return

        removal_set = set(image_paths)
        current_selected = self.selected_image
        self.current_images = [
            thumbnail for thumbnail in self.current_images
            if thumbnail.metadata.file_path not in removal_set
        ]

        self._refresh_display()

        if current_selected and current_selected not in removal_set:
            self._on_image_click(current_selected)
        elif self.current_images:
            self._on_image_click(self.current_images[0].metadata.file_path)
        else:
            self.selected_image = None

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
