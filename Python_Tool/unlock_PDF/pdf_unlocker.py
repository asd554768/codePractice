import os
import json
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
import pikepdf

# 設定 UI 主題與顏色
ctk.set_appearance_mode("System")  # 根據系統自動切換深色/淺色
ctk.set_default_color_theme("blue")

CONFIG_FILE = "config.json"

class PDFUnlockerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PDF 批次自動解密工具")
        self.geometry("550 x 450")
        self.resizable(False, False)

        # 變數綁定
        self.folder_path = ctk.StringVar()
        self.password = ctk.StringVar()
        self.save_default = ctk.BooleanVar(value=True)
        
        # 載入預設密碼
        self.load_config()

        # --- UI 佈局 ---
        
        # 標題
        self.title_label = ctk.CTkLabel(self, text="PDF 批次解密工具", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(20, 10))

        # 資料夾選擇區塊
        self.frame_folder = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_folder.pack(fill="x", padx=20, pady=10)
        
        self.folder_entry = ctk.CTkEntry(self.frame_folder, textvariable=self.folder_path, placeholder_text="請選擇包含加密 PDF 的資料夾...", width=380)
        self.folder_entry.pack(side="left", padx=(0, 10))
        
        self.btn_browse = ctk.CTkButton(self.frame_folder, text="瀏覽...", width=80, command=self.browse_folder)
        self.btn_browse.pack(side="left")

        # 密碼輸入區塊
        self.frame_pwd = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_pwd.pack(fill="x", padx=20, pady=10)
        
        self.pwd_entry = ctk.CTkEntry(self.frame_pwd, textvariable=self.password, placeholder_text="請輸入 PDF 密碼", show="*", width=380)
        self.pwd_entry.pack(side="left", padx=(0, 10))
        
        # 顯示/隱藏密碼按鈕
        self.btn_toggle_pwd = ctk.CTkButton(self.frame_pwd, text="顯示", width=80, fg_color="gray", hover_color="darkgray", command=self.toggle_password)
        self.btn_toggle_pwd.pack(side="left")

        # 預設密碼選項
        self.chk_save_default = ctk.CTkCheckBox(self, text="記住此密碼作為預設", variable=self.save_default)
        self.chk_save_default.pack(anchor="w", padx=20, pady=5)

        # 執行按鈕
        self.btn_start = ctk.CTkButton(self, text="開始解密", height=40, font=ctk.CTkFont(size=16, weight="bold"), command=self.start_decryption_thread)
        self.btn_start.pack(fill="x", padx=20, pady=(15, 10))

        # 狀態日誌區 (Log)
        self.log_box = ctk.CTkTextbox(self, height=120, state="disabled")
        self.log_box.pack(fill="both", padx=20, pady=(0, 20))

    def load_config(self):
        """讀取預設密碼設定檔"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if "default_password" in config:
                        self.password.set(config["default_password"])
            except Exception:
                pass

    def save_config(self):
        """儲存密碼到設定檔"""
        if self.save_default.get():
            config = {"default_password": self.password.get()}
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f)

    def browse_folder(self):
        """開啟資料夾選擇視窗"""
        folder = filedialog.askdirectory(title="選擇 PDF 資料夾")
        if folder:
            self.folder_path.set(folder)

    def toggle_password(self):
        """切換密碼顯示/隱藏狀態"""
        if self.pwd_entry.cget("show") == "*":
            self.pwd_entry.configure(show="")
            self.btn_toggle_pwd.configure(text="隱藏")
        else:
            self.pwd_entry.configure(show="*")
            self.btn_toggle_pwd.configure(text="顯示")

    def log_message(self, message):
        """安全地在 UI 寫入 Log 訊息"""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")  # 自動捲動到底部
        self.log_box.configure(state="disabled")

    def start_decryption_thread(self):
        """使用獨立執行緒進行解密，避免 GUI 卡頓"""
        target_folder = self.folder_path.get()
        pwd = self.password.get()

        if not target_folder or not os.path.isdir(target_folder):
            messagebox.showwarning("警告", "請先選擇有效的資料夾！")
            return
        if not pwd:
            messagebox.showwarning("警告", "請輸入密碼！")
            return

        # 鎖定按鈕，防止重複點擊
        self.btn_start.configure(state="disabled", text="處理中...")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end") # 清空日誌
        self.log_box.configure(state="disabled")
        
        self.save_config() # 儲存預設密碼

        # 啟動背景執行緒
        threading.Thread(target=self.process_pdfs, args=(target_folder, pwd), daemon=True).start()

    def process_pdfs(self, target_folder, pwd):
        """核心解密邏輯"""
        output_folder = os.path.join(target_folder, "Decrypted_PDFs")
        
        # 尋找所有 PDF 檔案
        pdf_files = [f for f in os.listdir(target_folder) if f.lower().endswith(".pdf")]
        
        if not pdf_files:
            self.log_message("❌ 在選定的資料夾中找不到任何 PDF 檔案。")
            self.after(0, self.reset_button)
            return

        # 建立輸出資料夾
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        success_count = 0
        fail_count = 0

        self.log_message(f"🔍 找到 {len(pdf_files)} 個 PDF 檔案，開始處理...\n" + "-"*30)

        for filename in pdf_files:
            file_path = os.path.join(target_folder, filename)
            output_path = os.path.join(output_folder, filename)

            try:
                # 使用 pikepdf 開啟並解密
                with pikepdf.open(file_path, password=pwd) as pdf:
                    pdf.save(output_path)
                
                self.log_message(f"✅ 成功解密: {filename}")
                success_count += 1
            except pikepdf.PasswordError:
                self.log_message(f"❌ 密碼錯誤: {filename}")
                fail_count += 1
            except Exception as e:
                self.log_message(f"⚠️ 發生未知的錯誤 ({filename}): {str(e)}")
                fail_count += 1

        self.log_message("-" * 30)
        self.log_message(f"🎉 處理完成！成功: {success_count} 個, 失敗: {fail_count} 個。")
        self.log_message(f"📁 解密後的檔案已儲存於: {output_folder}")

        # 恢復按鈕狀態 (透過 tkinter 的 after 方法確保 Thread-safe)
        self.after(0, self.reset_button)

    def reset_button(self):
        """重置開始按鈕狀態"""
        self.btn_start.configure(state="normal", text="開始解密")

if __name__ == "__main__":
    app = PDFUnlockerApp()
    app.mainloop()