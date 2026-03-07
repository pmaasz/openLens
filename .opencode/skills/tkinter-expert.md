# Tkinter Expert Skill

This skill provides specialized knowledge for working with the Tkinter GUI framework in Python.

## Core Principles

1. **Geometry Management**
   - **Never mix `pack()` and `grid()`** within the same parent widget. This causes the application to freeze.
   - Prefer `pack()` for simple vertical/horizontal layouts.
   - Prefer `grid()` for form-like layouts or complex alignments.
   - Always configure row/column weights (`grid_rowconfigure`, `grid_columnconfigure`) when using `grid()` to handle resizing.

2. **Variable Handling**
   - Use Tkinter variables (`StringVar`, `IntVar`, `BooleanVar`, `DoubleVar`) for data binding.
   - Attach variables to widgets via the `variable=` or `textvariable=` parameter.
   - Use `.get()` and `.set()` methods to access/modify values.
   - Use `.trace_add("write", callback)` to react to value changes.

3. **Thread Safety & Responsiveness**
   - **Never run long-blocking operations** in the main thread (e.g., heavy calculations, file I/O). It freezes the GUI.
   - Use `root.after(ms, callback)` to schedule tasks or run animations.
   - For heavy tasks, use `threading.Thread`, but **never update GUI widgets directly from a background thread**. Use a thread-safe queue or `root.after` to marshal updates back to the main thread.

4. **Event Binding**
   - Bind events using `widget.bind("<Event-Name>", handler)`.
   - Handler functions must accept an `event` argument, even if unused.
   - Common events: `<Button-1>` (click), `<Key>`, `<Configure>` (resize), `<Return>`.

5. **Structure**
   - Subclass `tk.Frame` or `tk.Toplevel` for custom components.
   - Keep GUI logic separate from business logic (Service Layer pattern).

## Code Snippets

### Standard Boilerplate
```python
import tkinter as tk
from tkinter import ttk

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Application")
        self.geometry("800x600")
        
        # Configure grid weights for resizing
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        self.main_frame = MainFrame(self)
        self.main_frame.grid(sticky="nsew")

if __name__ == "__main__":
    app = App()
    app.mainloop()
```

### Thread-Safe Update
```python
import threading
import queue

class WorkerFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.queue = queue.Queue()
        self.start_button = ttk.Button(self, text="Start", command=self.start_task)
        self.start_button.pack()
        
        # Check queue periodically
        self.after(100, self.check_queue)

    def start_task(self):
        threading.Thread(target=self.heavy_work, daemon=True).start()

    def heavy_work(self):
        # ... do heavy work ...
        result = "Done"
        self.queue.put(result)

    def check_queue(self):
        try:
            result = self.queue.get_nowait()
            self.on_task_complete(result)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.check_queue)
```
