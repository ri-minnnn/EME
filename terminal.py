
import tkinter as tk

class Terminal:
    def __init__(self, text_widget: tk.Text):
        self.text_widget = text_widget
        self.text_widget.config(state="normal")
        self.clear()

    def log(self, message: str):
        """Append a new line of text in the terminal."""
        self.text_widget.config(state="normal")
        self.text_widget.insert("end", message + "\n")
        self.text_widget.see("end")  # auto-scroll
        self.text_widget.config(state="disabled")

    def clear(self):
        """Clear the terminal window."""
        self.text_widget.config(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.config(state="disabled")
