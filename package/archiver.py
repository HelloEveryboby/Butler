import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import zipfile
import threading

# Handle import for both standalone and package modes
try:
    from package.log_manager import LogManager
except ModuleNotFoundError:
    import sys
    # Add the project root to the Python path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)


class ArchiverApp(tk.Toplevel):
    """
    A tkinter-based GUI application for compressing and decompressing files.
    """
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Archiver Tool")
        self.geometry("700x550")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Style
        style = ttk.Style(self)
        style.theme_use('clam')

        # --- Main Tabbed Interface ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(pady=10, padx=10, expand=True, fill='both')

        self.compress_tab = ttk.Frame(self.notebook)
        self.extract_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.compress_tab, text='Compress')
        self.notebook.add(self.extract_tab, text='Extract')

        # --- Build Tabs ---
        self.build_compress_tab()
        self.build_extract_tab()

        # --- Status Bar ---
        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(side='bottom', fill='x', padx=10, pady=5)
        self.status_label = ttk.Label(self.status_frame, text="Ready")
        self.status_label.pack(side='left')
        self.progress_bar = ttk.Progressbar(self.status_frame, orient='horizontal', mode='determinate')
        self.progress_bar.pack(side='right', fill='x', expand=True, padx=(10,0))

    def build_compress_tab(self):
        # --- Frame for file list ---
        list_frame = ttk.LabelFrame(self.compress_tab, text="Files and Folders to Compress")
        list_frame.pack(padx=10, pady=10, fill='both', expand=True)

        self.file_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED)
        self.file_listbox.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        list_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.file_listbox.yview)
        list_scrollbar.pack(side='right', fill='y')
        self.file_listbox.config(yscrollcommand=list_scrollbar.set)

        # --- Frame for list management buttons ---
        list_button_frame = ttk.Frame(self.compress_tab)
        list_button_frame.pack(fill='x', padx=10)

        ttk.Button(list_button_frame, text="Add File(s)", command=lambda: self.add_items('files')).pack(side='left', padx=5, pady=5)
        ttk.Button(list_button_frame, text="Add Directory", command=lambda: self.add_items('dirs')).pack(side='left', padx=5, pady=5)
        ttk.Button(list_button_frame, text="Remove Selected", command=self.remove_selected).pack(side='left', padx=5, pady=5)
        ttk.Button(list_button_frame, text="Clear All", command=self.clear_list).pack(side='left', padx=5, pady=5)

        # --- Frame for output settings ---
        output_frame = ttk.LabelFrame(self.compress_tab, text="Output Settings")
        output_frame.pack(padx=10, pady=10, fill='x')

        self.output_path_var = tk.StringVar()
        ttk.Label(output_frame, text="Output File:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ttk.Entry(output_frame, textvariable=self.output_path_var, width=60).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(output_frame, text="Browse...", command=self.browse_output_file).grid(row=0, column=2, padx=5, pady=5)
        output_frame.columnconfigure(1, weight=1)

        # --- Compress Button ---
        self.compress_button = ttk.Button(self.compress_tab, text="Compress", command=self.start_compression_thread)
        self.compress_button.pack(pady=10)

    def build_extract_tab(self):
        # --- Frame for input archive ---
        input_frame = ttk.LabelFrame(self.extract_tab, text="Archive to Extract")
        input_frame.pack(padx=10, pady=10, fill='x')

        self.archive_path_var = tk.StringVar()
        ttk.Label(input_frame, text="Archive File:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ttk.Entry(input_frame, textvariable=self.archive_path_var, width=60).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(input_frame, text="Browse...", command=self.browse_archive_file).grid(row=0, column=2, padx=5, pady=5)
        input_frame.columnconfigure(1, weight=1)

        # --- Frame for destination ---
        dest_frame = ttk.LabelFrame(self.extract_tab, text="Destination Folder")
        dest_frame.pack(padx=10, pady=10, fill='x')

        self.dest_path_var = tk.StringVar()
        ttk.Label(dest_frame, text="Extract to:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ttk.Entry(dest_frame, textvariable=self.dest_path_var, width=60).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(dest_frame, text="Browse...", command=self.browse_dest_folder).grid(row=0, column=2, padx=5, pady=5)
        dest_frame.columnconfigure(1, weight=1)

        # --- Extract Button ---
        self.extract_button = ttk.Button(self.extract_tab, text="Extract", command=self.start_extraction_thread)
        self.extract_button.pack(pady=20)

    # --- Compression Tab Methods ---
    def add_items(self, item_type):
        if item_type == 'files':
            files = filedialog.askopenfilenames(title="Select files to add")
            if files:
                for file in files:
                    if file not in self.file_listbox.get(0, tk.END):
                        self.file_listbox.insert(tk.END, file)
        elif item_type == 'dirs':
            directory = filedialog.askdirectory(title="Select a directory to add")
            if directory and directory not in self.file_listbox.get(0, tk.END):
                self.file_listbox.insert(tk.END, directory)
        self.update_status(f"Ready. Items in list: {self.file_listbox.size()}")

    def remove_selected(self):
        selected_indices = self.file_listbox.curselection()
        for i in reversed(selected_indices):
            self.file_listbox.delete(i)
        self.update_status(f"Ready. Items in list: {self.file_listbox.size()}")

    def clear_list(self):
        self.file_listbox.delete(0, tk.END)
        self.update_status("List cleared.")

    def browse_output_file(self):
        file_path = filedialog.asksaveasfilename(
            title="Save Archive As",
            defaultextension=".zip",
            filetypes=[("Zip files", "*.zip"), ("All files", "*.*")]
        )
        if file_path:
            self.output_path_var.set(file_path)

    def start_compression_thread(self):
        items_to_compress = self.file_listbox.get(0, tk.END)
        output_path = self.output_path_var.get()

        if not items_to_compress:
            messagebox.showwarning("Warning", "No files or folders to compress.", parent=self)
            return
        if not output_path:
            messagebox.showwarning("Warning", "Please specify an output file path.", parent=self)
            return

        self.compress_button.config(state=tk.DISABLED)
        self.progress_bar['value'] = 0
        self.update_status("Starting compression...")

        thread = threading.Thread(target=self.compress_files, args=(items_to_compress, output_path))
        thread.daemon = True
        thread.start()

    def compress_files(self, items, output_path):
        try:
            total_files = 0
            for item in items:
                if os.path.isfile(item):
                    total_files += 1
                elif os.path.isdir(item):
                    for _, _, files in os.walk(item):
                        total_files += len(files)

            self.progress_bar['maximum'] = total_files
            files_processed = 0

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for item in items:
                    if os.path.isfile(item):
                        arcname = os.path.basename(item)
                        zipf.write(item, arcname)
                        files_processed += 1
                        self.update_progress(files_processed, f"Compressing: {arcname}")
                    elif os.path.isdir(item):
                        base_folder = os.path.basename(item)
                        for root, _, files in os.walk(item):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.join(base_folder, os.path.relpath(file_path, item))
                                zipf.write(file_path, arcname)
                                files_processed += 1
                                self.update_progress(files_processed, f"Compressing: {file}")

            self.update_status("Compression successful!", "info")
            messagebox.showinfo("Success", f"Successfully created archive:\n{output_path}", parent=self)

        except Exception as e:
            logger.error(f"Compression failed: {e}", exc_info=True)
            self.update_status(f"Error: {e}", "error")
            messagebox.showerror("Error", f"An error occurred during compression:\n{e}", parent=self)
        finally:
            self.compress_button.config(state=tk.NORMAL)
            self.progress_bar['value'] = 0

    # --- Extraction Tab Methods ---
    def browse_archive_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Archive to Extract",
            filetypes=[("Zip files", "*.zip"), ("All files", "*.*")]
        )
        if file_path:
            self.archive_path_var.set(file_path)

    def browse_dest_folder(self):
        dir_path = filedialog.askdirectory(title="Select Destination Folder")
        if dir_path:
            self.dest_path_var.set(dir_path)

    def start_extraction_thread(self):
        archive_path = self.archive_path_var.get()
        dest_path = self.dest_path_var.get()

        if not archive_path or not os.path.exists(archive_path):
            messagebox.showwarning("Warning", "Please select a valid archive file.", parent=self)
            return
        if not dest_path or not os.path.isdir(dest_path):
            messagebox.showwarning("Warning", "Please select a valid destination folder.", parent=self)
            return

        self.extract_button.config(state=tk.DISABLED)
        self.progress_bar['value'] = 0
        self.update_status("Starting extraction...")

        thread = threading.Thread(target=self.extract_files, args=(archive_path, dest_path))
        thread.daemon = True
        thread.start()

    def extract_files(self, archive_path, dest_path):
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                file_list = zip_ref.infolist()
                total_files = len(file_list)
                self.progress_bar['maximum'] = total_files

                for i, member in enumerate(file_list):
                    zip_ref.extract(member, dest_path)
                    self.update_progress(i + 1, f"Extracting: {member.filename}")

            self.update_status("Extraction successful!", "info")
            messagebox.showinfo("Success", f"Successfully extracted archive to:\n{dest_path}", parent=self)

        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            self.update_status(f"Error: {e}", "error")
            messagebox.showerror("Error", f"An error occurred during extraction:\n{e}", parent=self)
        finally:
            self.extract_button.config(state=tk.NORMAL)
            self.progress_bar['value'] = 0

    def update_progress(self, value, status_text):
        self.progress_bar['value'] = value
        self.update_status(status_text)

    def update_status(self, message, level="info"):
        self.status_label.config(text=message)
        if level == "error":
            logger.error(message)
        else:
            logger.info(message)
        self.update_idletasks()

    def on_close(self):
        """ Handles the window close event. """
        logger.info("Archiver window closed.")
        self.destroy()

def run():
    """
    Entry point for the Butler system to launch the Archiver application.
    This function handles being called from within a running Tkinter app
    or running standalone.
    """
    try:
        # Check if a root window already exists (i.e., we are running from Butler)
        try:
            master = tk._get_default_root()
            app = ArchiverApp(master=master)
        except RuntimeError:
            # No root window exists, run in standalone mode.
            logger.info("No Tk root found, running Archiver in standalone mode.")
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            app = ArchiverApp(master=root)
            # When the app window is closed, destroy the hidden root to exit.
            app.protocol("WM_DELETE_WINDOW", lambda: (app.on_close(), root.destroy()))
            root.mainloop() # Start the event loop for standalone mode

    except Exception as e:
        logger.error(f"Failed to launch ArchiverApp: {e}", exc_info=True)
        # Fallback to console print if GUI elements fail.
        print(f"Error: Could not launch the Archiver application.\n{e}")

if __name__ == '__main__':
    run()
