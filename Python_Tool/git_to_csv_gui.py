import git
# from openpyxl import Workbook # 不再需要 openpyxl
import csv # 匯入 csv 模組
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# 修改 generate_git_log_excel 為 generate_git_log_csv
def generate_git_log_csv(repo_path, output_csv_file, num_commits=None):
    """
    生成一份 CSV 檔案，其中包含 Git 倉儲的提交歷史。

    參數：
        repo_path (str): Git 倉儲的路徑。
        output_csv_file (str): 輸出的 CSV 檔案名稱 (例如：git_log.csv)。
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

    headers = ["姓名", "SHA值", "commit內容"]
    rows = [] # 用來存放所有commit資料

    try:
        if num_commits and num_commits > 0:
            commits_iterator = repo.iter_commits(max_count=num_commits)
        else:
            commits_iterator = repo.iter_commits()

        for commit in commits_iterator:
            author_name = commit.author.name
            sha = commit.hexsha
            commit_message = commit.message.strip().replace('\n', ' ') # 將換行符替換為空格，避免CSV分行問題
            rows.append([author_name, sha, commit_message])

    except Exception as e:
        messagebox.showerror("錯誤", f"處理 Git 提交時發生錯誤：{e}")
        return False

    try:
        # 寫入 CSV 檔案
        with open(output_csv_file, 'w', newline='', encoding='utf-8-sig') as csvfile: # utf-8-sig 確保Excel正確讀取中文
            writer = csv.writer(csvfile)
            writer.writerow(headers) # 寫入表頭
            writer.writerows(rows)   # 寫入所有資料行
        return True
    except Exception as e:
        messagebox.showerror("錯誤", f"儲存 CSV 檔案 '{output_csv_file}' 時發生錯誤：{e}")
        return False

class GitLogGUI:
    def __init__(self, master):
        self.master = master
        master.title("Git Log to CSV/Excel") # 標題可以調整
        master.geometry("550x300")

        style = ttk.Style()
        style.configure("TLabel", padding=5, font=('Arial', 10))
        style.configure("TButton", padding=5, font=('Arial', 10))
        style.configure("TEntry", padding=5, font=('Arial', 10))

        self.repo_path_label = ttk.Label(master, text="Git 倉儲路徑:")
        self.repo_path_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.repo_path_var = tk.StringVar()
        self.repo_path_entry = ttk.Entry(master, textvariable=self.repo_path_var, width=40)
        self.repo_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.browse_repo_button = ttk.Button(master, text="瀏覽...", command=self.browse_repo)
        self.browse_repo_button.grid(row=0, column=2, padx=10, pady=10)

        # --- 輸出檔案 ---
        self.output_file_label = ttk.Label(master, text="輸出檔案:") # 修改標籤
        self.output_file_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.output_file_var = tk.StringVar(value="git_commit_history.csv") # 預設檔名為 .csv
        self.output_file_entry = ttk.Entry(master, textvariable=self.output_file_var, width=40)
        self.output_file_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.save_as_button = ttk.Button(master, text="另存為...", command=self.save_as_output) # 修改儲存函式
        self.save_as_button.grid(row=1, column=2, padx=10, pady=10)

        self.num_commits_label = ttk.Label(master, text="要擷取的筆數 (0 為全部):")
        self.num_commits_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.num_commits_var = tk.StringVar(value="0")
        self.num_commits_entry = ttk.Entry(master, textvariable=self.num_commits_var, width=10)
        self.num_commits_entry.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        self.generate_button = ttk.Button(master, text="生成檔案", command=self.generate) # 修改按鈕文字
        self.generate_button.grid(row=3, column=0, columnspan=3, padx=10, pady=20)

        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(master, textvariable=self.status_var, font=('Arial', 10, 'italic'))
        self.status_label.grid(row=4, column=0, columnspan=3, padx=10, pady=5, sticky="w")

        master.grid_columnconfigure(1, weight=1)

    def browse_repo(self):
        path = filedialog.askdirectory(title="選擇 Git 倉儲資料夾")
        if path:
            self.repo_path_var.set(path)
            self.status_var.set(f"已選擇倉儲路徑: {path}")

    def save_as_output(self): # 修改函式以支援 CSV
        path = filedialog.asksaveasfilename(
            title="儲存檔案",
            defaultextension=".csv", # 預設副檔名為 .csv
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("All files", "*.*")] # 同時提供CSV和Excel選項
        )
        if path:
            self.output_file_var.set(path)
            self.status_var.set(f"檔案將儲存至: {path}")


    def generate(self):
        repo_path = self.repo_path_var.get()
        output_file = self.output_file_var.get()
        num_commits_str = self.num_commits_var.get()

        if not repo_path:
            messagebox.showwarning("輸入錯誤", "請選擇 Git 倉儲路徑。")
            return
        if not output_file:
            messagebox.showwarning("輸入錯誤", "請指定輸出的檔案名稱或路徑。")
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
        self.master.update_idletasks()

        # 根據副檔名決定使用哪個函式
        file_extension = os.path.splitext(output_file)[1].lower()
        success = False

        if file_extension == ".csv":
            success = generate_git_log_csv(repo_path, output_file, num_commits if num_commits > 0 else None)
        elif file_extension == ".xlsx":
            # 如果仍想支援xlsx，需要確保 openpyxl 已安裝且 generate_git_log_excel 函式存在
            # 這裡我們假設您會將原始的 generate_git_log_excel 函式也保留在某處
            # 或者提示使用者安裝 openpyxl
            try:
                from openpyxl import Workbook # 僅在此處嘗試導入
                # 你需要將原始的 generate_git_log_excel 函式複製回程式中
                # 假設它叫做 generate_git_log_excel_original
                # success = generate_git_log_excel_original(repo_path, output_file, num_commits if num_commits > 0 else None)
                messagebox.showinfo("提示", "若要輸出為 .xlsx，請確保您的環境中已安裝 openpyxl 函式庫，\n並在程式碼中包含對應的處理邏輯。\n此範例主要展示CSV輸出。")
                # 為了範例的簡潔，這裡不直接執行xlsx的生成，你可以複製回原始的xlsx生成函式
                self.status_var.set("XLSX 生成未在此範例中啟用。")
                return # 暫時不處理xlsx以保持範例的csv焦點
            except ImportError:
                messagebox.showerror("函式庫缺失", "偵測到輸出為 .xlsx 但 openpyxl 函式庫未安裝或未在程式碼中處理。")
                self.status_var.set("openpyxl 未安裝。")
                return
        else:
            messagebox.showwarning("格式錯誤", "不支援的檔案格式。請選擇 .csv 或 .xlsx。")
            self.status_var.set("不支援的檔案格式。")
            return


        if success:
            self.status_var.set(f"成功生成檔案: '{os.path.abspath(output_file)}'")
            messagebox.showinfo("成功", f"檔案已成功生成！\n儲存於: {os.path.abspath(output_file)}")
        else:
            self.status_var.set("生成失敗，請檢查錯誤訊息。")

if __name__ == "__main__":
    # --- 安裝必要的函式庫 ---
    # 若選擇輸出CSV，則 openpyxl 非必需
    # pip install GitPython
    # pip install openpyxl (如果仍想保留XLSX輸出選項)

    root = tk.Tk()
    gui = GitLogGUI(root)
    root.mainloop()