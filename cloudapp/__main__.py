from kivy.lang import Builder
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from kivymd.app import MDApp
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.dialog import MDDialog
from kivymd.uix.progressbar import MDProgressBar
from kivy.clock import Clock
from github import Github
from threading import Thread
import os

KV = '''
ScreenManager:
    MainScreen:

<MainScreen>:
    name: "main"
    MDBoxLayout:
        orientation: "vertical"
        MDTopAppBar:
            title: "CoderAfroj Cloud"
            elevation: 4

        MDTextField:
            id: token_input
            hint_text: "Enter GitHub Token"
            mode: "rectangle"
            size_hint_x: .9
            pos_hint: {"center_x": .5}

        MDRaisedButton:
            text: "Connect to GitHub"
            pos_hint: {"center_x": .5}
            md_bg_color: 0, 0.6, 0.3, 1
            on_release: app.connect_github()

        MDLabel:
            id: user_label
            text: "Not connected"
            halign: "center"
            theme_text_color: "Secondary"
            padding_y: 10

        MDTextField:
            id: repo_search
            hint_text: "Search Repository"
            mode: "rectangle"
            size_hint_x: .9
            pos_hint: {"center_x": .5}
            on_text: app.filter_repos()

        ScrollView:
            MDList:
                id: repo_list

        MDBoxLayout:
            size_hint_y: None
            height: "100dp"
            orientation: "vertical"
            padding: 10
            MDTextField:
                id: upload_path
                hint_text: "Upload path (e.g. uploads/file.png)"
                mode: "rectangle"
            MDTextField:
                id: commit_msg
                hint_text: "Commit message"
                mode: "rectangle"
                text: "Uploaded via CoderAfroj Cloud"

        MDRaisedButton:
            text: "Select File to Upload"
            pos_hint: {"center_x": .5}
            on_release: app.pick_file()

        MDRaisedButton:
            text: "🚀 Upload File"
            pos_hint: {"center_x": .5}
            md_bg_color: 0, 0.4, 1, 1
            on_release: app.upload_file()

        MDProgressBar:
            id: progress
            value: 0
'''

class MainScreen(Screen):
    pass


class CloudApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "BlueGray"
        self.gh = None
        self.user = None
        self.repos = []
        self.selected_repo = None
        self.selected_file = None
        return Builder.load_string(KV)

    def log(self, msg):
        Snackbar(text=msg).open()

    def connect_github(self):
        token = self.root.ids.token_input.text.strip()
        if not token:
            self.log("Enter a valid token!")
            return
        try:
            self.gh = Github(token, timeout=20)
            self.user = self.gh.get_user()
            self.root.ids.user_label.text = f"✅ Connected as {self.user.login}"
            self.log(f"Connected as {self.user.login}")
            Thread(target=self.load_repos, daemon=True).start()
        except Exception as e:
            self.log(f"❌ Error: {e}")

    def load_repos(self):
        self.repos = list(self.user.get_repos())
        self.root.ids.repo_list.clear_widgets()
        for repo in self.repos:
            from kivymd.uix.list import OneLineListItem
            item = OneLineListItem(text=repo.full_name, on_release=lambda x, r=repo: self.select_repo(r))
            self.root.ids.repo_list.add_widget(item)

    def filter_repos(self):
        term = self.root.ids.repo_search.text.lower()
        self.root.ids.repo_list.clear_widgets()
        for repo in self.repos:
            if term in repo.full_name.lower():
                from kivymd.uix.list import OneLineListItem
                item = OneLineListItem(text=repo.full_name, on_release=lambda x, r=repo: self.select_repo(r))
                self.root.ids.repo_list.add_widget(item)

    def select_repo(self, repo):
        self.selected_repo = repo
        self.log(f"📁 Selected: {repo.full_name}")

    def pick_file(self):
        # Android file picker (works via androidstorage4kivy)
        try:
            from androidstorage4kivy import SharedStorage
            SharedStorage().open_file(self._on_file_picked)
        except Exception as e:
            self.log("File picker not supported outside Android.")

    def _on_file_picked(self, file_path):
        if file_path:
            self.selected_file = file_path
            self.log(f"Selected file: {os.path.basename(file_path)}")
            self.root.ids.upload_path.text = f"uploads/{os.path.basename(file_path)}"

    def upload_file(self):
        if not self.selected_repo or not self.selected_file:
            self.log("Select repo and file first!")
            return
        repo = self.selected_repo
        path = self.root.ids.upload_path.text.strip()
        msg = self.root.ids.commit_msg.text.strip()

        Thread(target=lambda: self._upload_worker(repo, path, msg), daemon=True).start()

    def _upload_worker(self, repo, path_in_repo, message):
        try:
            with open(self.selected_file, "rb") as f:
                content = f.read()
            try:
                existing = repo.get_contents(path_in_repo)
                repo.update_file(path_in_repo, message, content, existing.sha)
                self.log("✅ File updated successfully")
            except Exception:
                repo.create_file(path_in_repo, message, content)
                self.log("✅ File uploaded successfully")
        except Exception as e:
            self.log(f"❌ Error: {e}")
