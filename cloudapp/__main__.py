# app.py
import os
import threading
from datetime import datetime
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path

import customtkinter as ctk
from github import Github, GithubException
from PIL import Image

# ---------- Config ----------
APP_TITLE = "CoderAfroj Cloud - Professional GitHub Uploader"
DEFAULT_UPLOAD_MESSAGE = "Uploaded via CoderAfroj Cloud"
SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}
SUPPORTED_DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.md', '.csv', '.xls', '.xlsx'}

# ---------- Helpers ----------
def human_size(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}P{suffix}"

def get_file_type_icon(file_path):
    ext = Path(file_path).suffix.lower()
    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        return "🖼️"
    elif ext in SUPPORTED_DOCUMENT_EXTENSIONS:
        return "📄"
    else:
        return "📁"

# ---------- App ----------
class GitHubUploaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1200x800")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # State variables
        self.gh = None
        self.user = None
        self.repos = []
        self.selected_repo = None
        self.selected_file = None
        self.upload_thread = None
        self.preview_image = None

        self.setup_ui()

    # ---------- UI ----------
    def setup_ui(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self.root, width=300, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(4, weight=1)

        main_content = ctk.CTkFrame(self.root, corner_radius=0)
        main_content.grid(row=0, column=1, sticky="nsew")
        main_content.grid_columnconfigure(0, weight=1)
        main_content.grid_rowconfigure(1, weight=1)

        # Sidebar content
        ctk.CTkLabel(sidebar, text="CoderAfroj Cloud",
                     font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))

        token_frame = ctk.CTkFrame(sidebar)
        token_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(token_frame, text="GitHub Token:", anchor="w").pack(anchor="w", padx=10, pady=(10, 5))
        self.token_entry = ctk.CTkEntry(token_frame, placeholder_text="ghp_xxx...", show="*", width=250)
        self.token_entry.pack(fill="x", padx=10, pady=5)

        token_btn_frame = ctk.CTkFrame(token_frame, fg_color="transparent")
        token_btn_frame.pack(fill="x", padx=10, pady=(5, 10))

        self.show_token_var = tk.BooleanVar(value=False)
        show_cb = ctk.CTkCheckBox(token_btn_frame, text="Show", variable=self.show_token_var,
                                  command=self.toggle_show_token)
        show_cb.pack(side="left")

        connect_btn = ctk.CTkButton(token_btn_frame, text="Connect", command=self.connect_github,
                                    fg_color="#238636", hover_color="#2ea043")
        connect_btn.pack(side="right")

        # Repo section
        repo_frame = ctk.CTkFrame(sidebar)
        repo_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(repo_frame, text="Repositories", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        self.repo_search = ctk.CTkEntry(repo_frame, placeholder_text="Search repositories...")
        self.repo_search.pack(fill="x", padx=10, pady=5)
        self.repo_search.bind("<KeyRelease>", self.filter_repos)

        self.repo_listbox = tk.Listbox(repo_frame, height=12, bg="#1a1a1a", fg="white",
                                       selectbackground="#2fa572", activestyle="none", font=("Arial", 10))
        self.repo_listbox.pack(fill="both", expand=True, padx=10, pady=5)
        self.repo_listbox.bind("<<ListboxSelect>>", self.on_repo_select)

        repo_btn_frame = ctk.CTkFrame(repo_frame, fg_color="transparent")
        repo_btn_frame.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkButton(repo_btn_frame, text="Refresh", command=self.load_repos, width=80).pack(side="left", padx=(0, 5))
        ctk.CTkButton(repo_btn_frame, text="Open", command=self.open_selected_repo, width=80).pack(side="left")

        # Create repo section
        create_frame = ctk.CTkFrame(sidebar)
        create_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(create_frame, text="Create New Repository",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        self.new_repo_entry = ctk.CTkEntry(create_frame, placeholder_text="new-repo-name")
        self.new_repo_entry.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(create_frame, text="Create Repository", command=self.create_repo).pack(fill="x", padx=10, pady=(5, 10))

        # Main content - file section
        file_section = ctk.CTkFrame(main_content)
        file_section.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        file_section.grid_columnconfigure(1, weight=1)

        self.file_icon_label = ctk.CTkLabel(file_section, text="📁", font=ctk.CTkFont(size=24))
        self.file_icon_label.grid(row=0, column=0, padx=10)
        self.file_name_label = ctk.CTkLabel(file_section, text="No file selected", font=ctk.CTkFont(weight="bold"))
        self.file_name_label.grid(row=0, column=1, sticky="w")

        choose_btn = ctk.CTkButton(file_section, text="Choose File", command=self.choose_file,
                                   fg_color="#2fa572", hover_color="#38c97a")
        choose_btn.grid(row=0, column=2, sticky="e", padx=10, pady=10)

        # Preview
        self.preview_label = ctk.CTkLabel(main_content, text="Preview will appear here for images")
        self.preview_label.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Upload
        upload_options = ctk.CTkFrame(main_content)
        upload_options.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(upload_options, text="Upload Path in Repository:").pack(anchor="w", padx=10, pady=(5, 0))
        self.path_entry = ctk.CTkEntry(upload_options, placeholder_text="uploads/")
        self.path_entry.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(upload_options, text="Commit Message:").pack(anchor="w", padx=10, pady=(10, 0))
        self.message_entry = ctk.CTkEntry(upload_options, placeholder_text=DEFAULT_UPLOAD_MESSAGE)
        self.message_entry.pack(fill="x", padx=10, pady=5)

        btn_frame = ctk.CTkFrame(upload_options, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        self.upload_btn = ctk.CTkButton(btn_frame, text="🚀 Upload to GitHub", command=self.upload_file,
                                        fg_color="#238636", hover_color="#2ea043", font=ctk.CTkFont(weight="bold"))
        self.upload_btn.pack(side="left", padx=(0, 10))
        self.cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=self.cancel_upload,
                                        fg_color="#d32f2f", hover_color="#f44336", state="disabled")
        self.cancel_btn.pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(btn_frame, height=20, width=200)
        self.progress_bar.pack(side="right")
        self.progress_bar.set(0)

        # Log
        self.log_text = ctk.CTkTextbox(main_content, height=150, fg_color="#0f1720", text_color="#cbd5e1")
        self.log_text.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))

        self.status_label = ctk.CTkLabel(main_content, text="Ready to connect...", anchor="w")
        self.status_label.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 10))

        self.log("🚀 CoderAfroj Cloud started")

    # ---------- UI Helpers ----------
    def toggle_show_token(self):
        self.token_entry.configure(show="" if self.show_token_var.get() else "*")

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")

    def set_status(self, text):
        self.status_label.configure(text=text)

    def show_preview(self, file_path):
        from customtkinter import CTkImage
        file_ext = Path(file_path).suffix.lower()
        if file_ext in SUPPORTED_IMAGE_EXTENSIONS:
            img = CTkImage(Image.open(file_path), size=(300, 200))
            self.preview_label.configure(image=img, text="")
            self.preview_label.image = img
        else:
            self.preview_label.configure(image=None, text="No preview available")

    # ---------- GitHub ----------
    def connect_github(self):
        token = self.token_entry.get().strip()
        if not token:
            messagebox.showerror("Error", "Please enter a GitHub token.")
            return
        self.set_status("Connecting to GitHub...")
        try:
            self.gh = Github(token, timeout=20)
            self.user = self.gh.get_user()
            self.set_status(f"✅ Connected as {self.user.login}")
            self.log(f"Connected as {self.user.login}")
            self.load_repos()
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed: {e}")
            self.set_status("❌ Connection failed")

    def load_repos(self):
        if not self.user:
            return
        self.repo_listbox.delete(0, "end")
        self.repos = list(self.user.get_repos())
        for repo in self.repos:
            private_flag = " 🔒" if repo.private else ""
            self.repo_listbox.insert("end", f"{repo.full_name}{private_flag}")

    def filter_repos(self, event=None):
        term = self.repo_search.get().lower()
        self.repo_listbox.delete(0, "end")
        for repo in self.repos:
            if term in repo.full_name.lower():
                self.repo_listbox.insert("end", f"{repo.full_name}")

    def on_repo_select(self, event=None):
        sel = self.repo_listbox.curselection()
        if sel:
            self.selected_repo = self.repos[sel[0]]
            self.set_status(f"📁 Selected: {self.selected_repo.full_name}")

    def open_selected_repo(self):
        if self.selected_repo:
            import webbrowser
            webbrowser.open(self.selected_repo.html_url)

    def create_repo(self):
        if not self.user:
            return
        name = self.new_repo_entry.get().strip()
        if not name:
            return
        threading.Thread(target=lambda: self._create_repo_worker(name), daemon=True).start()

    def _create_repo_worker(self, name):
        try:
            repo = self.user.create_repo(name, auto_init=True)
            self.log(f"✅ Repository created: {repo.full_name}")
            self.load_repos()
        except Exception as e:
            self.log(f"❌ Failed: {e}")

    def choose_file(self):
        path = filedialog.askopenfilename(title="Select file to upload")
        if path:
            self.selected_file = path
            size = os.path.getsize(path)
            self.file_icon_label.configure(text=get_file_type_icon(path))
            self.file_name_label.configure(text=os.path.basename(path))
            self.log(f"Selected: {path}")
            self.show_preview(path)
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, f"uploads/{os.path.basename(path)}")

    def upload_file(self):
        if not self.selected_repo or not self.selected_file:
            return
        repo = self.selected_repo
        path_in_repo = self.path_entry.get().strip()
        commit_message = self.message_entry.get().strip() or DEFAULT_UPLOAD_MESSAGE
        threading.Thread(target=self._upload_worker, args=(repo, path_in_repo, commit_message), daemon=True).start()

    def _upload_worker(self, repo, path_in_repo, commit_message):
        try:
            with open(self.selected_file, "rb") as f:
                content = f.read()
            try:
                existing = repo.get_contents(path_in_repo)
                repo.update_file(path_in_repo, commit_message, content, existing.sha)
                self.set_status("✅ File updated successfully (image visible on GitHub)")
            except Exception:
                repo.create_file(path_in_repo, commit_message, content)
                self.set_status("✅ File uploaded successfully (image visible on GitHub)")
        except Exception as e:
            self.set_status(f"❌ Error: {str(e)}")

    def cancel_upload(self):
        self.set_status("Upload cancelled")

# ---------- Run ----------
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    app = GitHubUploaderApp(root)
    root.mainloop()
