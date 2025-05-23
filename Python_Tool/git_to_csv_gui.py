import git
import csv
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta # <--- 匯入 datetime 和 timedelta

# generate_git_log_csv 函式修改
def generate_git_log_csv(repo_path, output_csv_file, num_commits=None, start_date_str=None, end_date_str=None):
    """
    生成一份 CSV 檔案，其中包含 Git 倉儲的提交歷史。
    最舊的 commit 在最上面。

    參數：
        repo_path (str): Git 倉儲的路徑。
        output_csv_file (str): 輸出的 CSV 檔案名稱。
        num_commits (int, optional): 要擷取的提交筆數。如果為 None 或 0，則擷取所有符合條件的提交。
        start_date_str (str, optional): 開始日期字串 (YYYY-MM-DD)。
        end_date_str (str, optional): 結束日期字串 (YYYY-MM-DD)。
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
        messagebox.showerror("錯誤", f"讀取倉儲 '{repo_path}' 時發生未知錯誤：{e}")
        return False

    iter_kwargs = {}
    try:
        if start_date_str:
            # 解析開始日期
            dt_start = datetime.strptime(start_date_str, "%Y-%m-%d")
            iter_kwargs['since'] = dt_start
        if end_date_str:
            # 解析結束日期，並將 'until' 設為結束日期的後一天，以包含結束日期當天的commit
            dt_end = datetime.strptime(end_date_str, "%Y-%m-%d")
            iter_kwargs['until'] = dt_end + timedelta(days=1)

        # 檢查日期邏輯
        if 'since' in iter_kwargs and 'until' in iter_kwargs and iter_kwargs['since'] >= iter_kwargs['until']:
            messagebox.showwarning("日期錯誤", "開始日期必須在結束日期之前。")
            return False

    except ValueError:
        messagebox.showerror("日期格式錯誤", "日期格式必須為 YYYY-MM-DD。")
        return False
    except Exception as e:
        messagebox.showerror("日期處理錯誤", f"處理日期時發生錯誤: {e}")
        return False

    headers = ["姓名", "SHA值", "commit內容"]
    all_commit_details = []

    try:
        # 1. 獲取所有符合日期篩選的 commits (此時不使用 num_commits 限制)
        # iter_commits 預設從新到舊
        commits_iterator = repo.iter_commits(**iter_kwargs)

        for commit in commits_iterator:
            author_name = commit.author.name
            sha = commit.hexsha
            commit_message = commit.message.strip().replace('\n', ' ') # 避免CSV分行問題
            all_commit_details.append([author_name, sha, commit_message])

        # 2. 反轉列表，使得最舊的 commit 在最前面
        all_commit_details.reverse()

        # 3. 如果指定了 num_commits，則從最舊的開始取 N 筆
        if num_commits and num_commits > 0:
            final_commits_to_write = all_commit_details[:num_commits]
        else:
            final_commits_to_write = all_commit_details

        if not final_commits_to_write:
            messagebox.showinfo("提示", "在指定的日期範圍內沒有找到任何 commit。")
            # 仍會產生一個只有表頭的空檔案
            # return True # 或者可以選擇不產生檔案並返回 False

    except Exception as e:
        messagebox.showerror("錯誤", f"處理 Git 提交時發生錯誤：{e}")
        return False

    try:
        with open(output_csv_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            writer.writerows(final_commits_to_write)
        return True
    except Exception as e:
        messagebox.showerror("錯誤", f"儲存 CSV 檔案 '{output_csv_file}' 時發生錯誤：{e}")
        return False

class GitLogGUI:
    def __init__(self, master):
        self.master = master
        master.title("Git Log to CSV")
        master.geometry("600x400") # 調整視窗大小以容納新欄位

        style = ttk.Style()
        style.configure("TLabel", padding=5, font=('Arial', 10))
        style.configure("TButton", padding=5, font=('Arial', 10))
        style.configure("TEntry", padding=5, font=('Arial', 10))

        # --- Git 倉儲路徑 ---
        self.repo_path_label = ttk.Label(master, text="Git 倉儲路徑:")
        self.repo_path_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.repo_path_var = tk.StringVar()
        self.repo_path_entry = ttk.Entry(master, textvariable=self.repo_path_var, width=45)
        self.repo_path_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        self.browse_repo_button = ttk.Button(master, text="瀏覽...", command=self.browse_repo)
        self.browse_repo_button.grid(row=0, column=3, padx=10, pady=5)

        # --- 輸出檔案 ---
        self.output_file_label = ttk.Label(master, text="輸出 CSV 檔案:")
        self.output_file_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.output_file_var = tk.StringVar(value="git_commit_history.csv")
        self.output_file_entry = ttk.Entry(master, textvariable=self.output_file_var, width=45)
        self.output_file_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        self.save_as_button = ttk.Button(master, text="另存為...", command=self.save_as_output)
        self.save_as_button.grid(row=1, column=3, padx=10, pady=5)

        # --- 開始日期 ---
        self.start_date_label = ttk.Label(master, text="開始日期 (YYYY-MM-DD):")
        self.start_date_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.start_date_var = tk.StringVar()
        self.start_date_entry = ttk.Entry(master, textvariable=self.start_date_var, width=20)
        self.start_date_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        # --- 結束日期 ---
        self.end_date_label = ttk.Label(master, text="結束日期 (YYYY-MM-DD):")
        self.end_date_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.end_date_var = tk.StringVar()
        self.end_date_entry = ttk.Entry(master, textvariable=self.end_date_var, width=20)
        self.end_date_entry.grid(row=3, column=1, padx=10, pady=5, sticky="w")

        # --- 要擷取的筆數 ---
        self.num_commits_label = ttk.Label(master, text="擷取筆數 (0或空=全部):")
        self.num_commits_label.grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.num_commits_var = tk.StringVar(value="0")
        self.num_commits_entry = ttk.Entry(master, textvariable=self.num_commits_var, width=10)
        self.num_commits_entry.grid(row=4, column=1, padx=10, pady=5, sticky="w")

        # --- 生成按鈕 ---
        self.generate_button = ttk.Button(master, text="生成 CSV", command=self.generate)
        self.generate_button.grid(row=5, column=0, columnspan=4, padx=10, pady=15)

        # --- 狀態標籤 ---
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(master, textvariable=self.status_var, font=('Arial', 10, 'italic'))
        self.status_label.grid(row=6, column=0, columnspan=4, padx=10, pady=5, sticky="w")

        master.grid_columnconfigure(1, weight=1) # 讓中間欄位隨視窗縮放

    def browse_repo(self):
        path = filedialog.askdirectory(title="選擇 Git 倉儲資料夾")
        if path:
            self.repo_path_var.set(path)
            self.status_var.set(f"已選擇倉儲: {path}")

    def save_as_output(self):
        path = filedialog.asksaveasfilename(
            title="儲存 CSV 檔案",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            self.output_file_var.set(path)
            self.status_var.set(f"CSV 將儲存至: {path}")

    def generate(self):
        repo_path = self.repo_path_var.get()
        output_file = self.output_file_var.get()
        num_commits_str = self.num_commits_var.get()
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not repo_path:
            messagebox.showwarning("輸入錯誤", "請選擇 Git 倉儲路徑。")
            return
        if not output_file:
            messagebox.showwarning("輸入錯誤", "請指定輸出的 CSV 檔案名稱或路徑。")
            return

        num_commits = 0
        if num_commits_str.strip(): # 如果使用者有輸入
            try:
                num_commits = int(num_commits_str)
                if num_commits < 0:
                    messagebox.showwarning("輸入錯誤", "擷取筆數不能為負數。")
                    return
            except ValueError:
                messagebox.showwarning("輸入錯誤", "擷取筆數必須是一個有效的數字。")
                return

        # 日期格式驗證 (簡易)
        valid_dates = True
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("日期格式錯誤", "開始日期格式必須為 YYYY-MM-DD。")
                valid_dates = False
        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("日期格式錯誤", "結束日期格式必須為 YYYY-MM-DD。")
                valid_dates = False
        
        if not valid_dates:
            return

        # 檢查開始日期是否在結束日期之前 (僅當兩者都提供時)
        if start_date and end_date:
            try:
                dt_start_check = datetime.strptime(start_date, "%Y-%m-%d")
                dt_end_check = datetime.strptime(end_date, "%Y-%m-%d")
                if dt_start_check > dt_end_check:
                    messagebox.showwarning("日期錯誤", "開始日期不能晚於結束日期。")
                    return
            except ValueError: # 已在上一步驟處理，但以防萬一
                return


        self.status_var.set("處理中，請稍候...")
        self.master.update_idletasks()

        success = generate_git_log_csv(
            repo_path,
            output_file,
            num_commits if num_commits > 0 else None, # 傳遞 None 如果筆數為0或空
            start_date if start_date else None,
            end_date if end_date else None
        )

        if success:
            self.status_var.set(f"成功生成 CSV 檔案: '{os.path.abspath(output_file)}'")
            messagebox.showinfo("成功", f"CSV 檔案已成功生成！\n儲存於: {os.path.abspath(output_file)}")
        else:
            # 錯誤訊息已由 generate_git_log_csv 中的 messagebox 顯示
            self.status_var.set("生成失敗或過程中出現問題。")


if __name__ == "__main__":
    root = tk.Tk()
    gui = GitLogGUI(root)
    root.mainloop()