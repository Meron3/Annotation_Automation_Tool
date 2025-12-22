# event_handlers.py
import os
import shutil
import tkinter
import tkinter.messagebox as msgbox
import tkinter.filedialog as filedialog
from utils import load_class_names, load_approval_status, save_status
import json
import copy
import datetime
import time

class EventHandlers:
    def __init__(self, app):
        self.app = app

    def select_project_folder(self):
        project_dir = filedialog.askdirectory(title="ステップ1: プロジェクトフォルダを選択")
        if not project_dir: return
        class_names = load_class_names(project_dir)
        if class_names is None: self.app.log("エラー: classes.yamlの読み込みに失敗しました。"); return
        self.app.project_dir = project_dir
        self.app.class_names = class_names
        self.app.project_path_label.configure(text=f"プロジェクト: {os.path.basename(project_dir)}")
        self.app.select_image_folder_button.configure(state="normal")
        self.app.log(f"プロジェクトを読込: {project_dir}")

    def select_image_folder(self):
        image_dir = filedialog.askdirectory(title="ステップ2: 対象の画像フォルダを選択")
        if not image_dir: return
        self.app.image_dir = image_dir
        parent_dir = os.path.dirname(os.path.abspath(image_dir))
        self.app.labels_dir = os.path.join(parent_dir, "labels")
        os.makedirs(self.app.labels_dir, exist_ok=True)
        image_dir_name = os.path.basename(os.path.normpath(image_dir))
        self.app.image_path_label.configure(text=f"対象フォルダ: {image_dir_name}")
        
        self.app.approval_status, self.app.status_file_path = load_approval_status(self.app.project_dir, image_dir_name)
        
        self.app.all_image_files = sorted([f for f in os.listdir(image_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        
        total_size = sum(os.path.getsize(os.path.join(image_dir, f)) for f in self.app.all_image_files)
        self.app.total_image_size_cache = total_size
        total_label_size = 0
        for f in self.app.all_image_files:
            txt_path = os.path.join(self.app.labels_dir, f"{os.path.splitext(f)[0]}.txt")
            if os.path.exists(txt_path):
                total_label_size += os.path.getsize(txt_path)
        self.app.total_label_size_cache = total_label_size

        self.update_dashboard_stats()
        self.app.start_annotation_button.configure(state="normal"); self.app.start_approval_button.configure(state="normal")
        self.app.start_correction_button.configure(state="normal"); self.app.start_reapproval_button.configure(state="normal")
        if hasattr(self.app, 'export_button'): self.app.export_button.configure(state="normal")
        self.app.log(f"画像フォルダをロード: {image_dir_name} ({len(self.app.all_image_files)}枚)")
        self.app.session_start_count = None

    def update_dashboard_stats(self):
        total = len(self.app.all_image_files); annotated = 0; approved = 0; rejected = 0; fixed = 0
        for f in self.app.all_image_files:
            if os.path.exists(os.path.join(self.app.labels_dir, f"{os.path.splitext(f)[0]}.txt")): annotated += 1
            
            status = self.app.approval_status.get(f)
            if status == "approved": approved += 1
            elif status == "rejected": rejected += 1
            elif status == "fixed": fixed += 1
            
        self.app.stats_labels['total'].configure(text=str(total)); self.app.stats_labels['annotated'].configure(text=str(annotated))
        self.app.stats_labels['approved'].configure(text=str(approved)); self.app.stats_labels['rejected'].configure(text=str(rejected))
        self.app.stats_labels['fixed'].configure(text=str(fixed))
        
        from utils import format_bytes
        img_size_str = format_bytes(getattr(self.app, 'total_image_size_cache', 0))
        lbl_size_str = format_bytes(getattr(self.app, 'total_label_size_cache', 0))
        if 'total_size' in self.app.stats_labels:
            self.app.stats_labels['total_size'].configure(text=f"合計容量 (画像: {img_size_str} / ラベル: {lbl_size_str})")

        self.app.start_correction_button.configure(fg_color="#D90000" if rejected > 0 else "#3B8ED0", hover_color="#8F0000" if rejected > 0 else "#36719F")
        self.app.start_reapproval_button.configure(fg_color="#E59100" if fixed > 0 else "#3B8ED0", hover_color="#B37100" if fixed > 0 else "#36719F")

    def start_mode(self, mode):
        if not self.app.image_dir: return
        self.app.start_time = time.time()
        self.app.session_start_count = None 
        target_images = []
        if mode == 'annotation': target_images = self.app.all_image_files
        elif mode == 'approval':
            target_images = [f for f in self.app.all_image_files if os.path.exists(os.path.join(self.app.labels_dir, f"{os.path.splitext(f)[0]}.txt")) and self.app.approval_status.get(f) != "approved"]
            if not target_images: msgbox.showinfo("案内", "未承認のアノテーション済み画像はありません。"); return
        elif mode == 'correction':
            target_images = [f for f in self.app.all_image_files if self.app.approval_status.get(f) == "rejected"]
            if not target_images: msgbox.showinfo("案内", "修正が必要な画像(NG)はありません。"); return
        elif mode == 'reapproval':
            target_images = [f for f in self.app.all_image_files if self.app.approval_status.get(f) == "fixed"]
            if not target_images: msgbox.showinfo("案内", "再承認待ち(Fixed)の画像はありません。"); return

        self.app.image_files = target_images
        image_dir_name = os.path.basename(os.path.normpath(self.app.image_dir))
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{timestamp}_{image_dir_name}_{mode}.log"
        self.app.log_file_path = os.path.join(self.app.project_dir, log_filename)
        session_path = os.path.join(self.app.project_dir, f".{image_dir_name}_session.json")
        if os.path.exists(session_path):
            if msgbox.askyesno("作業再開", "前回のセッションデータがあります。復元しますか？"): self.load_project_session(session_path, mode); return
        self.app.switch_to_main_ui(mode); self.app.current_image_index = 0
        self.app.load_image(); self.app.update_progress_display()
        self.app.log(f"モード開始: {mode} (対象: {len(target_images)}枚)")

    def start_annotation_mode(self): self.start_mode('annotation')
    def start_approval_mode(self): self.start_mode('approval')
    def start_correction_mode(self): self.start_mode('correction')
    def start_reapproval_mode(self): self.start_mode('reapproval')

    def save_annotations(self):
        if self.app.current_image_index == -1: return
        img_w, img_h = self.app.current_image.size
        base_name = os.path.splitext(self.app.image_files[self.app.current_image_index])[0]
        txt_path = os.path.join(self.app.labels_dir, f"{base_name}.txt")
        
        old_size = 0
        if os.path.exists(txt_path):
            old_size = os.path.getsize(txt_path)
            
        with open(txt_path, "w") as f:
            sorted_boxes = sorted(self.app.boxes.values(), key=lambda b: (b['coords'][1], b['coords'][0]))
            for box in sorted_boxes:
                x1, y1, x2, y2, class_id = box['coords'] + [box['class_id']]
                dw, dh = 1. / img_w, 1. / img_h
                x_center, y_center = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                width, height = x2 - x1, y2 - y1
                f.write(f"{class_id} {x_center*dw:.6f} {y_center*dh:.6f} {width*dw:.6f} {height*dh:.6f}\n")
        
        new_size = os.path.getsize(txt_path)
        if hasattr(self.app, 'total_label_size_cache'):
            self.app.total_label_size_cache = self.app.total_label_size_cache - old_size + new_size

        self.app.log(f"アノテーション保存: {txt_path}")
        filename = self.app.image_files[self.app.current_image_index]
        if self.app.approval_status.get(filename) == "rejected":
             self.app.approval_status[filename] = "fixed"
             save_status(self.app.status_file_path, self.app.approval_status)
             self.app.update_info_labels()
        self.app.update_progress_display()

    def save_and_next(self, _=None):
        if self.app.mode in ['annotation', 'correction']: self.save_annotations(); self.next_image()
    
    def save_project_session(self, silent=False):
        if not self.app.project_dir or not self.app.image_dir: return
        image_dir_name = os.path.basename(os.path.normpath(self.app.image_dir))
        session_path = os.path.join(self.app.project_dir, f".{image_dir_name}_session.json")
        session_data = { "project_dir": self.app.project_dir, "image_dir": self.app.image_dir, "labels_dir": self.app.labels_dir, "current_image_index": self.app.current_image_index, "boxes": self.app.boxes, "undo_stack": self.app.undo_stack, "redo_stack": self.app.redo_stack, "approval_status": self.app.approval_status, "options": { "line_width": self.app.box_line_width, "font_size": self.app.box_font_size, "log_lines": self.app.log_visible_lines, "target_count": self.app.target_count, "progress_style": self.app.progress_style } }
        with open(session_path, 'w') as f: json.dump(session_data, f, indent=2)
        if not silent: self.app.log(f"プロジェクトを途中保存しました: {session_path}")

    def load_project_session(self, session_path, mode):
        with open(session_path, 'r') as f: data = json.load(f)
        self.app.project_dir = data["project_dir"]; self.app.image_dir = data["image_dir"]; self.app.labels_dir = data["labels_dir"]
        self.app.current_image_index = data["current_image_index"]
        self.app.boxes = {int(k): v for k, v in data["boxes"].items()}
        self.app.undo_stack = data["undo_stack"]; self.app.redo_stack = data["redo_stack"]
        self.app.approval_status = data.get("approval_status", data.get("annotation_status", {}))
        options = data.get("options", {})
        self.app.box_line_width = options.get("line_width", 2); self.app.box_font_size = options.get("font_size", 12)
        self.app.log_visible_lines = options.get("log_lines", 4); self.app.target_count = options.get("target_count", 0)
        self.app.progress_style = options.get("progress_style", "bar")
        self.app.switch_to_main_ui(mode)
        if self.app.current_image_index >= len(self.app.image_files): self.app.current_image_index = 0
        if mode in ['approval', 'reapproval'] and self.app.current_image_index == len(self.app.image_files) - 1: self.app.current_image_index = 0
        self.app.load_image(); self.app.update_progress_display()
        self.app.log(f"前回の作業状態を復元しました ({mode}): {session_path}")

    def prev_image(self):
        if self.app.current_image_index > 0: self.app.current_image_index -= 1; self.app.load_image()

    def next_image(self):
        if self.app.current_image_index < len(self.app.image_files) - 1: self.app.current_image_index += 1; self.app.load_image()
        else: msgbox.showinfo("案内", "これが最後の画像です。")
    
    def approve_annotation(self): self.update_status("approved"); self.save_project_session(silent=True); self.next_image()
    def reject_annotation(self): self.update_status("rejected"); self.save_project_session(silent=True); self.next_image()

    def update_status(self, status):
        if self.app.current_image_index == -1: return
        filename = self.app.image_files[self.app.current_image_index]
        self.app.approval_status[filename] = status
        save_status(self.app.status_file_path, self.app.approval_status)
        self.app.update_info_labels()

    def export_approved_dataset(self):
        if not self.app.project_dir or not self.app.image_dir: msgbox.showerror("エラー", "プロジェクトと画像フォルダが選択されていません。"); return
        target_image_dir = self.app.image_dir; status_map = self.app.approval_status
        if not status_map: msgbox.showwarning("警告", "ステータス情報が見つかりません。"); return
        export_root = filedialog.askdirectory(title="エクスポート先のフォルダを作成・選択してください")
        if not export_root: return
        dest_images_dir = os.path.join(export_root, "images"); dest_labels_dir = os.path.join(export_root, "labels")
        os.makedirs(dest_images_dir, exist_ok=True); os.makedirs(dest_labels_dir, exist_ok=True)
        copy_count = 0; parent_dir = os.path.dirname(os.path.abspath(target_image_dir)); source_labels_dir = os.path.join(parent_dir, "labels") 
        for filename, status in status_map.items():
            if status == "approved":
                src_img = os.path.join(target_image_dir, filename); dst_img = os.path.join(dest_images_dir, filename)
                label_name = os.path.splitext(filename)[0] + ".txt"
                src_label = os.path.join(source_labels_dir, label_name); dst_label = os.path.join(dest_labels_dir, label_name)
                if os.path.exists(src_img) and os.path.exists(src_label):
                    try: shutil.copy2(src_img, dst_img); shutil.copy2(src_label, dst_label); copy_count += 1
                    except Exception as e: print(f"Error copying {filename}: {e}")
        msgbox.showinfo("完了", f"エクスポートが完了しました。\n\n承認済み: {copy_count}件\n保存先: {export_root}")
        self.app.log(f"データセットのエクスポート完了: {copy_count}件 -> {export_root}")
    
    def on_mouse_press(self, event):
        if self.app.mode in ['approval', 'reapproval']: return
        
        # 既存ボックスの選択判定
        self.app.selected_box_id, self.app.selected_handle = self.app.find_selection(event.x, event.y)
        
        # 回転ハンドル
        if self.app.selected_handle == 'rot':
            self.app.mouse_state = 'rotating'
            self.app.record_history()
            return

        # リサイズまたは移動
        if self.app.selected_box_id is not None:
            self.app.mouse_state = 'resizing' if self.app.selected_handle else 'moving'
            self.app.start_x, self.app.start_y = event.x, event.y
            self.app.record_history()
            self.app.redraw_boxes()
            self.app.update_box_list_display()
            return 

        # --- 新規作成モード (クリック-移動-クリック) ---
        if self.app.mouse_state == 'idle':
            # 1回目のクリック: 描画開始
            self.app.mouse_state = 'drawing'
            self.app.start_x, self.app.start_y = event.x, event.y
            
            # 黄色・太さ2の実線
            self.app.temp_box_id = self.app.canvas.create_rectangle(
                event.x, event.y, event.x, event.y, 
                outline="yellow", width=2
            )
            self.app.selected_box_id = None 
            self.app.update_box_list_display()
            return
        
        elif self.app.mouse_state == 'drawing':
            # 2回目のクリック: 描画確定
            
            # ダイアログ表示中の誤描画を防ぐため、即座にdrawing状態を解除
            self.app.mouse_state = 'processing'
            
            x1, y1 = self.app.start_x, self.app.start_y
            x2, y2 = event.x, event.y
            
            if self.app.temp_box_id: self.app.canvas.delete(self.app.temp_box_id)
            self.app.temp_box_id = None
            
            # 座標正規化
            min_x, min_y = min(x1, x2), min(y1, y2)
            max_x, max_y = max(x1, x2), max(y1, y2)

            # 黄色い確定線を描画
            prelim_box_id = self.app.canvas.create_rectangle(
                min_x, min_y, max_x, max_y, 
                outline="yellow", width=2
            )
            
            # ★重要: ダイアログが出る前に画面を更新
            self.app.canvas.update()
            
            class_id = self.app.ask_class()
            self.app.canvas.delete(prelim_box_id)
            
            if class_id is not None:
                self.app.add_box(x1, y1, x2, y2, class_id)
                self.app.log(f"新規ボックス ({self.app.class_names[class_id]}) を追加しました。")
            else:
                self.app.redraw_boxes()
                
            self.app.mouse_state = 'idle'
            self.app.start_x, self.app.start_y = None, None

    def on_mouse_move(self, event):
        # クロスヘア更新（全モード共通）
        self.app.update_crosshair(event.x, event.y)

        if self.app.mode in ['approval', 'reapproval']: self.app.canvas.config(cursor=""); return
        
        # --- 描画中の線更新 ---
        if self.app.mouse_state == 'drawing':
            # temp_box_id が（リサイズ等で）消えていた場合に再生成
            if self.app.temp_box_id is None or not self.app.canvas.find_withtag(self.app.temp_box_id):
                self.app.temp_box_id = self.app.canvas.create_rectangle(
                    self.app.start_x, self.app.start_y, event.x, event.y,
                    outline="yellow", width=2
                )

            x1, y1 = self.app.start_x, self.app.start_y
            x2, y2 = event.x, event.y
            
            # 座標を正規化してセット。tag_raise で最前面へ
            self.app.canvas.coords(
                self.app.temp_box_id, 
                min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
            )
            self.app.canvas.tag_raise(self.app.temp_box_id)
            return

        if self.app.mouse_state == 'rotating':
            if self.app.selected_box_id is None: return
            coords = self.app.boxes[self.app.selected_box_id]['coords']
            x1, y1, x2, y2 = coords
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            dx = event.x - cx; dy = event.y - cy
            w = abs(x2 - x1); h = abs(y2 - y1)
            target_is_horizontal = abs(dx) > abs(dy)
            current_is_horizontal = w > h
            if target_is_horizontal != current_is_horizontal:
                new_w, new_h = h, w
                new_x1 = int(cx - new_w / 2); new_y1 = int(cy - new_h / 2)
                new_x2 = int(cx + new_w / 2); new_y2 = int(cy + new_h / 2)
                self.app.boxes[self.app.selected_box_id]['coords'] = [new_x1, new_y1, new_x2, new_y2]
                self.app.redraw_boxes()
            return

        box_id, handle = self.app.find_selection(event.x, event.y)
        if handle == 'rot': self.app.canvas.config(cursor="exchange")
        elif handle: self.app.canvas.config(cursor="sizing")
        elif box_id is not None: self.app.canvas.config(cursor="fleur")
        else: self.app.canvas.config(cursor="tcross")
        
        if self.app.mouse_state == 'moving':
            dx, dy = event.x - self.app.start_x, event.y - self.app.start_y
            self.app.move_box(self.app.selected_box_id, dx, dy)
            self.app.start_x, self.app.start_y = event.x, event.y
        elif self.app.mouse_state == 'resizing':
            self.app.resize_box(self.app.selected_box_id, self.app.selected_handle, event.x, event.y)

    def on_mouse_release(self, event):
        if self.app.mouse_state in ['moving', 'resizing', 'rotating']:
            self.app.update_original_coords()
            self.app.mouse_state = 'idle'
            self.app.update_box_list_display()

    def on_right_click(self, event):
        if self.app.mode in ['approval', 'reapproval']: return
        box_id, _ = self.app.find_selection(event.x, event.y)
        if box_id is None: return
        self.app.selected_box_id = box_id
        self.app.update_box_list_display()
        context_menu = tkinter.Menu(self.app.canvas, tearoff=0)
        class_submenu = tkinter.Menu(context_menu, tearoff=0)
        for i, name in enumerate(self.app.class_names):
            class_submenu.add_command(label=name, command=lambda cid=i: self.change_class(box_id, cid))
        context_menu.add_cascade(label="クラスを変更", menu=class_submenu)
        context_menu.add_separator()
        context_menu.add_command(label="削除", command=lambda: self.delete_box(box_id))
        try: context_menu.tk_popup(event.x_root, event.y_root)
        finally: context_menu.grab_release()

    def change_class(self, box_id, new_class_id):
        self.app.record_history()
        self.app.boxes[box_id]['class_id'] = new_class_id
        self.app.redraw_boxes(); self.app.update_box_list_display()
        self.app.log(f"ボックス {self.app.get_box_index(box_id)} のクラスを変更しました。")

    def delete_box(self, box_id):
        self.app.record_history()
        if box_id in self.app.boxes: del self.app.boxes[box_id]
        self.app.redraw_boxes(); self.app.update_box_list_display()
        self.app.log(f"ボックスを削除しました。")

    def delete_selected_box(self, _=None):
        if self.app.mode in ['annotation', 'correction'] and self.app.selected_box_id is not None:
            self.delete_box(self.app.selected_box_id); self.app.reset_state()
            
    def undo(self, _=None):
        if self.app.mode not in ['annotation', 'correction'] or len(self.app.undo_stack) <= 1: self.app.log("これ以上元に戻せません。"); return
        current_state = self.app.undo_stack.pop()
        self.app.redo_stack.append(current_state)
        self.app.boxes = copy.deepcopy(self.app.undo_stack[-1])
        self.app.redraw_boxes(); self.app.update_box_list_display()
        self.app.log("元に戻しました (Ctrl+Z)。")

    def redo(self, _=None):
        if self.app.mode not in ['annotation', 'correction'] or not self.app.redo_stack: self.app.log("これ以上やり直せません。"); return
        restored_state = self.app.redo_stack.pop()
        self.app.undo_stack.append(restored_state)
        self.app.boxes = copy.deepcopy(restored_state)
        self.app.redraw_boxes(); self.app.update_box_list_display()
        self.app.log("やり直しました (Ctrl+Y)。")

    def load_image_from_index(self):
        if not (0 <= self.app.current_image_index < len(self.app.image_files)): return
        image_path = os.path.join(self.app.image_dir, self.app.image_files[self.app.current_image_index])
        base_name = os.path.splitext(self.app.image_files[self.app.current_image_index])[0]
        txt_path = os.path.join(self.app.labels_dir, f"{base_name}.txt")
        self.app.log(f"表示中: {image_path}")
        self.app.undo_stack.clear(); self.app.redo_stack.clear(); self.app.boxes = {}
        if os.path.exists(txt_path): self.load_yolo_annotations(txt_path)
        else:
            if self.app.mode == 'annotation': self.run_auto_annotation(image_path)
        self.app.undo_stack.append(copy.deepcopy(self.app.boxes))
        self.app.display_image_and_boxes(image_path); self.app.update_box_list_display()

    def run_auto_annotation(self, image_path):
        results = self.app.model(image_path, verbose=False)
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0]); class_id = int(box.cls[0])
                if class_id < len(self.app.class_names):
                    new_id = max(self.app.boxes.keys()) + 1 if self.app.boxes else 0
                    self.app.boxes[new_id] = {'coords': [x1, y1, x2, y2], 'class_id': class_id, 'items': {}}
    
    def load_yolo_annotations(self, txt_path):
        from PIL import Image
        try:
            image_filename = os.path.basename(txt_path).replace('.txt', '')
            img_path = next(p for ext in ['.jpg', '.png', '.jpeg'] if os.path.exists(p := os.path.join(self.app.image_dir, f"{image_filename}{ext}")))
            img_w, img_h = Image.open(img_path).size
        except StopIteration: return
        with open(txt_path, 'r') as f:
            for i, line in enumerate(f):
                parts = line.strip().split(); class_id = int(parts[0])
                x_center, y_center, width, height = map(float, parts[1:])
                x_center_abs, width_abs = x_center * img_w, width * img_w
                y_center_abs, height_abs = y_center * img_h, height * img_h
                x1 = int(x_center_abs - width_abs / 2); y1 = int(y_center_abs - height_abs / 2)
                x2 = int(x_center_abs + width_abs / 2); y2 = int(y_center_abs + height_abs / 2)
                self.app.boxes[i] = {'coords': [x1, y1, x2, y2], 'class_id': class_id, 'items': {}}