import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from github import Github

class CloudApp(toga.App):
    def startup(self):
        # --------- Main window ---------
        self.main_window = toga.MainWindow(title=self.formal_name)

        # GitHub token input
        self.token_input = toga.TextInput(placeholder="GitHub Token (ghp_xxx...)", style=Pack(flex=1))
        self.connect_button = toga.Button("Connect", on_press=self.connect_github, style=Pack(padding_left=10))
        top_row = toga.Box(children=[self.token_input, self.connect_button], style=Pack(direction=ROW, padding=10))

        # Repo list
        self.repo_list = toga.Selection(items=[], style=Pack(flex=1))
        self.refresh_button = toga.Button("Refresh Repos", on_press=self.refresh_repos, style=Pack(padding_top=5))

        # File chooser
        self.file_label = toga.Label("No file selected", style=Pack(padding=5))
        self.choose_button = toga.Button("Choose File", on_press=self.choose_file, style=Pack(padding=5))

        # Upload inputs
        self.path_input = toga.TextInput(placeholder="uploads/", style=Pack(flex=1))
        self.message_input = toga.TextInput(placeholder="Upload message", style=Pack(flex=1, padding_top=5))
        self.upload_button = toga.Button("Upload", on_press=self.upload_file, style=Pack(padding=10, flex=1))

        # Log area
        self.log = toga.MultilineTextInput(readonly=True, style=Pack(flex=1, height=150))

        # Layout
        main_box = toga.Box(
            children=[
                top_row,
                self.repo_list,
                self.refresh_button,
                self.file_label,
                self.choose_button,
                self.path_input,
                self.message_input,
                self.upload_button,
                self.log
            ],
            style=Pack(direction=COLUMN, padding=10)
        )

        self.main_window.content = main_box
        self.main_window.show()

        # internal state
        self.gh = None
        self.user = None
        self.selected_repo = None
        self.selected_file = None

    # ---------- Logic ----------
    def log_msg(self, text):
        self.log.value += f"{text}\n"

    def connect_github(self, widget):
        token = self.token_input.value.strip()
        if not token:
            self.log_msg("❌ Enter a valid GitHub token.")
            return
        try:
            self.gh = Github(token, timeout=15)
            self.user = self.gh.get_user()
            self.log_msg(f"✅ Connected as {self.user.login}")
            self.refresh_repos(widget)
        except Exception as e:
            self.log_msg(f"❌ Connection failed: {e}")

    def refresh_repos(self, widget):
        if not self.user:
            self.log_msg("⚠️ Connect first.")
            return
        self.repo_list.items = [repo.full_name for repo in self.user.get_repos()]
        self.log_msg("🔄 Repositories loaded.")

    def choose_file(self, widget):
        try:
            file_path = self.main_window.open_file_dialog("Select file")
            if file_path:
                self.selected_file = file_path
                self.file_label.text = f"📄 {file_path.split('/')[-1]}"
                self.log_msg(f"Selected: {file_path}")
        except Exception as e:
            self.log_msg(f"❌ File select error: {e}")

    def upload_file(self, widget):
        if not self.selected_file or not self.repo_list.value:
            self.log_msg("⚠️ Select repo and file first.")
            return
        repo_name = self.repo_list.value
        repo = self.user.get_repo(repo_name)
        path_in_repo = self.path_input.value or "uploads/"
        commit_msg = self.message_input.value or "Uploaded via CloudApp"

        try:
            with open(self.selected_file, "rb") as f:
                content = f.read()

            # Try update, else create
            try:
                existing = repo.get_contents(path_in_repo)
                repo.update_file(path_in_repo, commit_msg, content, existing.sha)
                self.log_msg("✅ File updated successfully.")
            except Exception:
                repo.create_file(path_in_repo, commit_msg, content)
                self.log_msg("✅ File uploaded successfully.")
        except Exception as e:
            self.log_msg(f"❌ Upload error: {e}")

def main():
    return CloudApp("CloudApp", "com.bytecore.cloudapp")
