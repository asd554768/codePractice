import git
from openpyxl import Workbook
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

def generate_git_log_excel(repo_path, output_excel_file, num_commits=None):
    """
    生成一份 Excel 檔案，其中包含 Git 倉儲的提交歷史。

    參數：
        repo_path (str): Git 倉儲的路徑。
        output_excel_file (str): 輸出的 Excel 檔案名稱 (例如：git_log.xlsx)。
        num_commits (int, optional): 要擷取的提交筆數。如果為 None 或 0，則擷取所有提交。
    """
    try:
        repo = git.Repo(repo_path)
    except git.exc.InvalidGitRepositoryError:
        messagebox.showerror("錯誤", f"指定的路徑 '{repo_path}' 不是一個有效的 Git 倉儲。")
        return False
    except git.exc.NoSuchPathError:
        messagebox.showerror("錯誤", f"指定的路徑 '{repo_path}' 不存在。")
        return False
    except Exception as e:
        messagebox.showerror("錯誤", f"讀取倉儲時發生未知錯誤：{e}")
        return False

    wb = Workbook()
    ws = wb.active
    ws.title = "Git Log"

    headers = ["姓名", "SHA值", "commit內容"]
    ws.append(headers)

    try:
        if num_commits and num_commits > 0:
            commits_iterator = repo.iter_commits(max_count=num_commits)
        else:
            commits_iterator = repo.iter_commits() # 獲取所有 commits

        for commit in commits_iterator:
            author_name = commit.author.name
            sha = commit.hexsha
            commit_message = commit.message.strip()
            ws.append([author_name, sha, commit_message])

    except Exception as e:
        messagebox.showerror("錯誤", f"處理 Git 提交時發生錯誤：{e}")
        return False

    try:
        wb.save(output_excel_file)
        return True
    except Exception as e:
        messagebox.showerror("錯誤", f"儲存 Excel 檔案 '{output_excel_file}' 時發生錯誤：{e}")
        return False

class GitLogGUI:
    def __init__(self, master):
        self.master = master
        master.title("Git Log to Excel")
        master.geometry("550x300") # 調整視窗大小

        # --- 設定樣式 ---
        style = ttk.Style()
        style.configure("TLabel", padding=5, font=('Arial', 10))
        style.configure("TButton", padding=5, font=('Arial', 10))
        style.configure("TEntry", padding=5, font=('Arial', 10))

        # --- Git 倉儲路徑 ---
        self.repo_path_label = ttk.Label(master, text="Git 倉儲路徑:")
        self.repo_path_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.repo_path_var = tk.StringVar()
        self.repo_path_entry = ttk.Entry(master, textvariable=self.repo_path_var, width=40)
        self.repo_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.browse_repo_button = ttk.Button(master, text="瀏覽...", command=self.browse_repo)
        self.browse_repo_button.grid(row=0, column=2, padx=10, pady=10)

        # --- 輸出 Excel 檔案 ---
        self.excel_file_label = ttk.Label(master, text="輸出 Excel 檔案:")
        self.excel_file_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        self.excel_file_var = tk.StringVar(value="git_commit_history.xlsx") # 預設檔名
        self.excel_file_entry = ttk.Entry(master, textvariable=self.excel_file_var, width=40)
        self.excel_file_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.save_as_button = ttk.Button(master, text="另存為...", command=self.save_as_excel)
        self.save_as_button.grid(row=1, column=2, padx=10, pady=10)

        # --- 要擷取的筆數 ---
        self.num_commits_label = ttk.Label(master, text="要擷取的筆數 (0 為全部):")
        self.num_commits_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")

        self.num_commits_var = tk.StringVar(value="0") # 預設為0 (全部)
        self.num_commits_entry = ttk.Entry(master, textvariable=self.num_commits_var, width=10)
        self.num_commits_entry.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        # --- 生成按鈕 ---
        self.generate_button = ttk.Button(master, text="生成 Excel", command=self.generate)
        self.generate_button.grid(row=3, column=0, columnspan=3, padx=10, pady=20)

        # --- 狀態標籤 ---
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(master, textvariable=self.status_var, font=('Arial', 10, 'italic'))
        self.status_label.grid(row=4, column=0, columnspan=3, padx=10, pady=5, sticky="w")

        # --- 設定欄位權重讓元件可以隨視窗縮放 ---
        master.grid_columnconfigure(1, weight=1)

    def browse_repo(self):
        path = filedialog.askdirectory(title="選擇 Git 倉儲資料夾")
        if path:
            self.repo_path_var.set(path)
            self.status_var.set(f"已選擇倉儲路徑: {path}")

    def save_as_excel(self):
        path = filedialog.asksaveasfilename(
            title="儲存 Excel 檔案",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if path:
            self.excel_file_var.set(path)
            self.status_var.set(f"Excel 將儲存至: {path}")


    def generate(self):
        repo_path = self.repo_path_var.get()
        excel_file = self.excel_file_var.get()
        num_commits_str = self.num_commits_var.get()

        if not repo_path:
            messagebox.showwarning("輸入錯誤", "請選擇 Git 倉儲路徑。")
            return

        if not excel_file:
            messagebox.showwarning("輸入錯誤", "請指定輸出的 Excel 檔案名稱或路徑。")
            return

        try:
            num_commits = int(num_commits_str)
            if num_commits < 0:
                messagebox.showwarning("輸入錯誤", "擷取筆數不能為負數。")
                return
        except ValueError:
            messagebox.showwarning("輸入錯誤", "擷取筆數必須是一個有效的數字。")
            return

        self.status_var.set("處理中，請稍候...")
        self.master.update_idletasks() # 更新UI顯示

        if generate_git_log_excel(repo_path, excel_file, num_commits if num_commits > 0 else None):
            self.status_var.set(f"成功生成 Excel 檔案: '{os.path.abspath(excel_file)}'")
            messagebox.showinfo("成功", f"Excel 檔案已成功生成！\n儲存於: {os.path.abspath(excel_file)}")
        else:
            self.status_var.set("生成失敗，請檢查錯誤訊息。")
            # 錯誤訊息已由 generate_git_log_excel 函式中的 messagebox 顯示

if __name__ == "__main__":
    # --- 安裝必要的函式庫 ---
    # 請確認你已經安裝了 GitPython 和 openpyxl
    # pip install GitPython openpyxl

    root = tk.Tk()
    gui = GitLogGUI(root)
    root.mainloop()