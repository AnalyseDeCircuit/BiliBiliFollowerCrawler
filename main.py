import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
import threading
import time
import os
import platform
from datetime import datetime, timedelta

class BiliFollowerMonitor:
    def __init__(self, master):
        self.master = master
        master.title("B站粉丝监控工具 v2.4")
        master.minsize(700, 600)
        master.geometry("750x650")

        # 初始化变量
        self.is_running = False
        self.log_file = None
        self.log_file_handle = None
        self.last_uid = ""
        self.caffeinate_process = None
        self.user_info = {
            "uid": "",
            "nickname": "",
            "last_followers": 0
        }
        self.statistics = {
            "records": [],
            "first_valid_record": None
        }

        # 字体配置
        self.font_config = {
            "title": ("Microsoft YaHei", 13, "bold"),
            "input": ("Consolas", 13),
            "log": ("Courier New", 11),
            "button": ("Microsoft YaHei", 13)
        }

        # 配置网格布局
        master.grid_columnconfigure(1, weight=1)
        master.grid_rowconfigure(5, weight=1)

        # 创建界面组件
        self.create_widgets()
        self.setup_style()

    def setup_style(self):
        """配置ttk组件样式"""
        style = ttk.Style()
        style.configure("TButton", font=self.font_config["button"])
        style.configure("TCheckbutton", font=self.font_config["title"])
        style.configure("TCombobox", font=self.font_config["input"])

    def create_widgets(self):
        """创建界面组件"""
        # 用户UID输入
        ttk.Label(self.master, text="用户UID:", font=self.font_config["title"]).grid(
            row=0, column=0, padx=15, pady=8, sticky="w")
        self.uid_entry = ttk.Entry(self.master, font=self.font_config["input"])
        self.uid_entry.grid(row=0, column=1, padx=15, pady=8, sticky="ew")
        self.uid_entry.bind("<FocusOut>", self.on_uid_change)

        # 用户昵称显示（只读）
        ttk.Label(self.master, text="用户昵称:", font=self.font_config["title"]).grid(
            row=1, column=0, padx=15, pady=8, sticky="w")
        self.nickname_var = tk.StringVar()
        self.nickname_entry = ttk.Entry(self.master, font=self.font_config["input"], textvariable=self.nickname_var, state="readonly")
        self.nickname_entry.grid(row=1, column=1, padx=15, pady=8, sticky="ew")

        # 间隔时间设置
        ttk.Label(self.master, text="刷新间隔(秒):", font=self.font_config["title"]).grid(
            row=2, column=0, padx=15, pady=8, sticky="w")
        self.interval_entry = ttk.Entry(self.master, width=10, font=self.font_config["input"])
        self.interval_entry.insert(0, "60")
        self.interval_entry.grid(row=2, column=1, padx=15, pady=8, sticky="w")

        # 控制按钮
        button_frame = ttk.Frame(self.master)
        button_frame.grid(row=3, column=0, columnspan=2, pady=12, sticky="ew")
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        self.start_btn = ttk.Button(
            button_frame, text="开始监控", command=self.start_monitoring, 
            style="TButton")
        self.start_btn.grid(row=0, column=0, padx=8, sticky="ew")
        
        self.stop_btn = ttk.Button(
            button_frame, text="停止监控", command=self.stop_monitoring, 
            state=tk.DISABLED, style="TButton")
        self.stop_btn.grid(row=0, column=1, padx=8, sticky="ew")

        # 日志保存选项
        self.log_save_frame = ttk.Frame(self.master)
        self.log_save_frame.grid(row=4, column=0, columnspan=2, pady=8, sticky="w")

        self.save_log_var = tk.BooleanVar()
        self.save_check = ttk.Checkbutton(
            self.log_save_frame, 
            text="保存日志文件", 
            variable=self.save_log_var,
            command=self.toggle_log_options,
            style="TCheckbutton"
        )
        self.save_check.pack(side=tk.LEFT, padx=5)

        self.log_mode_var = tk.StringVar()
        self.log_mode = ttk.Combobox(
            self.log_save_frame,
            textvariable=self.log_mode_var,
            values=["新建文件（覆盖）", "追加到现有文件"],
            state="disabled",
            width=18,
            style="TCombobox"
        )
        self.log_mode.pack(side=tk.LEFT, padx=5)
        self.log_mode.bind("<<ComboboxSelected>>", self.select_log_file)

        # 新增：数据可视化按钮
        self.visual_btn = ttk.Button(
            self.log_save_frame,
            text="导出并可视化",
            command=self.export_data_and_show_plot,
            style="TButton"
        )
        self.visual_btn.pack(side=tk.LEFT, padx=5)

        # 日志显示区域
        self.log_text = tk.Text(
            self.master, 
            font=self.font_config["log"],
            state=tk.DISABLED,
            wrap=tk.WORD,
            tabs=('0.5c', '2c'),
            bg='#F5F5F5'
        )
        self.log_text.grid(row=5, column=0, columnspan=2, padx=15, pady=10, sticky="nsew")
        
        self.scrollbar = ttk.Scrollbar(self.master, command=self.log_text.yview)
        self.scrollbar.grid(row=5, column=2, sticky="ns")
        self.log_text.config(yscrollcommand=self.scrollbar.set)

        # 导出数据按钮
        self.export_btn = ttk.Button(
            self.master, text="导出数据并显示趋势图", command=self.export_data_and_show_plot, 
            style="TButton")
        self.export_btn.grid(row=6, column=0, columnspan=2, pady=12, sticky="ew")

    def toggle_log_options(self):
        """切换日志保存选项状态"""
        if self.save_log_var.get():
            self.log_mode.config(state="readonly")
            self.log_mode_var.set("")
        else:
            self.log_mode.config(state="disabled")
            self.log_file = None
            self.log_mode_var.set("")
            if hasattr(self, 'log_file_handle'):
                self.log_file_handle.close()
                del self.log_file_handle

    def select_log_file(self, event=None):
        """选择日志文件路径（严格模式）"""
        if not self.save_log_var.get():
            return

        mode = self.log_mode_var.get()
        if not mode:
            messagebox.showwarning("提示", "请先选择日志模式")
            self.save_log_var.set(False)
            return

        try:
            if mode == "新建文件（覆盖）":
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".log",
                    filetypes=[("日志文件", "*.log"), ("所有文件", "*.*")],
                    title="选择或创建日志文件"
                )
            elif mode == "追加到现有文件":
                file_path = filedialog.askopenfilename(
                    defaultextension=".log",
                    filetypes=[("日志文件", "*.log"), ("所有文件", "*.*")],
                    title="选择现有日志文件"
                )
                if file_path:
                    if not os.path.exists(file_path):
                        messagebox.showerror("错误", "文件不存在，请重新选择")
                        return self.select_log_file()
                    if not os.access(file_path, os.W_OK):
                        messagebox.showerror("错误", "文件不可写，请检查权限")
                        return self.select_log_file()
            else:
                return

            if file_path:
                self.log_file = file_path
                try:
                    test_mode = 'w' if mode == "新建文件（覆盖）" else 'a'
                    with open(file_path, test_mode, encoding='utf-8') as test_file:
                        test_file.write('')
                except Exception as e:
                    messagebox.showerror("错误", f"文件访问失败：{str(e)}")
                    return self.select_log_file()
            else:
                self.save_log_var.set(False)
                self.log_mode.config(state="disabled")
                self.log_mode_var.set("")
        except Exception as e:
            messagebox.showerror("错误", f"文件选择失败：{str(e)}")
            self.save_log_var.set(False)
            self.log_mode.config(state="disabled")
            self.log_mode_var.set("")

    def start_monitoring(self):
        """启动监控"""
        uid = self.uid_entry.get().strip()
        nickname = self.nickname_entry.get().strip()
        
        if not self.validate_inputs(uid, nickname):
            return

        if self.save_log_var.get() and not self.prepare_log_file():
            return

        self.prevent_sleep()
        self.initialize_monitoring(uid, nickname)

    def on_uid_change(self, event=None):
        """UID输入后自动获取昵称"""
        uid = self.uid_entry.get().strip()
        if not uid or not uid.isdigit():
            self.nickname_var.set("")
            return
        try:
            url = f"https://api.bilibili.com/x/space/acc/info?mid={uid}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                self.nickname_var.set(data["data"].get("name", ""))
            else:
                self.nickname_var.set("")
        except Exception:
            self.nickname_var.set("")

    def validate_inputs(self, uid, nickname):
        """验证输入有效性"""
        error_msgs = []
        if not uid:
            error_msgs.append("UID不能为空")
        elif not uid.isdigit():
            error_msgs.append("UID必须是数字")
        if not nickname:
            error_msgs.append("昵称获取失败，请检查UID")
        
        if error_msgs:
            messagebox.showerror("输入错误", "\n".join(error_msgs))
            return False
        
        try:
            interval = int(self.interval_entry.get())
            if interval < 40:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "请输入≥40秒的整数间隔时间")
            return False
        
        return True

    def prevent_sleep(self):
        """防止系统休眠（跨平台）"""
        system = platform.system()
        try:
            import subprocess
            if system == 'Darwin':
                self.caffeinate_process = subprocess.Popen(['caffeinate', '-di'])
            elif system == 'Windows':
                # 使用 powershell 无限循环防止休眠
                self.caffeinate_process = subprocess.Popen([
                    'powershell', '-Command', 'while ($true) { Start-Sleep -Seconds 60 }'
                ])
            elif system == 'Linux':
                # 使用 bash 无限循环防止休眠
                self.caffeinate_process = subprocess.Popen([
                    'bash', '-c', 'while true; do sleep 60; done'
                ])
        except Exception as e:
            self.update_log(f"警告：无法防止系统休眠 - {str(e)}")

    def allow_sleep(self):
        """允许系统休眠（跨平台）"""
        if hasattr(self, 'caffeinate_process') and self.caffeinate_process:
            try:
                self.caffeinate_process.terminate()
                self.caffeinate_process = None
            except Exception:
                pass

    def prepare_log_file(self):
        """准备日志文件"""
        try:
            mode = 'w' if self.log_mode_var.get() == "新建文件（覆盖）" else 'a'
            self.log_file_handle = open(self.log_file, mode, encoding='utf-8')
            return True
        except Exception as e:
            messagebox.showerror("错误", f"无法打开日志文件：{str(e)}")
            self.save_log_var.set(False)
            return False

    def initialize_monitoring(self, uid, nickname):
        """初始化监控状态"""
        self.statistics = {
            "records": [],
            "first_valid_record": None
        }
        self.user_info = {
            "uid": uid,
            "nickname": nickname,
            "last_followers": 0
        }
        self.is_running = True
        self.last_uid = uid
        
        for widget in [self.uid_entry, self.nickname_entry, 
                      self.interval_entry, self.save_check, self.log_mode]:
            widget.config(state=tk.DISABLED)
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        self.monitor_thread = threading.Thread(
            target=self.monitor_followers, 
            args=(uid, int(self.interval_entry.get()))
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.update_log("=== 监控已启动 ===")

    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        self.allow_sleep()

        if len(self.statistics["records"]) >= 2:
            self.generate_statistics()

        for widget in [self.uid_entry, self.nickname_entry, 
                      self.interval_entry, self.save_check, self.log_mode]:
            widget.config(state=tk.NORMAL)
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
        if hasattr(self, 'log_file_handle'):
            self.log_file_handle.close()
            del self.log_file_handle
        
        if hasattr(self, '_first_run'):
            del self._first_run

    def monitor_followers(self, uid, interval):
        """监控线程主逻辑"""
        url = f"https://api.bilibili.com/x/relation/stat?vmid={uid}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": f"https://space.bilibili.com/{uid}/"
        }

        next_run = time.monotonic()
        first_run = True

        while self.is_running and uid == self.last_uid:
            try:
                now = time.monotonic()
                if now < next_run:
                    time.sleep(next_run - now)
                
                record_time = datetime.now()
                response = requests.get(url, headers=headers, timeout=15)
                data = response.json()

                if data["code"] == 0:
                    current_followers = data["data"]["follower"]
                    self.process_success_response(current_followers, uid, record_time, first_run)
                    first_run = False
                else:
                    error_msg = f"接口错误：{data.get('message', '未知错误')} (code: {data['code']})"
                    self.update_log(error_msg)

                next_run += interval

            except requests.exceptions.RequestException as e:
                self.update_log(f"网络错误：{str(e)}")
            except Exception as e:
                self.update_log(f"未知错误：{str(e)}")

        if self.is_running:
            self.process_final_record(uid)

    def process_success_response(self, current_followers, uid, record_time, is_first):
        """处理成功响应"""
        record = {
            "time": record_time,
            "followers": current_followers
        }
        self.statistics["records"].append(record)

        if not is_first and not self.statistics["first_valid_record"]:
            self.statistics["first_valid_record"] = record

        if len(self.statistics["records"]) >= 2:
            prev = self.statistics["records"][-2]["followers"]
            change = current_followers - prev
        else:
            change = 0

        log_msg = (
            f"[{record_time.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"uid：{uid}，昵称：{self.user_info['nickname']}，"
            f"当前粉丝数：{current_followers}，"
            f"变化量：{change:+}" + (" (首次获取)" if is_first else "")
        )
        self.update_log(log_msg)

    def process_final_record(self, uid):
        """处理最终记录"""
        if len(self.statistics["records"]) >= 1:
            last_record = self.statistics["records"][-1]
            current_followers = last_record["followers"]
            record_time = datetime.now()
            self.process_success_response(current_followers, uid, record_time, False)
            self.update_log("已补全最终数据点")

    def generate_statistics(self):
        """生成统计信息"""
        if not self.statistics["first_valid_record"]:
            return

        first_valid = self.statistics["first_valid_record"]
        last_record = self.statistics["records"][-1]

        total_change = last_record["followers"] - first_valid["followers"]
        total_seconds = (last_record["time"] - first_valid["time"]).total_seconds()
        time_diff_minutes = total_seconds / 60
        avg_rate = total_change / time_diff_minutes if time_diff_minutes > 0 else 0
        duration = timedelta(seconds=int(total_seconds))

        stats_msg = (
            "\n=== 监控统计 ==="
            f"\n• 有效开始：{first_valid['time'].strftime('%Y-%m-%d %H:%M:%S')}"
            f"\n• 有效结束：{last_record['time'].strftime('%Y-%m-%d %H:%M:%S')}"
            f"\n• 持续时长：{duration}"
            f"\n• 总粉丝变化：{total_change:+}"
            f"\n• 平均变化速率：{avg_rate:+.2f} 粉丝/分钟"
            "\n================="
        )
        self.update_log(stats_msg)

    def update_log(self, message):
        """更新日志显示和文件"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

        if hasattr(self, 'log_file_handle') and self.log_file_handle:
            try:
                self.log_file_handle.write(message + "\n")
                self.log_file_handle.flush()
            except Exception as e:
                self.save_log_var.set(False)
                self.log_file_handle.close()
                del self.log_file_handle
                messagebox.showerror("错误", f"日志写入失败：{str(e)}")

    def export_data_and_show_plot(self):
        """导出监控数据为CSV并弹出可视化折线图"""
        import pandas as pd
        import matplotlib.pyplot as plt
        from tkinter import filedialog
        if not self.statistics["records"]:
            messagebox.showinfo("提示", "暂无可导出的监控数据！")
            return
        # 导出CSV
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")],
            title="导出监控数据为CSV"
        )
        if not file_path:
            return
        df = pd.DataFrame([
            {"time": r["time"].strftime("%Y-%m-%d %H:%M:%S"), "followers": r["followers"]}
            for r in self.statistics["records"]
        ])
        try:
            df.to_csv(file_path, index=False, encoding="utf-8-sig")
        except Exception as e:
            messagebox.showerror("导出失败", f"CSV写入失败：{str(e)}")
            return
        # 可视化
        try:
            plt.figure(figsize=(8, 4))
            plt.plot(pd.to_datetime(df['time']), df['followers'], marker='o')
            plt.xlabel('时间')
            plt.ylabel('粉丝数')
            plt.title('B站粉丝数变化趋势')
            plt.xticks(rotation=30)
            plt.tight_layout()
            plt.show()
        except Exception as e:
            messagebox.showerror("可视化失败", f"绘图失败：{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BiliFollowerMonitor(root)
    root.mainloop()
