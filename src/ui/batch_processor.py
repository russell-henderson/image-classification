"""
Batch processor component for handling multiple images at once.
"""

import asyncio
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Optional, Callable
from pathlib import Path

try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    CTK_AVAILABLE = False
    ctk = tk

from core.classifier import ClassificationEngine
from core.database import ImageMetadata


class BatchProcessor:
    """Dialog for batch processing multiple images."""
    
    def __init__(self, parent, classifier: ClassificationEngine, image_browser):
        self.parent = parent
        self.classifier = classifier
        self.image_browser = image_browser
        self.logger = logging.getLogger(__name__)
        
        # Processing state
        self.is_processing = False
        self.current_batch = []
        self.processed_count = 0
        self.error_count = 0
        
        self._create_dialog()
    
    def _create_dialog(self):
        """Create the batch processing dialog."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Batch Image Processing")
        self.dialog.geometry("600x500")
        self.dialog.resizable(True, True)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Configure grid
        self.dialog.grid_columnconfigure(0, weight=1)
        self.dialog.grid_rowconfigure(2, weight=1)
        
        self._create_source_section()
        self._create_options_section()
        self._create_progress_section()
        self._create_buttons()
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def _create_source_section(self):
        """Create source selection section."""
        source_frame = ttk.LabelFrame(self.dialog, text="Source", padding=10)
        source_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        source_frame.grid_columnconfigure(1, weight=1)
        
        # Source type selection
        self.source_type = tk.StringVar(value="folder")
        
        tk.Radiobutton(source_frame, text="Process folder", 
                      variable=self.source_type, value="folder",
                      command=self._on_source_change).grid(row=0, column=0, sticky="w", pady=2)
        
        tk.Radiobutton(source_frame, text="Process current browser images", 
                      variable=self.source_type, value="current",
                      command=self._on_source_change).grid(row=1, column=0, sticky="w", pady=2)
        
        tk.Radiobutton(source_frame, text="Process selected files", 
                      variable=self.source_type, value="files",
                      command=self._on_source_change).grid(row=2, column=0, sticky="w", pady=2)
        
        # Path/selection display
        self.path_label = tk.Label(source_frame, text="No folder selected", 
                                  bg="white", relief=tk.SUNKEN, anchor="w")
        self.path_label.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)
        
        # Browse button
        self.browse_btn = tk.Button(source_frame, text="Browse", command=self._browse_source)
        self.browse_btn.grid(row=4, column=0, sticky="w", pady=5)
        
        # Image count
        self.count_label = tk.Label(source_frame, text="Images to process: 0")
        self.count_label.grid(row=4, column=1, sticky="e", pady=5)
    
    def _create_options_section(self):
        """Create processing options section."""
        options_frame = ttk.LabelFrame(self.dialog, text="Processing Options", padding=10)
        options_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        options_frame.grid_columnconfigure(1, weight=1)
        
        # Processing options
        self.force_refresh = tk.BooleanVar(value=False)
        self.include_subfolders = tk.BooleanVar(value=True)
        self.skip_classified = tk.BooleanVar(value=True)
        
        tk.Checkbutton(options_frame, text="Force re-classification of already processed images",
                      variable=self.force_refresh).grid(row=0, column=0, columnspan=2, sticky="w", pady=2)
        
        tk.Checkbutton(options_frame, text="Include subfolders",
                      variable=self.include_subfolders).grid(row=1, column=0, columnspan=2, sticky="w", pady=2)
        
        tk.Checkbutton(options_frame, text="Skip already classified images",
                      variable=self.skip_classified).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)
        
        # Batch size
        tk.Label(options_frame, text="Batch size:").grid(row=3, column=0, sticky="w", pady=5)
        self.batch_size = tk.IntVar(value=10)
        batch_spinbox = tk.Spinbox(options_frame, from_=1, to=50, textvariable=self.batch_size, width=10)
        batch_spinbox.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        
        # Delay between API calls
        tk.Label(options_frame, text="API delay (seconds):").grid(row=4, column=0, sticky="w", pady=5)
        self.api_delay = tk.DoubleVar(value=1.0)
        delay_spinbox = tk.Spinbox(options_frame, from_=0.1, to=10.0, increment=0.1, 
                                  textvariable=self.api_delay, width=10)
        delay_spinbox.grid(row=4, column=1, sticky="w", padx=5, pady=5)
    
    def _create_progress_section(self):
        """Create progress monitoring section."""
        progress_frame = ttk.LabelFrame(self.dialog, text="Progress", padding=10)
        progress_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        progress_frame.grid_columnconfigure(0, weight=1)
        progress_frame.grid_rowconfigure(1, weight=1)
        
        # Progress bar and status
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                           mode='determinate', length=400)
        self.progress_bar.grid(row=0, column=0, sticky="ew", pady=5)
        
        # Status text area
        self.status_text = tk.Text(progress_frame, height=15, wrap=tk.WORD, 
                                  font=("Courier", 9), state=tk.DISABLED)
        status_scrollbar = ttk.Scrollbar(progress_frame, orient="vertical", 
                                        command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_scrollbar.set)
        
        self.status_text.grid(row=1, column=0, sticky="nsew", pady=5)
        status_scrollbar.grid(row=1, column=1, sticky="ns")
        
        # Statistics
        stats_frame = tk.Frame(progress_frame)
        stats_frame.grid(row=2, column=0, sticky="ew", pady=5)
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        self.processed_label = tk.Label(stats_frame, text="Processed: 0")
        self.processed_label.grid(row=0, column=0, sticky="w")
        
        self.errors_label = tk.Label(stats_frame, text="Errors: 0")
        self.errors_label.grid(row=0, column=1, sticky="w")
        
        self.remaining_label = tk.Label(stats_frame, text="Remaining: 0")
        self.remaining_label.grid(row=0, column=2, sticky="w")
    
    def _create_buttons(self):
        """Create action buttons."""
        button_frame = tk.Frame(self.dialog)
        button_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        
        self.start_btn = tk.Button(button_frame, text="Start Processing", 
                                  command=self._start_processing, bg="green", fg="white")
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(button_frame, text="Stop", 
                                 command=self._stop_processing, state=tk.DISABLED,
                                 bg="red", fg="white")
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.close_btn = tk.Button(button_frame, text="Close", command=self._close_dialog)
        self.close_btn.pack(side=tk.RIGHT, padx=5)
        
        self.clear_btn = tk.Button(button_frame, text="Clear Log", command=self._clear_log)
        self.clear_btn.pack(side=tk.RIGHT, padx=5)
    
    def _on_source_change(self):
        """Handle source type change."""
        source = self.source_type.get()
        
        if source == "folder":
            self.browse_btn.config(state=tk.NORMAL, text="Browse Folder")
            self.path_label.config(text="No folder selected")
        elif source == "files":
            self.browse_btn.config(state=tk.NORMAL, text="Select Files")
            self.path_label.config(text="No files selected")
        else:  # current
            self.browse_btn.config(state=tk.DISABLED)
            current_count = len(self.image_browser.current_images) if self.image_browser else 0
            self.path_label.config(text=f"Current browser images ({current_count} images)")
            self.count_label.config(text=f"Images to process: {current_count}")
    
    def _browse_source(self):
        """Browse for source folder or files."""
        source = self.source_type.get()
        
        if source == "folder":
            folder = filedialog.askdirectory(title="Select Folder to Process")
            if folder:
                self.path_label.config(text=folder)
                self._count_images_in_folder(folder)
        
        elif source == "files":
            file_types = [
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"),
                ("All files", "*.*")
            ]
            files = filedialog.askopenfilenames(title="Select Images", filetypes=file_types)
            if files:
                self.path_label.config(text=f"{len(files)} files selected")
                self.count_label.config(text=f"Images to process: {len(files)}")
                self.selected_files = list(files)
    
    def _count_images_in_folder(self, folder_path: str):
        """Count images in the selected folder."""
        def count_async():
            try:
                from core.image_handler import ImageHandler
                handler = ImageHandler()
                recursive = self.include_subfolders.get()
                image_files = handler.scan_directory(folder_path, recursive=recursive)
                
                # Update UI in main thread
                self.dialog.after(0, lambda: self.count_label.config(
                    text=f"Images to process: {len(image_files)}"))
                
            except Exception as e:
                self.logger.error(f"Error counting images: {e}")
                self.dialog.after(0, lambda: self.count_label.config(
                    text="Error counting images"))
        
        threading.Thread(target=count_async, daemon=True).start()
    
    def _get_image_list(self) -> List[str]:
        """Get the list of images to process."""
        source = self.source_type.get()
        
        if source == "folder":
            folder_path = self.path_label.cget("text")
            if folder_path == "No folder selected":
                return []
            
            from core.image_handler import ImageHandler
            handler = ImageHandler()
            recursive = self.include_subfolders.get()
            return handler.scan_directory(folder_path, recursive=recursive)
        
        elif source == "files":
            return getattr(self, 'selected_files', [])
        
        elif source == "current":
            if self.image_browser and self.image_browser.current_images:
                return [img.metadata.file_path for img in self.image_browser.current_images]
        
        return []
    
    def _start_processing(self):
        """Start the batch processing."""
        if self.is_processing:
            return
        
        # Get image list
        image_list = self._get_image_list()
        if not image_list:
            messagebox.showwarning("No Images", "No images found to process.")
            return
        
        # Filter already classified images if requested
        if self.skip_classified.get():
            filtered_list = []
            for img_path in image_list:
                metadata = self.classifier.db_manager.get_image(img_path)
                if not metadata or not metadata.classification or self.force_refresh.get():
                    filtered_list.append(img_path)
            image_list = filtered_list
        
        if not image_list:
            messagebox.showinfo("No Processing Needed", 
                               "All selected images are already classified.")
            return
        
        # Setup processing
        self.current_batch = image_list
        self.processed_count = 0
        self.error_count = 0
        self.is_processing = True
        
        # Update UI
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress_var.set(0)
        
        self._log_message(f"Starting batch processing of {len(image_list)} images...")
        
        # Start processing in background thread
        threading.Thread(target=self._process_batch, daemon=True).start()
    
    def _stop_processing(self):
        """Stop the batch processing."""
        self.is_processing = False
        self._log_message("Processing stopped by user.")
        
        # Update UI
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
    
    def _process_batch(self):
        """Process the batch of images."""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            batch_size = self.batch_size.get()
            total_images = len(self.current_batch)
            
            # Process in batches
            for i in range(0, total_images, batch_size):
                if not self.is_processing:
                    break
                
                batch = self.current_batch[i:i + batch_size]
                
                # Process this batch
                try:
                    results = loop.run_until_complete(
                        self.classifier.batch_process_images(
                            batch, 
                            progress_callback=self._on_image_processed
                        )
                    )
                    
                    self.processed_count += len(results)
                    
                except Exception as e:
                    self.logger.error(f"Error processing batch: {e}")
                    self.error_count += len(batch)
                    self.dialog.after(0, lambda: self._log_message(f"Batch error: {e}"))
                
                # Update progress
                progress = (i + len(batch)) / total_images * 100
                self.dialog.after(0, lambda p=progress: self.progress_var.set(p))
                
                # Delay between batches
                if i + batch_size < total_images and self.is_processing:
                    delay = self.api_delay.get()
                    self.dialog.after(0, lambda: self._log_message(f"Waiting {delay}s before next batch..."))
                    threading.Event().wait(delay)
            
            # Processing complete
            self.dialog.after(0, self._on_processing_complete)
            
        except Exception as e:
            self.logger.error(f"Fatal error in batch processing: {e}")
            self.dialog.after(0, lambda: self._log_message(f"Fatal error: {e}"))
            self.dialog.after(0, self._on_processing_complete)
        finally:
            loop.close()
    
    def _on_image_processed(self, current: int, total: int, image_path: str):
        """Handle individual image processing completion."""
        filename = Path(image_path).name
        message = f"Processed: {filename} ({current}/{total})"
        
        # Update UI in main thread
        self.dialog.after(0, lambda: self._log_message(message))
        self.dialog.after(0, lambda: self._update_stats())
    
    def _on_processing_complete(self):
        """Handle processing completion."""
        self.is_processing = False
        
        # Update UI
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_var.set(100)
        
        # Final message
        success_count = self.processed_count - self.error_count
        message = f"Processing complete! Successfully processed: {success_count}, Errors: {self.error_count}"
        self._log_message(message)
        
        # Refresh browser if it's showing current images
        if hasattr(self.image_browser, 'refresh_current_view'):
            self.image_browser.refresh_current_view()
        
        messagebox.showinfo("Processing Complete", message)
    
    def _update_stats(self):
        """Update statistics display."""
        remaining = len(self.current_batch) - self.processed_count
        
        self.processed_label.config(text=f"Processed: {self.processed_count}")
        self.errors_label.config(text=f"Errors: {self.error_count}")
        self.remaining_label.config(text=f"Remaining: {remaining}")
    
    def _log_message(self, message: str):
        """Add a message to the log."""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}\\n"
        
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, log_line)
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
    
    def _clear_log(self):
        """Clear the log text."""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        self.status_text.config(state=tk.DISABLED)
    
    def _close_dialog(self):
        """Close the dialog."""
        if self.is_processing:
            if messagebox.askyesno("Processing Active", 
                                  "Processing is still active. Stop and close?"):
                self._stop_processing()
                self.dialog.destroy()
        else:
            self.dialog.destroy()
