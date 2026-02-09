"""
Main application entry point for the Image Classification Desktop App.
"""

import json
import logging
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Dict, Any

try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    CTK_AVAILABLE = False
    import tkinter as ctk

from core.database import DatabaseManager
from core.image_handler import ImageHandler
from core.classifier import ClassificationEngine
from ui.browser import ImageBrowser
from ui.metadata_panel import MetadataPanel
from ui.batch_processor import BatchProcessor


class ImageClassifierApp:
    """Main application class."""

    def __init__(self):
        self.config = self._load_config()
        self._setup_logging()
        self.logger = logging.getLogger(__name__)

        # Initialize core components
        self.db_manager = DatabaseManager(self.config['database_path'])
        self.image_handler = ImageHandler(
            thumbnail_size=self.config['thumbnail_size'],
            max_image_size=self.config['max_image_size']
        )
        self.classifier = ClassificationEngine(self.config, self.db_manager)

        # Initialize UI
        self._setup_ui()

        self.logger.info("Application initialized successfully")

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from settings.json."""
        defaults = {
            'providers': {
                'ollama': {
                    'enabled': True,
                    'base_url': 'http://localhost:11434',
                    'model': 'llava:latest',
                    'timeout_seconds': 120
                }
            },
            'classification': {
                'primary_provider': 'ollama'
            },
            'batch_size': 10,
            'thumbnail_size': 256,
            'cache_duration': 86400,
            'database_path': str(
                Path(__file__).parent / 'image_metadata.db'
            ),
            'thumbnail_cache_dir': 'thumbnails',
            'max_image_size': 2048,
            'supported_formats': [
                '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'
            ],
            'ui_theme': 'dark',
            # Default to 6 columns to match your “6 across @ 150” goal.
            # (Dynamic columns will come next, inside ImageBrowser.)
            'grid_columns': 6,
            'rate_limit_delay': 1.0,
            # New: default gallery pane width ratio (left vs full window).
            # 0.70 ≈ “gallery is the primary surface”
            'ui_gallery_ratio': 0.70
        }
        try:
            config_path = Path(__file__).parent / 'config' / 'settings.json'
            with open(config_path, 'r') as f:
                config = json.load(f)

            # Merge defaults with config (deep merge for providers/classification)
            merged = dict(defaults)
            merged.update(config)
            merged['providers'] = {
                **defaults['providers'], **config.get('providers', {})}
            merged['classification'] = {
                **defaults['classification'], **config.get('classification', {})}

            # Convert relative paths to absolute
            db_path_value = merged.get(
                'database_path', defaults['database_path'])
            if not Path(db_path_value).is_absolute():
                db_path = Path(__file__).parent / db_path_value
                merged['database_path'] = str(db_path)

            return merged
        except Exception as e:
            print(f"Error loading config: {e}")
            # Fallback configuration
            return defaults

    def _setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('image_classifier.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def _setup_ui(self):
        """Initialize the user interface."""
        # Configure appearance
        if CTK_AVAILABLE:
            ctk.set_appearance_mode(self.config.get('ui_theme', 'dark'))
            ctk.set_default_color_theme("blue")
            self.root = ctk.CTk()
            self.root.title("Image Classifier - Desktop App")
        else:
            self.root = tk.Tk()
            self.root.title("Image Classifier - Desktop App")

        # Wider default window so the left gallery can fit more columns
        self.root.geometry("1920x1080")
        self.root.minsize(1400, 800)

        # Root grid weights: make left column dominant
        self.root.grid_columnconfigure(0, weight=5, minsize=1400)
        self.root.grid_columnconfigure(1, weight=1, minsize=360)
        self.root.grid_rowconfigure(0, weight=1)

        # Create main components
        self._create_menu()
        self._create_main_layout()

    def _create_menu(self):
        """Create the application menu."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Folder", command=self._open_folder)
        file_menu.add_command(label="Import Images",
                              command=self._import_images)
        file_menu.add_separator()
        file_menu.add_command(label="Settings", command=self._show_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Batch Process",
                               command=self._show_batch_processor)
        tools_menu.add_command(label="Search Similar",
                               command=self._search_similar)
        tools_menu.add_separator()
        tools_menu.add_command(label="Clear Cache", command=self._clear_cache)
        tools_menu.add_command(label="Database Stats",
                               command=self._show_stats)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _create_main_layout(self):
        """Create the main application layout."""
        # Main container
        if CTK_AVAILABLE:
            main_frame = ctk.CTkFrame(self.root)
        else:
            main_frame = tk.Frame(self.root)

        main_frame.grid(row=0, column=0, columnspan=2,
                        sticky="nsew", padx=6, pady=6)

        # Make left column larger so gallery has more room
        main_frame.grid_columnconfigure(0, weight=5)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Image browser (left side)
        self.image_browser = ImageBrowser(
            main_frame,
            self.db_manager,
            self.image_handler,
            self.classifier,
            grid_columns=self.config.get('grid_columns', 6),  # default toward 6
            on_selection_change=self._on_image_selection
        )
        self.image_browser.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # Metadata panel (right side)
        self.metadata_panel = MetadataPanel(
            main_frame,
            self.classifier,
            self.db_manager,
            on_metadata_change=self._on_metadata_change
        )
        self.metadata_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

    def _on_image_selection(self, image_path: str):
        """Handle image selection change."""
        metadata = self.db_manager.get_image(image_path)
        if metadata:
            self.metadata_panel.load_metadata(metadata)
        else:
            # Create metadata for new image
            metadata = self.image_handler.create_metadata(image_path)
            if metadata:
                self.db_manager.add_image(metadata)
                self.metadata_panel.load_metadata(metadata)

    def _on_metadata_change(self, image_path: str, field: str, value):
        """Handle metadata field changes."""
        self.db_manager.update_metadata(image_path, **{field: value})
        # Refresh the browser display
        self.image_browser.refresh_current_view()

    def _open_folder(self):
        """Open a folder for browsing."""
        from tkinter import filedialog

        folder = filedialog.askdirectory(title="Select Image Folder")
        if folder:
            self.image_browser.load_folder(folder)

    def _import_images(self):
        """Import individual images."""
        from tkinter import filedialog

        file_types = [
            ("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"),
            ("All files", "*.*")
        ]

        files = filedialog.askopenfilenames(
            title="Select Images to Import",
            filetypes=file_types
        )

        if files:
            self.image_browser.load_images(list(files))

    def _show_batch_processor(self):
        """Show the batch processing dialog."""
        BatchProcessor(self.root, self.classifier, self.image_browser)

    def _search_similar(self):
        """Search for similar images."""
        current_image = self.image_browser.get_selected_image()
        if current_image:
            similar_images = self.classifier.search_similar_images(
                current_image)
            if similar_images:
                self.image_browser.show_search_results(similar_images)
            else:
                self._show_message(
                    "No similar images found.", "Search Results")
        else:
            self._show_message(
                "Please select an image first.", "Search Similar")

    def _clear_cache(self):
        """Clear thumbnail and API cache."""
        self.image_handler.clear_thumbnail_cache()
        self.db_manager.cleanup_cache()
        self._show_message("Cache cleared successfully.", "Cache")

    def _show_stats(self):
        """Show database statistics."""
        stats = self.classifier.get_classification_stats()

        stats_text = "\n".join([
            f"Total Images: {stats.get('total_images', 0)}",
            f"Classified Images: {stats.get('classified_images', 0)}",
            f"Classification Rate: {stats.get('classification_rate', 0):.1%}",
            f"Average Rating: {stats.get('average_rating', 0):.1f}",
            f"Cached Images: {stats.get('cached_images', 0)}",
            "",
            "Format Distribution:",
            *[f"  {fmt}: {count}"
              for fmt, count in stats.get('format_distribution', {}).items()],
            "",
            "Provider Usage:",
            *[f"  {api}: {count}"
              for api, count in stats.get('api_usage', {}).items()]
        ])

        self._show_message(stats_text, "Database Statistics")

    def _show_settings(self):
        """Show settings dialog."""
        # TODO: Implement settings dialog
        self._show_message("Settings dialog not yet implemented.", "Settings")

    def _show_about(self):
        """Show about dialog."""
        about_text = """Image Classifier Desktop App

A lightweight Python desktop application for local image metadata management
and AI classification using Ollama (local-only).

Features:
• Image browsing and organization
• AI-powered classification using Ollama + LLaVA
• Metadata editing and tagging
• Batch processing capabilities
• Search and similarity matching (local)

Developed with Python and (Custom)Tkinter. No cloud AI providers."""
        self._show_message(about_text, "About")

    def _show_message(self, message: str, title: str):
        """Show a message dialog."""
        from tkinter import messagebox
        messagebox.showinfo(title, message)

    def _on_closing(self):
        """Handle application closing."""
        try:
            self.logger.info("Application closing...")

            # Clear caches to free memory
            self.image_handler.clear_thumbnail_cache()

            self.root.destroy()
        except Exception as e:
            self.logger.error(f"Error during application closing: {e}")
            self.root.destroy()

    def run(self):
        """Start the application."""
        try:
            self.logger.info("Starting Image Classifier Application")
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"Fatal error in main loop: {e}")
            raise


def main():
    """Main entry point."""
    try:
        app = ImageClassifierApp()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
