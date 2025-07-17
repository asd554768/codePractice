import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import pandas as pd

class BinaryParserApp:
    def __init__(self, root):
        """
        初始化應用程式 GUI 介面
        """
        self.root = root
        self.root.title("二進位檔案解析工具 v2.1")
        self.root.geometry("700x500")

        self.excel_path = tk.StringVar()
        self.bin_path = tk.StringVar()

        # --- 介面框架 ---
        main_frame = tk.Frame(root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 檔案選擇區 ---
        file_frame = tk.LabelFrame(main_frame, text="檔案選擇", padx=10, pady=10)
        file_frame.pack(fill=tk.X, pady=5)

        # Excel 規則檔案
        tk.Button(file_frame, text="1. 選擇 Excel 規則檔", command=self.select_excel_file).grid(row=0, column=0, sticky=tk.W, pady=2)
        tk.Entry(file_frame, textvariable=self.excel_path, width=70, state='readonly').grid(row=0, column=1, sticky=tk.EW, padx=5)

        # Binary 目標檔案
        tk.Button(file_frame, text="2. 選擇 Binary 目標檔 (.bin)", command=self.select_bin_file).grid(row=1, column=0, sticky=tk.W, pady=2)
        tk.Entry(file_frame, textvariable=self.bin_path, width=70, state='readonly').grid(row=1, column=1, sticky=tk.EW, padx=5)
        
        # --- 執行按鈕 ---
        tk.Button(main_frame, text="開始解析 (Parse)", font=("Arial", 12, "bold"), bg="#007BFF", fg="white", command=self.parse_data).pack(fill=tk.X, pady=10)

        # --- 結果顯示區 ---
        result_frame = tk.LabelFrame(main_frame, text="解析結果", padx=10, pady=10)
        result_frame.pack(fill=tk.BOTH, expand=True)
        
        self.result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, font=("Consolas", 11))
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # --- 狀態列 ---
        self.status_bar = tk.Label(root, text="請先選擇檔案", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        file_frame.grid_columnconfigure(1, weight=1)

    def select_excel_file(self):
        """
        開啟檔案對話框以選擇 Excel 檔案
        """
        path = filedialog.askopenfilename(
            title="選擇 Excel 規則檔案",
            filetypes=[("Excel 檔案", "*.xlsx *.xls")]
        )
        if path:
            self.excel_path.set(path)
            self.update_status(f"已選擇 Excel 規則檔: {path}")

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
        核心功能：讀取規則與目標檔案，根據第四欄的型態定義進行解析並顯示結果
        """
        excel_file = self.excel_path.get()
        bin_file = self.bin_path.get()

        if not excel_file or not bin_file:
            messagebox.showerror("錯誤", "請務必同時選擇 Excel 規則檔案和 Binary 目標檔案。")
            return

        self.result_text.delete('1.0', tk.END)
        self.update_status("正在解析中...")

        try:
            df_rules = pd.read_excel(excel_file, header=None).fillna('')
            df_rules.columns = ['name', 'start', 'length', 'type']

            with open(bin_file, 'rb') as f:
                binary_content = f.read()
            
            file_size = len(binary_content)
            self.result_text.insert(tk.END, f"--- Binary 檔案總大小: {file_size} bytes ---\n\n")

            for index, rule in df_rules.iterrows():
                name = rule['name']
                data_type = str(rule['type']).strip().lower()

                try:
                    start = int(rule['start'])
                    length = int(rule['length'])
                except ValueError:
                    result_line = f"{name}: 錯誤 - Excel 中的起始位置或長度不是有效的數字。\n"
                    self.result_text.insert(tk.END, result_line, 'error')
                    continue

                end = start + length

                if start >= file_size or end > file_size:
                    result_line = f"{name}: 錯誤 - 定義的範圍 [{start}-{end}] 超出檔案總長度 {file_size}。\n"
                    self.result_text.insert(tk.END, result_line, 'error')
                    continue

                data_chunk = binary_content[start:end]
                
                result_value = ""
                
                if data_type == 'int':
                    # --- *** MODIFIED LINE *** ---
                    # 依然從 Little-Endian 讀取數值
                    parsed_int = int.from_bytes(data_chunk, byteorder='little')
                    # 將得到的數值格式化為大寫的十六進位字串
                    hex_value = f"0x{parsed_int:X}"
                    result_value = f"{hex_value}"
                    # --- *** END OF MODIFICATION *** ---

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
                
                result_line = f"{name}: {result_value}\n"
                self.result_text.insert(tk.END, result_line)

            self.update_status("解析完成！")

        except FileNotFoundError as e:
            messagebox.showerror("檔案未找到", f"找不到指定的檔案：\n{e}")
            self.update_status(f"錯誤：找不到檔案", is_error=True)
        except Exception as e:
            messagebox.showerror("發生錯誤", f"處理過程中發生未預期的錯誤：\n{e}")
            self.update_status(f"錯誤：{e}", is_error=True)
            
        self.result_text.tag_config('error', foreground='red')

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