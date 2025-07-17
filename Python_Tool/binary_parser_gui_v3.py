import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import pandas as pd

class BinaryParserApp:
    def __init__(self, root):
        """
        初始化應用程式 GUI 介面
        """
        self.root = root
        self.root.title("二進位檔案解析工具 v2.3 (支援 CSV/Excel)")
        self.root.geometry("700x550")

        # 用於儲存解析結果的列表
        self.parsed_results = []

        # 修改變數名稱以反映其通用性
        self.rule_file_path = tk.StringVar()
        self.bin_path = tk.StringVar()

        # --- 介面框架 ---
        main_frame = tk.Frame(root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 檔案選擇區 (更新) ---
        file_frame = tk.LabelFrame(main_frame, text="檔案選擇", padx=10, pady=10)
        file_frame.pack(fill=tk.X, pady=5)

        # 更新按鈕文字與指令
        tk.Button(file_frame, text="1. 選擇規則檔 (Excel/CSV)", command=self.select_rule_file).grid(row=0, column=0, sticky=tk.W, pady=2)
        tk.Entry(file_frame, textvariable=self.rule_file_path, width=70, state='readonly').grid(row=0, column=1, sticky=tk.EW, padx=5)
        
        tk.Button(file_frame, text="2. 選擇 Binary 目標檔 (.bin)", command=self.select_bin_file).grid(row=1, column=0, sticky=tk.W, pady=2)
        tk.Entry(file_frame, textvariable=self.bin_path, width=70, state='readonly').grid(row=1, column=1, sticky=tk.EW, padx=5)
        
        # --- 執行按鈕 ---
        tk.Button(main_frame, text="開始解析 (Parse)", font=("Arial", 12, "bold"), bg="#007BFF", fg="white", command=self.parse_data).pack(fill=tk.X, pady=10)

        # --- 結果顯示區 ---
        result_frame = tk.LabelFrame(main_frame, text="解析結果", padx=10, pady=10)
        result_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- MODIFIED LAYOUT LOGIC ---
        # 先建立匯出按鈕，並將其固定在底部
        self.export_button = tk.Button(result_frame, text="匯出 Excel (Export)", state=tk.DISABLED, command=self.export_to_excel)
        # 將按鈕 pack 到視窗底部，並讓它水平填滿
        self.export_button.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

        # 接著建立文字顯示區，讓它填滿所有剩餘的空間
        self.result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, font=("Consolas", 11))
        # 將文字區 pack 到頂部，並讓它在水平和垂直方向都填滿且可擴展
        self.result_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # --- END OF MODIFICATION ---

        # --- 狀態列 ---
        self.status_bar = tk.Label(root, text="請先選擇檔案", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        file_frame.grid_columnconfigure(1, weight=1)

    def select_rule_file(self):
        """
        開啟檔案對話框以選擇規則檔案 (Excel 或 CSV)
        """
        path = filedialog.askopenfilename(
            title="選擇規則檔案 (Excel 或 CSV)",
            filetypes=[
                ("支援的檔案", "*.xlsx *.xls *.csv"),
                ("Excel 檔案", "*.xlsx *.xls"),
                ("CSV 檔案", "*.csv"),
                ("所有檔案", "*.*")
            ]
        )
        if path:
            self.rule_file_path.set(path)
            self.update_status(f"已選擇規則檔: {path}")

    def select_bin_file(self):
        """
        開啟檔案對話框以選擇 Binary 檔案
        """
        path = filedialog.askopenfilename(
            title="選擇要解析的 Binary 檔案",
            filetypes=[("Binary 檔案", "*.bin"), ("所有檔案", "*.*")]
        )
        if path:
            self.bin_path.set(path)
            self.update_status(f"已選擇 Binary 目標檔: {path}")

    def parse_data(self):
        """
        核心功能：讀取、解析、顯示結果，並將結果存入 self.parsed_results
        """
        self.export_button.config(state=tk.DISABLED)
        self.parsed_results = []
        self.result_text.delete('1.0', tk.END)

        rule_file = self.rule_file_path.get()
        bin_file = self.bin_path.get()

        if not rule_file or not bin_file:
            messagebox.showerror("錯誤", "請務必同時選擇規則檔案和 Binary 目標檔案。")
            return

        self.update_status("正在解析中...")

        try:
            # --- 根據副檔名讀取規則檔 ---
            if rule_file.lower().endswith('.csv'):
                df_rules = pd.read_csv(rule_file, header=None)
            else:
                df_rules = pd.read_excel(rule_file, header=None)
            
            # 檢查檔案是否為空
            if df_rules.empty:
                raise ValueError("規則檔案是空的。")

            # 將 NaN 值填充為空字串
            df_rules = df_rules.fillna('')
            
            # 根據讀取到的欄位數，穩健地命名
            num_cols = len(df_rules.columns)
            if num_cols < 3:
                raise ValueError("規則檔案必須至少有 '名稱', '起始', '長度' 三欄。")
            
            col_names = ['name', 'start', 'length', 'type']
            df_rules.columns = col_names[:num_cols]

            # 如果 'type' 欄不存在，則新增一個空欄
            if 'type' not in df_rules.columns:
                df_rules['type'] = ''
            
            with open(bin_file, 'rb') as f:
                binary_content = f.read()
            
            file_size = len(binary_content)
            
            header_info = f"--- Binary 檔案總大小: {file_size} bytes ---\n"
            self.result_text.insert(tk.END, header_info + "\n")

            for index, rule in df_rules.iterrows():
                name = rule['name']
                data_type = str(rule['type']).strip().lower()
                result_value = ""

                try:
                    start = int(rule['start'])
                    length = int(rule['length'])
                except (ValueError, TypeError):
                    result_value = "錯誤 - Excel/CSV 中的起始位置或長度不是有效的數字。"
                    self.parsed_results.append([name, result_value])
                    continue

                end = start + length

                if start >= file_size or end > file_size:
                    result_value = f"錯誤 - 定義的範圍 [{start}-{end}] 超出檔案總長度 {file_size}。"
                    self.parsed_results.append([name, result_value])
                    continue

                data_chunk = binary_content[start:end]
                
                if data_type == 'int':
                    parsed_int = int.from_bytes(data_chunk, byteorder='little')
                    hex_value = f"0x{parsed_int:X}"
                    result_value = f"{hex_value}"
                elif data_type == 'string':
                    try:
                        decoded_str = data_chunk.decode('ascii').rstrip('\x00')
                        result_value = f"{decoded_str}"
                    except UnicodeDecodeError:
                        hex_val = f"0x{data_chunk.hex().upper()}"
                        result_value = f"[無法解析為ASCII] (原始值: {hex_val})"
                else: 
                    hex_value = f"0x{data_chunk.hex().upper()}"
                    result_value = f"{hex_value}  (Raw Hex)"
                
                self.parsed_results.append([name, result_value])

            for name, value in self.parsed_results:
                is_error = '錯誤' in str(value)
                tag = 'error' if is_error else 'normal'
                self.result_text.insert(tk.END, f"{name}: {value}\n", tag)

            self.update_status("解析完成！")
            self.export_button.config(state=tk.NORMAL)

        except FileNotFoundError as e:
            messagebox.showerror("檔案未找到", f"找不到指定的檔案：\n{e}")
            self.update_status(f"錯誤：找不到檔案", is_error=True)
        except Exception as e:
            messagebox.showerror("讀取或解析失敗", f"處理檔案時發生錯誤：\n{e}")
            self.update_status(f"錯誤：{e}", is_error=True)
            
        self.result_text.tag_config('error', foreground='red')
        self.result_text.tag_config('normal', foreground='black')

    def export_to_excel(self):
        """
        將 self.parsed_results 的內容匯出為 Excel 檔案
        """
        if not self.parsed_results:
            messagebox.showwarning("無法匯出", "沒有可匯出的解析結果。請先執行一次解析。")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 檔案", "*.xlsx")],
            title="請選擇儲存位置與檔名"
        )

        if not filepath:
            self.update_status("匯出操作已取消。")
            return

        try:
            self.update_status(f"正在匯出至 {filepath} ...")
            df_export = pd.DataFrame(self.parsed_results, columns=['項目 (Item)', '數值 (Value)'])
            df_export.to_excel(filepath, index=False)
            
            messagebox.showinfo("匯出成功", f"解析結果已成功儲存至：\n{filepath}")
            self.update_status(f"成功匯出至 {filepath}")

        except Exception as e:
            messagebox.showerror("匯出失敗", f"儲存檔案時發生錯誤：\n{e}")
            self.update_status(f"錯誤：匯出失敗！ {e}", is_error=True)

    def update_status(self, message, is_error=False):
        """
        更新狀態列的文字和顏色
        """
        self.status_bar.config(text=message, fg="red" if is_error else "black")
        self.root.update_idletasks()


if __name__ == "__main__":
    root = tk.Tk()
    app = BinaryParserApp(root)
    root.mainloop()
