import git
import csv
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta, date # 匯入 date, datetime, timedelta

def generate_git_log_csv(repo_path, output_csv_file, num_commits=None, start_date_str=None, end_date_str=None):
    """
    生成一份 CSV 檔案，其中包含 Git 倉儲的提交歷史。
    最舊的 commit 在最上面。

    參數：
        repo_path (str): Git 倉儲的路徑。
        output_csv_file (str): 輸出的 CSV 檔案名稱。
        num_commits (int, optional): 要擷取的提交筆數。如果為 None，則擷取所有符合條件的提交。
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
            dt_start = datetime.strptime(start_date_str, "%Y-%m-%d")
            iter_kwargs['since'] = dt_start
        if end_date_str:
            dt_end = datetime.strptime(end_date_str, "%Y-%m-%d")
            iter_kwargs['until'] = dt_end + timedelta(days=1)
    except ValueError:
        messagebox.showerror("日期格式錯誤", "內部日期處理錯誤，格式應為YYYY-MM-DD。")
        return False
    except Exception as e:
        messagebox.showerror("日期處理錯誤", f"處理日期時發生錯誤: {e}")
        return False


    headers = ["姓名", "SHA值", "commit內容"]
    all_commit_details = []

    try:
        commits_iterator = repo.iter_commits(**iter_kwargs)
        for commit in commits_iterator:
            author_name = commit.author.name
            sha = commit.hexsha
            commit_message = commit.message.strip().replace('\n', ' ')
            all_commit_details.append([author_name, sha, commit_message])

        all_commit_details.reverse() 

        if num_commits and num_commits > 0:
            final_commits_to_write = all_commit_details[:num_commits]
        else:
            final_commits_to_write = all_commit_details

        if not final_commits_to_write and (start_date_str or end_date_str):
            messagebox.showinfo("提示", "在指定的日期範圍內沒有找到任何 commit。")

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
        master.title("Git 提交紀錄轉 CSV 工具")
        master.geometry("600x400")

        style = ttk.Style()
        style.configure("TLabel", padding=5, font=('Arial', 10))
        style.configure("TButton", padding=5, font=('Arial', 10))
        style.configure("TEntry", padding=5, font=('Arial', 10))

        # --- Git 倉儲路徑 ---
        self.repo_path_label = ttk.Label(master, text="Git 倉儲路徑:")
        self.repo_path_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.repo_path_var = tk.StringVar()
        # 當倉儲路徑改變時，嘗試更新預設檔名
        self.repo_path_var.trace_add("write", lambda *args: self.update_default_output_filename())
        self.repo_path_entry = ttk.Entry(master, textvariable=self.repo_path_var, width=45)
        self.repo_path_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        self.browse_repo_button = ttk.Button(master, text="瀏覽...", command=self.browse_repo)
        self.browse_repo_button.grid(row=0, column=3, padx=10, pady=5)

        # --- 輸出檔案 ---
        self.output_file_label = ttk.Label(master, text="輸出 CSV 檔案:")
        self.output_file_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        
        # 初始預設檔名（不含SHA，因為此時可能還未選擇倉儲）
        initial_today_str_for_filename = date.today().strftime("%Y%m%d")
        self.output_file_var = tk.StringVar(value=f"{initial_today_str_for_filename}_git_commit_history.csv")
        
        self.output_file_entry = ttk.Entry(master, textvariable=self.output_file_var, width=45)
        self.output_file_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        self.save_as_button = ttk.Button(master, text="另存為...", command=self.save_as_output)
        self.save_as_button.grid(row=1, column=3, padx=10, pady=5)

        # --- 設定今日日期為預設值 ---
        today_str_for_date_fields = date.today().strftime("%Y-%m-%d")

        # --- 開始日期 ---
        self.start_date_label = ttk.Label(master, text="開始日期 (YYYY-MM-DD):")
        self.start_date_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.start_date_var = tk.StringVar(value=today_str_for_date_fields)
        self.start_date_entry = ttk.Entry(master, textvariable=self.start_date_var, width=20)
        self.start_date_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        # --- 結束日期 ---
        self.end_date_label = ttk.Label(master, text="結束日期 (YYYY-MM-DD):")
        self.end_date_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.end_date_var = tk.StringVar(value=today_str_for_date_fields)
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

        master.grid_columnconfigure(1, weight=1)

    def update_default_output_filename(self):
        """當倉儲路徑改變時，更新預設的輸出檔名。"""
        repo_path = self.repo_path_var.get()
        today_str_filename = date.today().strftime("%Y%m%d")
        
        if not repo_path:
            # 如果路徑被清空，恢復為僅包含日期的預設檔名
            self.output_file_var.set(f"{today_str_filename}_git_commit_history.csv")
            return

        try:
            repo = git.Repo(repo_path)
            latest_commit = None
            try:
                # 獲取最新的一筆 commit
                latest_commit = next(repo.iter_commits(max_count=1))
            except StopIteration: # 倉儲中沒有 commit
                pass

            if latest_commit:
                latest_sha_short = latest_commit.hexsha[:7] # 取 SHA 前7碼
                default_filename = f"{today_str_filename}_{latest_sha_short}_git_commit_history.csv"
            else: # 倉儲有效但沒有 commit
                default_filename = f"{today_str_filename}_no_commits_history.csv"
            
            self.output_file_var.set(default_filename)

        except (git.exc.InvalidGitRepositoryError, git.exc.NoSuchPathError):
            # 如果路徑無效或不是 Git 倉儲，恢復為僅包含日期的預設檔名
            self.output_file_var.set(f"{today_str_filename}_git_commit_history.csv")
        except Exception:
            # 其他未知錯誤，也恢復為基本預設檔名
            self.output_file_var.set(f"{today_str_filename}_git_commit_history.csv")
            # 可以選擇性地記錄錯誤 self.status_var.set("更新預設檔名時發生錯誤")


    def browse_repo(self):
        path = filedialog.askdirectory(title="選擇 Git 倉儲資料夾")
        if path:
            self.repo_path_var.set(path) # 設定路徑，這會觸發 trace_add 中的 update_default_output_filename
            self.status_var.set(f"已選擇倉儲: {path}")
            # self.update_default_output_filename() # 現在由 trace_add 處理

    def save_as_output(self):
        # 建議在開啟另存為對話框前，先確保檔名是最新的
        self.update_default_output_filename() # 確保使用最新的SHA (如果使用者手動輸入路徑)
        
        path = filedialog.asksaveasfilename(
            title="儲存 CSV 檔案",
            initialfile=self.output_file_var.get(), # 使用目前 output_file_var 中的值作為建議檔名
            defaultextension=".csv",
            filetypes=[("CSV 檔案", "*.csv"), ("所有檔案", "*.*")]
        )
        if path:
            self.output_file_var.set(path) # 使用者選擇的最終路徑和檔名
            self.status_var.set(f"CSV 將儲存至: {path}")

    def generate(self):
        repo_path = self.repo_path_var.get()
        output_file = self.output_file_var.get()
        num_commits_str = self.num_commits_var.get()
        start_date_input = self.start_date_var.get().strip()
        end_date_input = self.end_date_var.get().strip()

        if not repo_path:
            messagebox.showwarning("輸入錯誤", "請選擇 Git 倉儲路徑。")
            return
        if not output_file:
            messagebox.showwarning("輸入錯誤", "請指定輸出的 CSV 檔案名稱或路徑。")
            return

        num_commits = 0
        if num_commits_str:
            try:
                num_commits = int(num_commits_str)
                if num_commits < 0:
                    messagebox.showwarning("輸入錯誤", "擷取筆數不能為負數。")
                    return
            except ValueError:
                messagebox.showwarning("輸入錯誤", "擷取筆數必須是一個有效的數字。")
                return

        if start_date_input:
            try:
                datetime.strptime(start_date_input, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("日期格式錯誤", "開始日期格式必須為YYYY-MM-DD。")
                return
        
        if end_date_input:
            try:
                datetime.strptime(end_date_input, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("日期格式錯誤", "結束日期格式必須為YYYY-MM-DD。")
                return
        
        if start_date_input and end_date_input:
            try:
                dt_start_check = datetime.strptime(start_date_input, "%Y-%m-%d").date()
                dt_end_check = datetime.strptime(end_date_input, "%Y-%m-%d").date()
                if dt_start_check > dt_end_check:
                    messagebox.showwarning("日期錯誤", "開始日期不能晚於結束日期。")
                    return
            except ValueError:
                return


        self.status_var.set("處理中，請稍候...")
        self.master.update_idletasks()

        success = generate_git_log_csv(
            repo_path,
            output_file,
            num_commits if num_commits > 0 else None,
            start_date_input if start_date_input else None,
            end_date_input if end_date_input else None
        )

        if success:
            self.status_var.set(f"成功生成 CSV 檔案: '{os.path.abspath(output_file)}'")
            messagebox.showinfo("成功", f"CSV 檔案已成功生成！\n儲存於: {os.path.abspath(output_file)}")
        else:
            self.status_var.set("生成失敗或過程中出現問題。")


if __name__ == "__main__":
    root = tk.Tk()
    gui = GitLogGUI(root)
    root.mainloop()
