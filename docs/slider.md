# slider.md

Good news: your slider is already wired into `_refresh_display()`. The reason nothing changes is almost certainly:

1. the thumbnails are being generated/cached at a fixed size (or cached once and reused), and
2. your grid column logic is currently **capped** in a way that prevents “more columns when there’s room.”

We’ll fix this with **3 tight changes in `src/ui/browser.py`** (no new files, no refactor).

---

## Step 1: Make the slider apply size changes correctly (debounced) + force thumbnail refresh

### 1) Add two instance vars in `__init__` (right after `self.thumbnail_size = 150`)

```python
        self._size_change_after_id = None
        self._last_thumb_size = self.thumbnail_size
```

### 2) Replace `_on_size_change` with this (debounce + force refresh)

```python
    def _on_size_change(self, value):
        """Handle thumbnail size change."""
        new_size = int(float(value))
        if new_size == self.thumbnail_size:
            return

        self.thumbnail_size = new_size

        # Debounce so we don't re-render for every tick while dragging
        if self._size_change_after_id is not None:
            try:
                self.after_cancel(self._size_change_after_id)
            except Exception:
                pass
            self._size_change_after_id = None

        self._size_change_after_id = self.after(150, self._apply_thumbnail_size_change)

    def _apply_thumbnail_size_change(self):
        """Apply thumbnail size change and force grid refresh."""
        self._size_change_after_id = None

        # If your ImageHandler caches thumbnails, this ensures it doesn't reuse old-size thumbs.
        # This is defensive: if the method doesn't exist, we just continue.
        if self._last_thumb_size != self.thumbnail_size:
            for method_name in ("clear_thumbnail_cache", "clear_cache", "reset_cache"):
                if hasattr(self.image_handler, method_name):
                    try:
                        getattr(self.image_handler, method_name)()
                    except Exception:
                        pass
                    break

        self._last_thumb_size = self.thumbnail_size
        self._refresh_display()
```

This ensures the slider doesn’t spam re-renders and also pushes the system to stop reusing old cached thumbs.

---

## Step 2: Allow the field to “fit more” by removing the hard cap on columns

Right now you do:

```python
actual_columns = max(1, min(self.grid_columns, canvas_width // thumb_width))
```

That prevents more columns than `self.grid_columns`.

### Replace that line with this (dynamic columns)

```python
        actual_columns = max(1, canvas_width // thumb_width)
```

If you still want a safety cap (optional), use:

```python
        actual_columns = max(1, min(12, canvas_width // thumb_width))
```

But given your “fit more” requirement, the uncapped version is the most faithful.

---

## Step 3: Make it reflow when the window/pane width changes

In `_setup_ui()` (same place you create `self.canvas`), add a resize binding **once**:

```python
        self.canvas.bind("<Configure>", self._on_canvas_resize)
```

Then add this method:

```python
    def _on_canvas_resize(self, event):
        # Only reflow in grid mode; list mode doesn't need it
        if getattr(self, "view_mode", "grid") != "grid":
            return

        # Debounce resize reflow
        if getattr(self, "_resize_after_id", None) is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except Exception:
                pass

        self._resize_after_id = self.after(100, self._refresh_display)
```

---

## What you should see after these edits

* Dragging the **Size** slider should visibly change thumbnail sizes (after ~150ms pauses while dragging).
* The grid should reflow automatically as sizes change.
* If you shrink thumbnails, you should naturally get more columns (your “field fits more”).
