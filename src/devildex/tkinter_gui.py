import tkinter as tk
from tkinter import ttk
import tkinterweb
import TKinterModernThemes as TKMT


class MiniBrowser(TKMT.ThemedTKinterFrame):
    def __init__(self, theme, mode, usecommandlineargs=True, usethemeconfigfile=True, url=None):

        super().__init__("Mini Browser con tkinterweb", theme, mode,
                         usecommandlineargs, usethemeconfigfile)
        self.url = url

        self.address_bar_frame = ttk.Frame(
            self.master)
        self.address_bar_frame.pack(side='top', fill='x', padx=10, pady=10)

        self.url_label = ttk.Label(self.address_bar_frame, text="URL:")
        self.url_label.pack(side='left', padx=(0, 5))

        self.url_entry = ttk.Entry(self.address_bar_frame)
        self.url_entry.pack(side='left', expand=True, fill='x')
        self.url_entry.bind("<Return>", self.load_url_event)

        self.load_button = ttk.Button(self.address_bar_frame, text="Vai", command=self.load_url)
        self.load_button.pack(side='left', padx=(5, 0))
        self.html_viewer = tkinterweb.HtmlFrame(self.master, messages_enabled=False)
        self.html_viewer.pack(expand=True, fill='both', padx=10, pady=(0, 10))
        if not self.url:
            self.url = "https://www.google.com"

        self.url_entry.insert(0, self.url)
        self.load_url()

        self.master.rowconfigure(1, weight=1)
        self.master.columnconfigure(0, weight=1)

    def load_url(self):
        url = self.url_entry.get()
        if url:
            print(f"Caricamento URL: {url}")
            self.html_viewer.load_website(url)

    def load_url_event(self, event):
        self.load_url()


if __name__ == "__main__":
    app = MiniBrowser(theme="sun-valley", mode="light", url="https://www.google.com")

    app.root.mainloop()