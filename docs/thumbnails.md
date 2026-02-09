Yes, I understand exactly what you’re saying.

### What’s actually happening (based on your 600px screenshot)

You have **enough horizontal space** for 3 columns at ~500–550px, but the grid is behaving like it only has room for 2 columns because the code is calculating columns off a **smaller “effective width”** than what you see on screen.

In Tkinter “canvas + embedded frame” layouts, this usually happens when:

* the **embedded frame inside the canvas is not being resized to the canvas width**, so it stays stuck at an older/narrower width, and
* your column calculation uses `canvas.winfo_width()` (or the embedded frame width) that does not reflect the true usable area.

That produces the exact symptom you showed: **large blank area on the right inside the gallery**, while thumbnails wrap too early.

Cursor likely assumed the blank area was a separate metadata pane because that’s a common two-column pattern, but in your case it’s just **unused width inside the gallery canvas region**.

---

## The fix: force the scrollable inner frame to match the canvas width

This is the canonical fix for “unused space on the right” in a scrollable canvas grid.

### Step 1 (do only this)

In `src/ui/browser.py`, find where you create the embedded frame inside the canvas. It will look like one of these patterns:

```py
self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
```

or

```py
self.canvas.create_window(...)
```

Make sure you **store** the window id:

```python
self.canvas_window = self.canvas.create_window(
    (0, 0),
    window=self.scrollable_frame,
    anchor="nw"
)
```

Then update your existing canvas `<Configure>` handler (or add one if missing) to include this line:

```python
def _on_canvas_resize(self, event):
    # This line is the key: it forces the inner frame to take the full canvas width
    self.canvas.itemconfigure(self.canvas_window, width=event.width)

    # optional: debounce reflow if you already do that
    if getattr(self, "_resize_after_id", None):
        try:
            self.after_cancel(self._resize_after_id)
        except Exception:
            pass
    self._resize_after_id = self.after(80, self._refresh_display)
```

That single `itemconfigure(..., width=event.width)` is what stops the inner frame from staying narrow and leaving that dead space.
