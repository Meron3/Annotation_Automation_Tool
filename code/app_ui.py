# app_ui.py
import tkinter
import customtkinter as ctk
from PIL import Image, ImageTk
from ultralytics import YOLO
import os
from event_handlers import EventHandlers
from utils import format_bytes
import datetime
import copy
import time
import colorsys

MAX_HISTORY = 101

class AnnotationApp(ctk.CTk):
    def __init__(self, model_path):
        super().__init__()
        self.title("汎用画像アノテーションツール (v2.14.12)")
        self.geometry("1500x900")

        self.font_family = "Meiryo UI" 
        
        self.model = YOLO(model_path); self.events = EventHandlers(self)
        self.mode = 'start'; self.mouse_state = 'idle'
        self.project_dir, self.image_dir, self.labels_dir = "", "", ""
        self.class_names, self.all_image_files, self.image_files = [], [], []
        self.current_image_index = -1
        self.current_image, self.tk_image = None, None
        self.resized_w, self.resized_h = 0, 0
        self.boxes = {}; self.undo_stack = []; self.redo_stack = []
        
        # 承認ステータス用
        self.approval_status = {}
        self.status_file_path = ""
        
        self.selected_box_id, self.selected_handle = None, None
        self.start_x, self.start_y, self.temp_box_id = None, None, None
        
        # クロスヘア用ID
        self.crosshair_v = None
        self.crosshair_h = None
        
        # オプション
        self.box_line_width = 2
        self.box_font_size = 12
        self.log_visible_lines = 4
        self.target_count = 0
        self.progress_style = "bar"

        # 自動保存・演出用設定
        self.auto_save_interval = 300000 # 初期値5分
        self.has_celebrated = False
        self.gaming_task = None      
        self.original_colors = {}    
        
        # 計測・制御用
        self.start_time = None
        self.session_start_count = None
        self.annotated_count_cache = 0
        self.ignore_input_until = 0
        self.is_dialog_active = False
        
        # サイズキャッシュ
        self.total_image_size_cache = 0
        self.total_label_size_cache = 0

        self.options_window = None
        self.resize_timer = None
        self.log_file_path = None
        self.stats_labels = {} 

        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(0, weight=1)
        
        self.start_frame = self.create_start_screen()
        self.main_frame = ctk.CTkFrame(self)
        self.start_frame.grid(row=0, column=0, sticky="nsew")
        
        self.bind_shortcuts()
        self.bind("<Configure>", self._on_resize)
        self.schedule_auto_save()
        
        self.update_timer()

    def schedule_auto_save(self):
        if self.auto_save_interval > 0:
            self.events.save_project_session(silent=True)
            self.after(self.auto_save_interval, self.schedule_auto_save)

    def update_timer(self):
        if self.mode != 'start' and self.start_time is not None:
            elapsed_seconds = int(time.time() - self.start_time)
            hours, remainder = divmod(elapsed_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours:02}:{minutes:02}:{seconds:02}"
            
            pace_str = "- sec/枚"
            if self.session_start_count is not None:
                session_processed = self.annotated_count_cache - self.session_start_count
                if session_processed > 0:
                    avg_time = elapsed_seconds / session_processed
                    pace_str = f"{avg_time:.1f} sec/枚"

            if hasattr(self, 'time_val_label'):
                self.time_val_label.configure(text=time_str)
                self.pace_val_label.configure(text=pace_str)

        self.after(1000, self.update_timer)

    def log(self, message):
        print(message)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        full_log_entry = f"[{timestamp}] {message}\n"

        if self.log_file_path:
            try:
                with open(self.log_file_path, 'a', encoding='utf-8') as f:
                    f.write(full_log_entry)
            except Exception as e:
                print(f"Log file writing error: {e}")

        if hasattr(self, 'log_textbox') and self.log_textbox.winfo_exists():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", full_log_entry)
            self.log_textbox.see("end")
            content = self.log_textbox.get("1.0", "end").split("\n")
            if len(content) > 200:
                self.log_textbox.delete("1.0", f"{len(content)-200}.0")
            self.log_textbox.configure(state="disabled")

    def create_start_screen(self):
        frame = ctk.CTkFrame(self)
        frame.grid_columnconfigure(0, weight=1); frame.grid_rowconfigure(0, weight=1)
        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(content_frame, text="アノテーションツール", font=ctk.CTkFont(family=self.font_family, size=24, weight="bold")).pack(pady=20)
        
        step1_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        step1_frame.pack(pady=10, fill="x")
        ctk.CTkButton(step1_frame, text="1. プロジェクトを選択", command=self.events.select_project_folder, font=ctk.CTkFont(family=self.font_family)).pack(pady=5, ipady=2)
        self.project_path_label = ctk.CTkLabel(step1_frame, text="プロジェクト: 未選択", text_color="gray", font=ctk.CTkFont(family=self.font_family)); self.project_path_label.pack()

        step2_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        step2_frame.pack(pady=10, fill="x")
        self.select_image_folder_button = ctk.CTkButton(step2_frame, text="2. 対象画像フォルダを選択", command=self.events.select_image_folder, state="disabled", font=ctk.CTkFont(family=self.font_family))
        self.select_image_folder_button.pack(pady=5, ipady=2)
        self.image_path_label = ctk.CTkLabel(step2_frame, text="対象フォルダ: 未選択", text_color="gray", font=ctk.CTkFont(family=self.font_family)); self.image_path_label.pack()

        stats_frame = ctk.CTkFrame(content_frame, border_width=1, border_color="gray")
        stats_frame.pack(pady=20, padx=10, fill="x")
        ctk.CTkLabel(stats_frame, text="現在のプロジェクトステータス", font=ctk.CTkFont(family=self.font_family, weight="bold")).grid(row=0, column=0, columnspan=5, pady=5)
        
        labels = [("総枚数", "total"), ("アノテーション済", "annotated"), ("承認 (OK)", "approved"), ("却下 (NG)", "rejected"), ("再承認待ち", "fixed")]
        for i, (text, key) in enumerate(labels):
            ctk.CTkLabel(stats_frame, text=text, font=ctk.CTkFont(family=self.font_family)).grid(row=1, column=i, padx=10, pady=(5,0))
            self.stats_labels[key] = ctk.CTkLabel(stats_frame, text="-", font=ctk.CTkFont(family=self.font_family, size=18, weight="bold"))
            self.stats_labels[key].grid(row=2, column=i, padx=10, pady=(0,10))
            stats_frame.grid_columnconfigure(i, weight=1)

        size_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        size_frame.grid(row=3, column=0, columnspan=5, pady=(5, 5))
        self.stats_labels['total_size'] = ctk.CTkLabel(size_frame, text="合計容量 (画像: - / ラベル: -)", font=ctk.CTkFont(family=self.font_family, size=12))
        self.stats_labels['total_size'].pack()

        ctk.CTkLabel(content_frame, text="--- 作業を選択 ---", font=ctk.CTkFont(family=self.font_family)).pack(pady=(10, 5))
        
        btn_frame1 = ctk.CTkFrame(content_frame, fg_color="transparent")
        btn_frame1.pack(pady=5)
        self.start_annotation_button = ctk.CTkButton(btn_frame1, text="3. アノテーション開始 (全件)", state="disabled", command=self.events.start_annotation_mode, width=220, font=ctk.CTkFont(family=self.font_family))
        self.start_annotation_button.grid(row=0, column=0, padx=5, pady=5)
        self.start_approval_button = ctk.CTkButton(btn_frame1, text="4. 承認作業 (全件/未承認)", state="disabled", command=self.events.start_approval_mode, width=220, font=ctk.CTkFont(family=self.font_family))
        self.start_approval_button.grid(row=0, column=1, padx=5, pady=5)

        btn_frame2 = ctk.CTkFrame(content_frame, fg_color="transparent")
        btn_frame2.pack(pady=5)
        self.start_correction_button = ctk.CTkButton(btn_frame2, text="5. 修正作業 (NGのみ)", state="disabled", command=self.events.start_correction_mode, width=220, font=ctk.CTkFont(family=self.font_family))
        self.start_correction_button.grid(row=0, column=0, padx=5, pady=5)
        self.start_reapproval_button = ctk.CTkButton(btn_frame2, text="6. 再承認作業 (修正分のみ)", state="disabled", command=self.events.start_reapproval_mode, width=220, font=ctk.CTkFont(family=self.font_family))
        self.start_reapproval_button.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(content_frame, text="--- 完了後 ---", font=ctk.CTkFont(family=self.font_family)).pack(pady=(20, 5))
        self.export_button = ctk.CTkButton(content_frame, text="7. データセットのエクスポート", state="disabled", command=self.events.export_approved_dataset, width=450, fg_color="#E59100", hover_color="#B37100", font=ctk.CTkFont(family=self.font_family))
        self.export_button.pack(pady=5)
        return frame

    def create_main_ui(self):
        if self.main_frame.winfo_children(): return
        self.main_frame.grid_columnconfigure(1, weight=1); self.main_frame.grid_rowconfigure(0, weight=1)
        
        self.left_frame = ctk.CTkFrame(self.main_frame, width=300, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsw")
        
        top_controls_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        top_controls_frame.pack(pady=0, padx=20, fill="x", side="top")
        
        ctk.CTkButton(top_controls_frame, text="プロジェクト選択画面に戻る", command=self.switch_to_start_screen, font=ctk.CTkFont(family=self.font_family)).pack(pady=(10,5), fill="x")
        ctk.CTkButton(top_controls_frame, text="オプション設定", command=self.open_options_window, font=ctk.CTkFont(family=self.font_family)).pack(pady=5, fill="x")
        
        nav_frame = ctk.CTkFrame(top_controls_frame, fg_color="transparent")
        nav_frame.pack(pady=5, fill="x")
        ctk.CTkButton(nav_frame, text="<< 戻る[←]", command=self.events.prev_image, font=ctk.CTkFont(family=self.font_family)).pack(side="left", expand=True, padx=(0,5))
        ctk.CTkButton(nav_frame, text="次へ[→] >>", command=self.events.next_image, font=ctk.CTkFont(family=self.font_family)).pack(side="left", expand=True, padx=(5,0))

        self.save_and_next_button = ctk.CTkButton(top_controls_frame, text="保存して次へ (Enter)", command=self.events.save_and_next, fg_color="#6473FF", hover_color="#1A9334", font=ctk.CTkFont(family=self.font_family))
        self.save_button = ctk.CTkButton(top_controls_frame, text="保存のみ (Ctrl+S)", command=self.events.save_annotations, font=ctk.CTkFont(family=self.font_family))
        self.save_project_button = ctk.CTkButton(top_controls_frame, text="プロジェクトを途中保存", command=self.events.save_project_session, font=ctk.CTkFont(family=self.font_family))
        
        self.approve_button = ctk.CTkButton(top_controls_frame, text="承認して次へ (OK)", command=self.events.approve_annotation, fg_color="green", hover_color="darkgreen", font=ctk.CTkFont(family=self.font_family))
        self.reject_button = ctk.CTkButton(top_controls_frame, text="却下して次へ (NG)", command=self.events.reject_annotation, fg_color="red", hover_color="darkred", font=ctk.CTkFont(family=self.font_family))

        progress_frame = ctk.CTkFrame(self.left_frame); progress_frame.pack(pady=10, padx=20, fill="x", side="top")
        
        timer_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        timer_frame.pack(fill="x", pady=(5,5))
        ctk.CTkLabel(timer_frame, text="作業時間:", font=ctk.CTkFont(family=self.font_family, size=11)).pack(side="left", padx=5)
        self.time_val_label = ctk.CTkLabel(timer_frame, text="00:00:00", font=ctk.CTkFont(family=self.font_family, size=12, weight="bold"))
        self.time_val_label.pack(side="left", padx=5)
        
        pace_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        pace_frame.pack(fill="x", pady=(0,10))
        ctk.CTkLabel(pace_frame, text="ペース:", font=ctk.CTkFont(family=self.font_family, size=11)).pack(side="left", padx=5)
        self.pace_val_label = ctk.CTkLabel(pace_frame, text="- sec/枚", font=ctk.CTkFont(family=self.font_family, size=12, weight="bold"))
        self.pace_val_label.pack(side="left", padx=5)

        ctk.CTkLabel(progress_frame, text="--- 進捗状況 ---", font=ctk.CTkFont(family=self.font_family, weight="bold")).pack()
        self.progress_label = ctk.CTkLabel(progress_frame, text="完了: 0 / 0", font=ctk.CTkFont(family=self.font_family)); self.progress_label.pack()
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame); self.progress_bar.set(0)
        
        fg_color = progress_frame.cget("fg_color")
        appearance_mode = ctk.get_appearance_mode()
        canvas_bg = "gray"
        if isinstance(fg_color, (list, tuple)):
            if len(fg_color) >= 2:
                canvas_bg = fg_color[0] if appearance_mode == "Light" else fg_color[1]
            elif len(fg_color) == 1:
                canvas_bg = fg_color[0]
        else:
            canvas_bg = fg_color
            
        self.pie_canvas = tkinter.Canvas(progress_frame, width=140, height=150, bg=canvas_bg, highlightthickness=0)

        if self.progress_style == "bar": self.progress_bar.pack(fill="x", padx=10, pady=5)
        else: self.pie_canvas.pack(pady=5)

        self.current_img_size_label = ctk.CTkLabel(progress_frame, text="現在の画像サイズ: -", font=ctk.CTkFont(family=self.font_family)); self.current_img_size_label.pack(anchor="w", padx=10)
        self.total_img_size_label = ctk.CTkLabel(progress_frame, text="画像合計サイズ: -", font=ctk.CTkFont(family=self.font_family)); self.total_img_size_label.pack(anchor="w", padx=10)
        self.label_size_label = ctk.CTkLabel(progress_frame, text="ラベル合計サイズ: -", font=ctk.CTkFont(family=self.font_family)); self.label_size_label.pack(anchor="w", padx=10)
        
        self.box_list_frame = ctk.CTkScrollableFrame(self.left_frame, label_text="--- オブジェクト一覧 ---"); self.box_list_frame.pack(pady=10, padx=20, fill="both", expand=True, side="top")
        
        self.right_frame = ctk.CTkFrame(self.main_frame); self.right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.right_frame.grid_rowconfigure(1, weight=1); self.right_frame.grid_columnconfigure(0, weight=1)
        self.info_frame = ctk.CTkFrame(self.right_frame); self.info_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))
        self.image_info_label = ctk.CTkLabel(self.info_frame, text="画像: - / -", anchor="w", font=ctk.CTkFont(family=self.font_family)); self.image_info_label.pack(side="left", padx=10)
        self.status_display_label = ctk.CTkLabel(self.info_frame, text="ステータス: 未選択", anchor="e", font=ctk.CTkFont(family=self.font_family)); self.status_display_label.pack(side="right", padx=10)
        self.canvas = tkinter.Canvas(self.right_frame, bg="gray", bd=0, highlightthickness=0, cursor="tcross"); self.canvas.grid(row=1, column=0, sticky="nsew")
        self.log_textbox = ctk.CTkTextbox(self.right_frame, state="disabled", font=ctk.CTkFont(family=self.font_family, size=12));
        self.log_textbox.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self._update_log_view_height(self.log_visible_lines)
        
        # 移動イベントのバインド (クリック移動方式なのでMotionが重要)
        self.canvas.bind("<ButtonPress-1>", self.events.on_mouse_press)
        self.canvas.bind("<Motion>", self.events.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.events.on_mouse_release)
        self.canvas.bind("<Button-3>", self.events.on_right_click)

    def switch_to_main_ui(self, mode):
        self.mode = mode; self.start_frame.grid_forget()
        self.create_main_ui()
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        title_map = {"annotation": "アノテーションモード", "approval": "承認モード", "correction": "修正モード (NGのみ)", "reapproval": "再承認モード (Fixedのみ)"}
        self.title(f"アノテーションツール - {title_map.get(mode, mode)}")
        
        if self.start_time is None:
            self.start_time = time.time()

        if self.mode in ['approval', 'reapproval']:
            self.save_button.pack_forget(); self.save_and_next_button.pack_forget()
            self.save_project_button.pack(pady=5, fill="x"); self.save_project_button.configure(text="承認状況を保存")
            self.approve_button.pack(pady=(10, 5), fill="x"); self.reject_button.pack(pady=5, fill="x")
        else: 
            self.approve_button.pack_forget(); self.reject_button.pack_forget()
            self.save_and_next_button.pack(pady=(10,5), fill="x"); self.save_button.pack(pady=5, fill="x")
            self.save_project_button.pack(pady=5, fill="x"); self.save_project_button.configure(text="プロジェクトを途中保存")
        
        self.update_progress_display()

    def switch_to_start_screen(self):
        self.mode = 'start'; self.main_frame.grid_forget(); self.start_frame.grid(row=0, column=0, sticky="nsew")
        self.title("汎用画像アノテーションツール")
        if self.image_dir: self.events.update_dashboard_stats()

    def open_options_window(self):
        if self.options_window is None or not self.options_window.winfo_exists():
            self.options_window = ctk.CTkToplevel(self)
            self.options_window.title("オプション設定")
            self.options_window.geometry("300x550")
            self.options_window.transient(self)
            
            ctk.CTkLabel(self.options_window, text="線の幅 (即時反映)", font=ctk.CTkFont(family=self.font_family)).pack(fill="x", padx=15, pady=(10,0))
            line_slider = ctk.CTkSlider(self.options_window, from_=1, to=10, number_of_steps=9, command=self._update_line_width)
            line_slider.set(self.box_line_width); line_slider.pack(fill="x", padx=15, pady=5)
            
            ctk.CTkLabel(self.options_window, text="文字サイズ (即時反映)", font=ctk.CTkFont(family=self.font_family)).pack(fill="x", padx=15, pady=(10,0))
            font_slider = ctk.CTkSlider(self.options_window, from_=8, to=24, number_of_steps=16, command=self._update_font_size)
            font_slider.set(self.box_font_size); font_slider.pack(fill="x", padx=15, pady=5)
            
            ctk.CTkLabel(self.options_window, text="ログ表示行数", font=ctk.CTkFont(family=self.font_family)).pack(fill="x", padx=15, pady=(10,0))
            lines_entry = ctk.CTkEntry(self.options_window, placeholder_text=f"現在の設定: {self.log_visible_lines}行"); lines_entry.pack(fill="x", padx=15, pady=5)
            
            ctk.CTkLabel(self.options_window, text="目標完了枚数 (0で全数)", font=ctk.CTkFont(family=self.font_family)).pack(fill="x", padx=15, pady=(10,0))
            target_entry = ctk.CTkEntry(self.options_window); target_entry.insert(0, str(self.target_count)); target_entry.pack(fill="x", padx=15, pady=5)

            ctk.CTkLabel(self.options_window, text="自動保存間隔 (分) (0で無効)", font=ctk.CTkFont(family=self.font_family)).pack(fill="x", padx=15, pady=(10,0))
            autosave_entry = ctk.CTkEntry(self.options_window)
            current_min = int(self.auto_save_interval / 60000)
            autosave_entry.insert(0, str(current_min))
            autosave_entry.pack(fill="x", padx=15, pady=5)

            ctk.CTkLabel(self.options_window, text="進捗表示スタイル", font=ctk.CTkFont(family=self.font_family)).pack(fill="x", padx=15, pady=(10,0))
            style_var = tkinter.StringVar(value=self.progress_style)
            ctk.CTkRadioButton(self.options_window, text="棒グラフ", variable=style_var, value="bar", font=ctk.CTkFont(family=self.font_family)).pack(anchor="w", padx=20)
            ctk.CTkRadioButton(self.options_window, text="円グラフ", variable=style_var, value="pie", font=ctk.CTkFont(family=self.font_family)).pack(anchor="w", padx=20)

            def apply_changes():
                self._update_log_view_height(lines_entry.get())
                if (t_val := target_entry.get()).isdigit(): 
                    self.target_count = int(t_val)
                    self.has_celebrated = False 
                    self.stop_gaming_effect() # 設定変更時に演出停止
                    self.update_progress_display()
                
                if (as_val := autosave_entry.get()).isdigit():
                    minutes = int(as_val)
                    self.auto_save_interval = minutes * 60000
                    self.log(f"自動保存間隔を {minutes}分 に設定しました。")

                if (new_style := style_var.get()) != self.progress_style:
                    self.progress_style = new_style; self.progress_bar.pack_forget(); self.pie_canvas.pack_forget()
                    if self.progress_style == "bar": self.progress_bar.pack(fill="x", padx=10, pady=5)
                    else: self.pie_canvas.pack(pady=5)
                    self.update_progress_display()

            ctk.CTkButton(self.options_window, text="設定を適用 (Apply)", command=apply_changes, font=ctk.CTkFont(family=self.font_family)).pack(pady=(20, 5))
            ctk.CTkButton(self.options_window, text="閉じる (Close)", command=self.options_window.destroy, font=ctk.CTkFont(family=self.font_family), fg_color="gray").pack(pady=5)
        else: self.options_window.focus()

    def _update_line_width(self, value): self.box_line_width = int(value); self.redraw_boxes()
    def _update_font_size(self, value): self.box_font_size = int(value); self.redraw_boxes()
    def _update_log_view_height(self, value):
        if str(value).isdigit():
            self.log_visible_lines = int(value)
            if hasattr(self, 'log_textbox'): self.log_textbox.configure(height=self.log_visible_lines * 18); self._on_resize()

    def _on_resize(self, event=None):
        if self.resize_timer: self.after_cancel(self.resize_timer)
        self.resize_timer = self.after(100, self._update_canvas_image)

    def _update_canvas_image(self):
        # 操作中（ドラッグ中など）は自動リサイズによる再描画を行わない（割り込み防止）
        if self.mouse_state != 'idle':
            return

        if not self.current_image or not hasattr(self, 'canvas') or not self.canvas.winfo_exists(): return
        log_height = self.log_textbox.winfo_height() if hasattr(self, 'log_textbox') and self.log_textbox.winfo_viewable() else 0
        info_height = self.info_frame.winfo_height()
        canvas_width = self.right_frame.winfo_width()
        canvas_height = self.right_frame.winfo_height() - info_height - log_height - 10
        if canvas_height <= 0 or canvas_width <= 0 : return
        img_w, img_h = self.current_image.size
        scale = min(canvas_width / img_w, canvas_height / img_h) if img_w > 0 and img_h > 0 else 1
        self.resized_w, self.resized_h = int(img_w * scale), int(img_h * scale)
        self.tk_image = ImageTk.PhotoImage(self.current_image.resize((self.resized_w, self.resized_h), Image.Resampling.LANCZOS))
        self.canvas.image = self.tk_image
        self.redraw_boxes()

    def bind_shortcuts(self):
        self.bind("<Right>", lambda e: self.events.next_image() if self.mode != 'start' else None)
        self.bind("<Left>", lambda e: self.events.prev_image() if self.mode != 'start' else None)
        self.bind("<Control-s>", lambda e: self.events.save_annotations() if self.mode in ['annotation', 'correction'] else None)
        self.bind("<Control-z>", lambda e: self.events.undo() if self.mode in ['annotation', 'correction'] else None)
        self.bind("<Control-y>", lambda e: self.events.redo() if self.mode in ['annotation', 'correction'] else None)
        self.bind("<Escape>", self.reset_state)
        self.bind("<Delete>", self.events.delete_selected_box)
        self.bind("<Return>", self._on_enter_pressed)
        
        # クラス切り替えショートカット (0-9)
        for i in range(10):
            self.bind(str(i), self.change_class_by_key)

    def change_class_by_key(self, event):
        if self.mode not in ['annotation', 'correction'] or self.selected_box_id is None: return
        try:
            idx = int(event.keysym)
            if idx < len(self.class_names):
                self.events.change_class(self.selected_box_id, idx)
        except: pass

    def _on_enter_pressed(self, event=None):
        if self.mode not in ['annotation', 'correction']: return
        if self.is_dialog_active or time.time() < self.ignore_input_until:
            return
        self.events.save_and_next()

    def reset_state(self, _=None):
        if self.mouse_state == 'drawing' and self.temp_box_id: self.canvas.delete(self.temp_box_id)
        self.mouse_state = 'idle'; self.selected_box_id = None; self.selected_handle = None
        self.start_x, self.start_y = None, None
        if self.mode != 'start': self.redraw_boxes()

    def load_image(self): 
        self.reset_state()
        self.boxes = {} 
        self.events.load_image_from_index()

    def display_image_and_boxes(self, image_path):
        self.current_image = Image.open(image_path)
        self._update_canvas_image()
        self.update_info_labels()
        if hasattr(self, 'current_img_size_label'):
            self.current_img_size_label.configure(text=f"現在の画像サイズ: {format_bytes(os.path.getsize(image_path))}")

    def add_box(self, dx1, dy1, dx2, dy2, class_id):
        self.record_history()
        img_w, img_h = self.current_image.size
        ox1=int(round(min(dx1,dx2)*img_w/self.resized_w)); oy1=int(round(min(dy1,dy2)*img_h/self.resized_h))
        ox2=int(round(max(dx1,dx2)*img_w/self.resized_w)); oy2=int(round(max(dy1,dy2)*img_h/self.resized_h))
        new_id = max(self.boxes.keys()) + 1 if self.boxes else 0
        self.boxes[new_id] = {'coords': [ox1, oy1, ox2, oy2], 'class_id': class_id, 'items': {}}
        self.redraw_boxes(); self.update_box_list_display()

    def redraw_boxes(self):
        self.canvas.delete("all")
        
        # クロスヘアIDをリセット（キャンバスがクリアされたため）
        self.crosshair_v = None
        self.crosshair_h = None
        
        # 全消去時はボックスのアイテムID管理もクリアする
        for box in self.boxes.values():
            box['items'] = {}

        if not self.current_image: return
        self.canvas.create_image(0, 0, anchor="nw", image=self.canvas.image)
        if self.resized_w == 0: return
        img_w, img_h = self.current_image.size
        sorted_boxes = sorted(self.boxes.items(), key=lambda item: (item[1]['coords'][1], item[1]['coords'][0]))
        for i, (box_id, box) in enumerate(sorted_boxes):
            ox1, oy1, ox2, oy2 = box['coords']
            dx1 = int(round(ox1 * self.resized_w / img_w))
            dy1 = int(round(oy1 * self.resized_h / img_h))
            dx2 = int(round(ox2 * self.resized_w / img_w))
            dy2 = int(round(oy2 * self.resized_h / img_h))
            self._update_box_visuals(box_id, (dx1, dy1, dx2, dy2), index=i + 1)

    def _update_box_visuals(self, box_id, coords, index=None):
        if box_id not in self.boxes: return
        box = self.boxes[box_id]
        items = box.get('items', {})
        
        dx1, dy1, dx2, dy2 = coords
        color = self.get_color_for_class(box['class_id'])
        is_selected = (box_id == self.selected_box_id)
        box_width = self.box_line_width + 1 if is_selected else self.box_line_width

        # 1. Main Box
        if 'box' in items:
            self.canvas.coords(items['box'], dx1, dy1, dx2, dy2)
            self.canvas.itemconfig(items['box'], outline=color, width=box_width)
        else:
            items['box'] = self.canvas.create_rectangle(dx1, dy1, dx2, dy2, outline=color, width=box_width, tags=f"box_{box_id}")

        # 2. Text Label
        if 'text' in items:
            self.canvas.coords(items['text'], dx1, dy1 - 5)
            self.canvas.itemconfig(items['text'], text=self.class_names[box['class_id']], fill=color, font=(self.font_family, self.box_font_size, "bold"))
        else:
            items['text'] = self.canvas.create_text(dx1, dy1 - 5, text=self.class_names[box['class_id']], anchor="sw", fill=color, font=(self.font_family, self.box_font_size, "bold"))

        # 3. Index Label (Background & Text)
        if index is not None:
            bg_width = 18 + (len(str(index)) - 1) * 6
            if 'index_bg' in items:
                self.canvas.coords(items['index_bg'], dx1, dy1, dx1 + bg_width, dy1 + 14)
                self.canvas.itemconfig(items['index_bg'], fill=color)
            else:
                items['index_bg'] = self.canvas.create_rectangle(dx1, dy1, dx1 + bg_width, dy1 + 14, fill=color, outline="")
            
            if 'index_text' in items:
                self.canvas.coords(items['index_text'], dx1 + (bg_width / 2), dy1 + 7)
                self.canvas.itemconfig(items['index_text'], text=str(index))
            else:
                items['index_text'] = self.canvas.create_text(dx1 + (bg_width / 2), dy1 + 7, text=str(index), fill="white", font=(self.font_family, max(8, self.box_font_size - 3), "bold"))

        # 4. Handles (Only if selected)
        if self.mode in ['annotation', 'correction'] and is_selected:
            hs = 4
            # Define coords for all handles
            hc = {
                'tl': (dx1-hs, dy1-hs, dx1+hs, dy1+hs),
                'tm': ((dx1+dx2)/2-hs, dy1-hs, (dx1+dx2)/2+hs, dy1+hs),
                'tr': (dx2-hs, dy1-hs, dx2+hs, dy1+hs),
                'ml': (dx1-hs, (dy1+dy2)/2-hs, dx1+hs, (dy1+dy2)/2+hs),
                'mr': (dx2-hs, (dy1+dy2)/2-hs, dx2+hs, (dy1+dy2)/2+hs),
                'bl': (dx1-hs, dy2-hs, dx1+hs, dy2+hs),
                'bm': ((dx1+dx2)/2-hs, dy2-hs, (dx1+dx2)/2+hs, dy2+hs),
                'br': (dx2-hs, dy2-hs, dx2+hs, dy2+hs)
            }
            
            for name, h_coords in hc.items():
                if name in items:
                    self.canvas.coords(items[name], h_coords)
                    self.canvas.itemconfig(items[name], fill=color)
                else:
                    items[name] = self.canvas.create_rectangle(h_coords, fill=color, outline="white", tags=f"handle_{box_id}_{name}")

            # Rotation Handle
            rot_x, rot_y = (dx1+dx2)/2, dy1 - 25
            if 'rot_line' in items:
                self.canvas.coords(items['rot_line'], (dx1+dx2)/2, dy1, rot_x, rot_y)
                self.canvas.itemconfig(items['rot_line'], fill=color)
            else:
                items['rot_line'] = self.canvas.create_line((dx1+dx2)/2, dy1, rot_x, rot_y, fill=color, width=1)
            
            if 'rot_handle' in items:
                self.canvas.coords(items['rot_handle'], rot_x-5, rot_y-5, rot_x+5, rot_y+5)
                self.canvas.itemconfig(items['rot_handle'], fill=color)
            else:
                items['rot_handle'] = self.canvas.create_oval(rot_x-5, rot_y-5, rot_x+5, rot_y+5, fill=color, outline="white", tags=f"handle_{box_id}_rot")

        else:
            # If not selected, remove handles if they exist
            handle_keys = ['tl','tm','tr','ml','mr','bl','bm','br', 'rot_line', 'rot_handle']
            for k in handle_keys:
                if k in items:
                    self.canvas.delete(items[k])
                    del items[k]
                    
        box['items'] = items

    def update_crosshair(self, x, y):
        # キャンバスサイズ取得
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        
        # 縦線
        if self.crosshair_v and self.canvas.find_withtag(self.crosshair_v):
            self.canvas.coords(self.crosshair_v, x, 0, x, h)
            self.canvas.tag_raise(self.crosshair_v)
        else:
            self.crosshair_v = self.canvas.create_line(x, 0, x, h, fill="#FFFFFF", dash=(2, 4), tags="crosshair")

        # 横線
        if self.crosshair_h and self.canvas.find_withtag(self.crosshair_h):
            self.canvas.coords(self.crosshair_h, 0, y, w, y)
            self.canvas.tag_raise(self.crosshair_h)
        else:
            self.crosshair_h = self.canvas.create_line(0, y, w, y, fill="#FFFFFF", dash=(2, 4), tags="crosshair")

    def find_selection(self, x, y):
        for box_id, box in reversed(list(self.boxes.items())):
            items = box.get('items', {})
            if 'rot_handle' in items and self.canvas.find_withtag(items['rot_handle']):
                coords = self.canvas.coords(items['rot_handle'])
                if coords[0]-2 <= x <= coords[2]+2 and coords[1]-2 <= y <= coords[3]+2:
                    return box_id, 'rot'

            for key, item_id in items.items():
                if key not in ['box', 'text', 'rot_line', 'rot_handle'] and self.canvas.find_withtag(item_id):
                    coords = self.canvas.coords(item_id)
                    if len(coords) == 4 and coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                        return box_id, key
            
            if 'box' in items and self.canvas.find_withtag(items['box']):
                coords = self.canvas.coords(items['box'])
                if len(coords) == 4:
                    x1, y1, x2, y2 = coords
                    if (abs(x-x1)<5 or abs(x-x2)<5) and (y1-5<=y<=y2+5) or (abs(y-y1)<5 or abs(y-y2)<5) and (x1-5<=x<=x2+5): return box_id, None
        return None, None
    
    def move_box(self, box_id, dx, dy):
        for item_id in self.boxes[box_id].get('items', {}).values(): self.canvas.move(item_id, dx, dy)
    
    def resize_box(self, box_id, handle, x, y):
        items = self.boxes[box_id]['items']; 
        if 'box' not in items or not self.canvas.find_withtag(items['box']): return
        coords = self.canvas.coords(items['box']); x1, y1, x2, y2 = coords
        new_x1, new_y1, new_x2, new_y2 = x1, y1, x2, y2
        if 't' in handle: new_y1 = y
        if 'b' in handle: new_y2 = y
        if 'l' in handle: new_x1 = x
        if 'r' in handle: new_x2 = x
        if abs(new_x2 - new_x1) < 5 or abs(new_y2 - new_y1) < 5: return
        self._update_box_visuals(box_id, (min(new_x1,new_x2), min(new_y1,new_y2), max(new_x1,new_x2), max(new_y1,new_y2)), index=self.get_box_index(box_id))

    def update_original_coords(self):
        if self.selected_box_id is None or self.selected_box_id not in self.boxes: return
        img_w, img_h = self.current_image.size; items = self.boxes[self.selected_box_id]['items']
        if 'box' not in items or not self.canvas.find_withtag(items['box']): return
        dx1, dy1, dx2, dy2 = self.canvas.coords(items['box'])
        ox1=int(round(min(dx1,dx2)*img_w/self.resized_w)); oy1=int(round(min(dy1,dy2)*img_h/self.resized_h))
        ox2=int(round(max(dx1,dx2)*img_w/self.resized_w)); oy2=int(round(max(dy1,dy2)*img_h/self.resized_h))
        self.boxes[self.selected_box_id]['coords'] = [ox1, oy1, ox2, oy2]

    def record_history(self):
        self.undo_stack.append(copy.deepcopy(self.boxes)); 
        if len(self.undo_stack) > MAX_HISTORY: self.undo_stack.pop(0)
        self.redo_stack.clear()

    def update_info_labels(self):
        if self.current_image_index == -1: return
        total, current = len(self.image_files), self.current_image_index + 1
        self.image_info_label.configure(text=f"画像: {current} / {total}")
        filename = self.image_files[self.current_image_index]
        status = self.approval_status.get(filename, "未確認")
        color = "white"
        if status == "approved": color = "#00FF00"
        elif status == "rejected": color = "#FF0000"
        elif status == "fixed": color = "#FFD700" 
        status_text = f"ステータス: {status}"
        if status == "rejected": status_text += " (修正が必要です)"
        elif status == "fixed": status_text += " (再承認待ち)"
        self.status_display_label.configure(text=status_text, text_color=color)
        bg_color = "#330000" if status == "rejected" else ("#333300" if status == "fixed" else "gray")
        self.canvas.configure(bg=bg_color)
    
    def update_progress_display(self, _=None):
        if not self.image_dir: return
        annotated_count=sum(1 for f in self.image_files if os.path.exists(os.path.join(self.labels_dir, f"{os.path.splitext(f)[0]}.txt")))
        if self.session_start_count is None: self.session_start_count = annotated_count
        self.annotated_count_cache = annotated_count
        
        if hasattr(self, 'total_img_size_label'):
            img_total = getattr(self, 'total_image_size_cache', 0)
            self.total_img_size_label.configure(text=f"画像合計サイズ: {format_bytes(img_total)}")
            lbl_total = getattr(self, 'total_label_size_cache', 0)
            self.label_size_label.configure(text=f"ラベル合計サイズ: {format_bytes(lbl_total)}")

        total_files = len(self.image_files)
        target = self.target_count if self.target_count > 0 else (total_files if total_files > 0 else 1)
        ratio = min(1.0, annotated_count / target if target > 0 else 0)
        self.progress_label.configure(text=f"完了: {annotated_count} / {total_files}")
        if self.progress_style == "bar": self.progress_bar.set(ratio)
        else: self.draw_pie_chart(ratio)
        
        # 目標達成時の演出
        if self.target_count > 0 and annotated_count >= self.target_count:
            if not self.has_celebrated:
                self.has_celebrated = True
                self.trigger_gaming_effect()
        elif self.target_count > 0 and annotated_count < self.target_count:
            self.has_celebrated = False

    def stop_gaming_effect(self):
        if self.gaming_task:
            self.after_cancel(self.gaming_task)
            self.gaming_task = None
        
        # 演出前の色に戻す
        if self.original_colors:
            self.main_frame.configure(fg_color=self.original_colors["main"])
            self.left_frame.configure(fg_color=self.original_colors["left"])
            self.right_frame.configure(fg_color=self.original_colors["right"])

    def trigger_gaming_effect(self):
        self.log("★目標達成！Congratulations!★")
        self.stop_gaming_effect() # 既存の演出があれば停止してリセット
        
        # 現在の色を保存
        self.original_colors = {
            "main": self.main_frame.cget("fg_color"),
            "left": self.left_frame.cget("fg_color"),
            "right": self.right_frame.cget("fg_color")
        }

        duration = 5000 
        interval = 20  # 高速更新
        steps = duration // interval
        
        self._run_gaming_cycle(0, steps, interval)

    def _run_gaming_cycle(self, current_step, total_steps, interval):
        if current_step >= total_steps:
            self.stop_gaming_effect()
            return

        # 色相(Hue)を回転: 5秒間で5周 (speed multiplier = 5.0)
        hue = (current_step / total_steps * 5.0) % 1.0
        
        # HSV -> RGB (Saturation=0.3 で淡いパステルカラーに)
        rgb = colorsys.hsv_to_rgb(hue, 0.3, 1.0)
        
        r, g, b = [int(x * 255) for x in rgb]
        color_hex = f"#{r:02x}{g:02x}{b:02x}"
        
        try:
            self.main_frame.configure(fg_color=color_hex)
            self.left_frame.configure(fg_color=color_hex)
            self.right_frame.configure(fg_color=color_hex)
            
            # タスクIDを保存（キャンセル可能にするため）
            self.gaming_task = self.after(interval, lambda: self._run_gaming_cycle(current_step + 1, total_steps, interval))
        except Exception as e:
            self.stop_gaming_effect()
            print(f"Gaming effect error: {e}")
    
    def draw_pie_chart(self, ratio):
        self.pie_canvas.delete("all")
        self.pie_canvas.create_oval(20, 10, 120, 110, fill="#E0E0E0", outline="")
        angle = 360 * ratio
        if angle > 0:
            if angle == 360: self.pie_canvas.create_oval(20, 10, 120, 110, fill="#3B8ED0", outline="")
            else: self.pie_canvas.create_arc(20, 10, 120, 110, start=90, extent=-angle, fill="#3B8ED0", outline="")
        self.pie_canvas.create_text(70, 130, text=f"{ratio * 100:.2f}%", fill="black", font=("Arial", 14, "bold"))

    def update_box_list_display(self):
        if not hasattr(self, 'box_list_frame') or not self.box_list_frame.winfo_exists(): return
        for widget in self.box_list_frame.winfo_children(): widget.destroy()
        if not self.boxes or not self.class_names: return
        sorted_boxes = sorted(self.boxes.items(), key=lambda item: (item[1]['coords'][1], item[1]['coords'][0]))
        for i, (box_id, box) in enumerate(sorted_boxes):
            coords, class_id = box['coords'], box['class_id']
            w, h = coords[2] - coords[0], coords[3] - coords[1]
            text = f"{i+1}: {self.class_names[class_id]} ({w}x{h})"
            
            is_selected = (box_id == self.selected_box_id)
            
            # 選択されている場合は背景色を濃く（ハイライト）
            bg_color = ("#D0D0D0", "#404040") if is_selected else "transparent"
            text_color = self.get_color_for_class(class_id)
            
            # ボタン化してクリック可能に
            btn = ctk.CTkButton(
                self.box_list_frame, 
                text=text, 
                text_color=text_color, 
                fg_color=bg_color,
                hover_color=("gray75", "gray30"),
                anchor="w",
                height=24, # リストを見やすくするため少しコンパクトに
                font=ctk.CTkFont(family=self.font_family, size=12),
                command=lambda bid=box_id: self.select_box_from_list(bid)
            )
            btn.pack(fill="x", padx=5, pady=2)
            
    def select_box_from_list(self, box_id):
        # リストからボックスを選択したときの処理
        self.selected_box_id = box_id
        self.selected_handle = None # ハンドル選択はリセット
        self.mouse_state = 'idle' # マウス状態をリセット
        self.redraw_boxes() # キャンバスを再描画（ハンドル表示）
        self.update_box_list_display() # リスト表示を更新（ハイライト）
        
    def get_box_index(self, box_id):
        sorted_ids = [item[0] for item in sorted(self.boxes.items(), key=lambda item: (item[1]['coords'][1], item[1]['coords'][0]))]
        try: return sorted_ids.index(box_id) + 1
        except ValueError: return None
        
    def ask_class(self):
        if not self.class_names: return None
        self.is_dialog_active = True
        result = {'class_id': None}

        try:
            dialog = ctk.CTkToplevel(self)
            dialog.title("クラス選択")
            dialog.attributes("-topmost", True)
            
            mx, my = self.winfo_pointerx(), self.winfo_pointery()
            w, h = 200, 300
            s_w, s_h = self.winfo_screenwidth(), self.winfo_screenheight()
            x_pos = s_w - w - 10 if mx + w + 10 > s_w else mx + 10
            y_pos = s_h - h - 10 if my + h + 10 > s_h else my + 10
            dialog.geometry(f"{w}x{h}+{x_pos}+{y_pos}")
            
            val = tkinter.IntVar(value=0)
            
            scroll_frame = ctk.CTkScrollableFrame(dialog); scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
            radios = []
            for i, name in enumerate(self.class_names):
                r = ctk.CTkRadioButton(scroll_frame, text=f"{i}: {name}", variable=val, value=i, font=ctk.CTkFont(family=self.font_family))
                r.pack(anchor="w", padx=5, pady=2); radios.append(r)
            
            def confirm(_=None):
                result['class_id'] = val.get()
                self.ignore_input_until = time.time() + 0.5 
                self.cleanup_bindings()
                dialog.destroy()
            
            def on_close():
                self.cleanup_bindings()
                dialog.destroy()
            
            def on_scroll(event):
                if event.delta:
                    current = val.get()
                    if event.delta > 0: new_val = max(0, current - 1)
                    else: new_val = min(len(self.class_names) - 1, current + 1)
                    val.set(new_val)
            
            self.bind_all("<MouseWheel>", on_scroll)
            self.bind_all("<Button-2>", confirm)
            self.bind_all("<Return>", confirm)
            
            def cleanup_bindings_func():
                self.unbind_all("<MouseWheel>")
                self.unbind_all("<Button-2>")
                self.unbind_all("<Return>")
                self.bind("<Return>", self._on_enter_pressed)
            
            self.cleanup_bindings = cleanup_bindings_func
            
            ctk.CTkButton(dialog, text="決定 (Enter/Click)", command=confirm, font=ctk.CTkFont(family=self.font_family)).pack(fill="x", padx=5, pady=5)
            
            dialog.focus_force()
            dialog.protocol("WM_DELETE_WINDOW", on_close)
            
            self.wait_window(dialog)
            return result['class_id']
            
        finally:
            self.is_dialog_active = False

    def get_color_for_class(self, class_id):
        colors = ["#FF3838", "#00C2FF", "#FF9D97", "#FF701F", "#FFB21D", "#CFD231", "#48F90A", "#92CC17", "#3DDB86", "#1A9334", "#00D4BB",
                  "#2C99A8", "#344593", "#6473FF", "#0018EC", "#8438FF", "#520085", "#CB38FF", "#FF95C8", "#FF37C7"]
        return colors[class_id % len(colors)]
    
    def _update_drawing_options(self, _=None):
        self.box_line_width = int(self.line_width_slider.get()); self.box_font_size = int(self.font_size_slider.get())
        self.redraw_boxes()