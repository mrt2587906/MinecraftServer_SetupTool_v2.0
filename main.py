# -*- coding: utf-8 -*-
import os, sys, subprocess, shutil, tempfile, threading, time, datetime, webbrowser
import tkinter as tk
from tkinter import messagebox, filedialog
import requests
import zipfile
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ========================
# Core Modules
# ========================

# --- Paper 管理 ---
class PaperManager:
    def get_versions(self):
        try:
            r = requests.get("https://api.papermc.io/v2/projects/paper")
            r.raise_for_status()
            return r.json().get("versions",[])
        except:
            return []

    def download(self, folder, version):
        builds_url = f"https://api.papermc.io/v2/projects/paper/versions/{version}"
        r = requests.get(builds_url); r.raise_for_status()
        latest_build = r.json()["builds"][-1]
        jar_url = f"https://api.papermc.io/v2/projects/paper/versions/{version}/builds/{latest_build}/downloads/paper-{version}-{latest_build}.jar"
        jar_path = os.path.join(folder,"server.jar")
        os.makedirs(folder, exist_ok=True)
        with open(jar_path,"wb") as f:
            f.write(requests.get(jar_url).content)
        return jar_path

# --- Java 管理 ---
class JavaManager:
    def get_required_version(self, mc_version):
        try:
            parts = mc_version.split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts)>1 else 0
            if major>=21 or (major==20 and minor>=5): return 21
            if major>=17: return 17
            return 8
        except: return 8

    def download(self, version, folder):
        base = f"https://api.adoptium.net/v3/assets/latest/{version}/hotspot"
        params = {"architecture":"x64","heap_size":"normal","image_type":"jdk",
                  "jvm_impl":"hotspot","os":"windows","vendor":"eclipse"}
        r = requests.get(base, params=params); r.raise_for_status()
        url = r.json()[0]["binary"]["package"]["link"]
        zip_path = os.path.join(tempfile.gettempdir(),f"java{version}.zip")
        with open(zip_path,"wb") as f:
            f.write(requests.get(url).content)
        extract_path = os.path.join(folder,f"java{version}")
        if os.path.exists(extract_path): shutil.rmtree(extract_path)
        with zipfile.ZipFile(zip_path,'r') as zip_ref: zip_ref.extractall(extract_path)
        for root,dirs,files in os.walk(extract_path):
            if "java.exe" in files: return os.path.join(root,"java.exe")
        return None

# --- 世界備份 ---
class BackupManager:
    def __init__(self, server_folder="server"):
        self.server_folder = server_folder
        self.backup_folder = os.path.join(server_folder,"backups")
        os.makedirs(self.backup_folder, exist_ok=True)

    def create_backup(self):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"world_backup_{ts}"
        src = os.path.join(self.server_folder,"world")
        dest = os.path.join(self.backup_folder,name)
        if os.path.exists(src):
            shutil.copytree(src,dest)
            return dest
        return None

    def list_backups(self):
        return [f for f in os.listdir(self.backup_folder) if os.path.isdir(os.path.join(self.backup_folder,f))]

    def restore_backup(self,name):
        src = os.path.join(self.backup_folder,name)
        dest = os.path.join(self.server_folder,"world")
        if os.path.exists(dest): shutil.rmtree(dest)
        shutil.copytree(src,dest)
        return True

# --- 防火牆管理 ---
class FirewallManager:
    @staticmethod
    def open_port(port):
        try:
            subprocess.run(f'netsh advfirewall firewall add rule name="MCServer{port}" dir=in action=allow protocol=TCP localport={port}',
                           shell=True, check=True)
            return True
        except: return False

# ========================
# GUI Pages
# ========================

# --- 核心頁面 ---
class CorePage(ctk.CTkFrame):
    def __init__(self,parent):
        super().__init__(parent)
        self.server_folder="server"; os.makedirs(self.server_folder, exist_ok=True)
        self.paper=PaperManager(); self.java=JavaManager(); self.backup=BackupManager(self.server_folder)
        self.server_process=None

        ctk.CTkLabel(self,text="伺服器核心設定",font=("Arial",18,"bold")).pack(pady=10)

        # 版本選擇
        f_ver=ctk.CTkFrame(self); f_ver.pack(pady=5,fill="x",padx=10)
        ctk.CTkLabel(f_ver,text="Paper 版本:",font=("Arial",14)).grid(row=0,column=0,padx=5,pady=5,sticky="w")
        self.version_var=tk.StringVar(value="請選擇版本")
        self.versions=self.paper.get_versions(); self.versions.reverse()
        ctk.CTkOptionMenu(f_ver,variable=self.version_var,values=self.versions,width=150).grid(row=0,column=1,padx=5,pady=5)

        # Java 選項
        f_java=ctk.CTkFrame(self); f_java.pack(pady=5,fill="x",padx=10)
        ctk.CTkLabel(f_java,text="自動下載 Java:",font=("Arial",14)).grid(row=0,column=0,padx=5,pady=5,sticky="w")
        self.download_java_var=tk.BooleanVar(value=False)
        ctk.CTkCheckBox(f_java,variable=self.download_java_var).grid(row=0,column=1)

        # 記憶體
        f_mem=ctk.CTkFrame(self); f_mem.pack(pady=5,fill="x",padx=10)
        ctk.CTkLabel(f_mem,text="最小記憶體 (MB):",font=("Arial",13)).grid(row=0,column=0,padx=5,pady=5,sticky="w")
        self.min_mem=tk.IntVar(value=1024)
        ctk.CTkSlider(f_mem,from_=512,to=8192,variable=self.min_mem).grid(row=0,column=1,padx=5,pady=5)
        ctk.CTkLabel(f_mem,text="最大記憶體 (MB):",font=("Arial",13)).grid(row=1,column=0,padx=5,pady=5,sticky="w")
        self.max_mem=tk.IntVar(value=4096)
        ctk.CTkSlider(f_mem,from_=1024,to=16384,variable=self.max_mem).grid(row=1,column=1,padx=5,pady=5)

        # EULA
        f_eula=ctk.CTkFrame(self); f_eula.pack(pady=5,fill="x",padx=10)
        self.eula_var=tk.BooleanVar(value=False)
        ctk.CTkCheckBox(f_eula,text="同意 EULA",variable=self.eula_var).pack(side="left",padx=5)

        # 狀態
        self.status_var=tk.StringVar(value="狀態: 尚未啟動")
        ctk.CTkLabel(self,textvariable=self.status_var,font=("Arial",14,"bold"),text_color="green").pack(pady=5)

        # 按鈕
        f_btn=ctk.CTkFrame(self); f_btn.pack(pady=10)
        ctk.CTkButton(f_btn,text="下載 & 建立伺服器",command=self.create_server).pack(side="left",padx=5)
        ctk.CTkButton(f_btn,text="啟動伺服器",command=self.start_server).pack(side="left",padx=5)
        ctk.CTkButton(f_btn,text="停止伺服器",command=self.stop_server).pack(side="left",padx=5)

    def create_server(self):
        version=self.version_var.get()
        if version=="請選擇版本":
            self.status_var.set("⚠ 請選擇 Paper 版本"); return
        java_path=None
        if self.download_java_var.get():
            java_ver=self.java.get_required_version(version)
            self.status_var.set(f"下載 Java {java_ver}...")
            java_path=self.java.download(java_ver,self.server_folder)
            self.status_var.set("Java 下載完成")
        self.status_var.set(f"下載 Paper {version}...")
        self.paper.download(self.server_folder,version)
        self.status_var.set("Paper 下載完成")
        if self.eula_var.get():
            with open(os.path.join(self.server_folder,"eula.txt"),"w") as f: f.write("eula=true\n")
            self.status_var.set("EULA 已同意")
        self.status_var.set("伺服器建立完成 ✅")

    def start_server(self):
        if self.server_process:
            self.status_var.set("⚠ 伺服器已啟動"); return
        jar=os.path.join(self.server_folder,"server.jar")
        if not os.path.exists(jar):
            self.status_var.set("⚠ server.jar 不存在"); return
        self.server_process=subprocess.Popen(
            ["java",f"-Xms{self.min_mem.get()}M",f"-Xmx{self.max_mem.get()}M","-jar",jar,"nogui"],
            cwd=self.server_folder
        )
        self.status_var.set("伺服器已啟動 ▶")

    def stop_server(self):
        if self.server_process:
            self.server_process.terminate(); self.server_process=None
            self.status_var.set("伺服器已停止 ⏹")
        else: self.status_var.set("⚠ 伺服器未啟動")

# ========================
# Backup Page
# ========================
class BackupPage(ctk.CTkFrame):
    def __init__(self,parent):
        super().__init__(parent)
        self.manager=BackupManager()
        ctk.CTkLabel(self,text="世界備份管理",font=("Arial",18)).pack(pady=10)
        f_btn=ctk.CTkFrame(self); f_btn.pack(pady=5)
        ctk.CTkButton(f_btn,text="建立備份",command=self.backup).pack(side="left",padx=5)
        ctk.CTkButton(f_btn,text="還原備份",command=self.restore).pack(side="left",padx=5)
        self.listbox=ctk.CTkTextbox(self,height=300)
        self.listbox.pack(fill="both",expand=True,padx=10,pady=10)
        self.refresh_list()

    def refresh_list(self):
        self.listbox.delete("1.0","end")
        self.backups=self.manager.list_backups()
        for i,b in enumerate(self.backups): self.listbox.insert("end",f"{i}. {b}\n")

    def backup(self):
        path=self.manager.create_backup()
        if path: self.listbox.insert("end",f"✔ 已建立備份: {path}\n"); self.refresh_list()

    def restore(self):
        line=self.listbox.get("insert linestart","insert lineend")
        if not line: return
        index=int(line.split(".")[0])
        self.manager.restore_backup(self.backups[index])
        self.listbox.insert("end",f"✔ 已還原: {self.backups[index]}\n")

# ========================
# Settings Page
# ========================
class SettingsPage(ctk.CTkFrame):
    def __init__(self,parent):
        super().__init__(parent)
        ctk.CTkLabel(self,text="伺服器設定",font=("Arial",18)).pack(pady=10)
        f=ctk.CTkFrame(self); f.pack(pady=10,padx=10,fill="x")
        tk.Label(f,text="伺服器 Port:", font=("Arial",14)).grid(row=0,column=0,padx=5,pady=5,sticky="w")
        self.port_var=tk.IntVar(value=25565)
        ctk.CTkEntry(f,textvariable=self.port_var,width=100).grid(row=0,column=1,padx=5,pady=5)
        ctk.CTkButton(f,text="開啟防火牆 Port",command=self.open_port).pack(pady=5)
        self.status_var=tk.StringVar(value="")
        ctk.CTkLabel(self,textvariable=self.status_var,font=("Arial",14),text_color="green").pack(pady=5)

    def open_port(self):
        port=self.port_var.get()
        if FirewallManager.open_port(port):
            self.status_var.set(f"✔ 已開啟 Port {port}")

# ========================
# About Page / Contributors
# ========================
class AboutPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        ctk.CTkLabel(self, text="Minecraft 伺服器架設工具", font=("微軟正黑體", 18, "bold")).pack(pady=(10,5))
        ctk.CTkLabel(self, text="版本：1.4", font=("微軟正黑體", 15)).pack(pady=2)
        ctk.CTkLabel(self, text="原作者：Evan小饅頭", font=("微軟正黑體", 15)).pack(pady=2)

        separator = ctk.CTkFrame(self, height=2, fg_color="#444444")
        separator.pack(fill="x", padx=20, pady=(10,10))

        ctk.CTkLabel(self, text="貢獻者名單：", font=("微軟正黑體",16,"bold")).pack(anchor="w", padx=20)

        contributors = [
            ("Evan小饅頭","https://www.youtube.com/channel/UCE8BD2BIgZIrdYl5l5niYHA/"),
            ("聖典騎士", "https://www.youtube.com/@sondancuisu113"),
        ]

        for name, link in contributors:
            if link:
                lbl = ctk.CTkLabel(self, text=name, font=("微軟正黑體",14,"underline"),
                                   text_color="skyblue", cursor="hand2")
                lbl.bind("<Button-1>", lambda e, url=link: webbrowser.open_new(url))
            else:
                lbl = ctk.CTkLabel(self, text=name, font=("微軟正黑體",14))
            lbl.pack(anchor="w", padx=40, pady=2)

# ========================
# Main GUI
# ========================
def main():
    win=ctk.CTk()
    win.title("Minecraft 伺服器管理工具 - 完整版")
    win.geometry("750x650")
    tabview=ctk.CTkTabview(win)
    tabview.pack(expand=True,fill="both",padx=20,pady=20)
    tabview.add("核心")
    tabview.add("備份")
    tabview.add("設定")
    tabview.add("關於我們")

    core_tab=CorePage(tabview.tab("核心")); core_tab.pack(fill="both",expand=True)
    backup_tab=BackupPage(tabview.tab("備份")); backup_tab.pack(fill="both",expand=True)
    setting_tab=SettingsPage(tabview.tab("設定")); setting_tab.pack(fill="both",expand=True)
    about_tab=AboutPage(tabview.tab("關於我們")); about_tab.pack(fill="both",expand=True)

    win.mainloop()

if __name__=="__main__":
    main()