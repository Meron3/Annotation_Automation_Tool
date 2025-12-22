# utils.py
import os
import yaml
import json

def format_bytes(size):
    if size == 0: return "0 B"
    power, n = 1024, 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB'}
    while size > power and n < len(power_labels) -1 :
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"

def load_class_names(project_dir):
    try:
        with open(os.path.join(project_dir, "classes.yaml"), 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            names_data = data.get('names') 

            if isinstance(names_data, dict):
                # {0: 'person', 1: 'car'} のような辞書形式の場合
                # キーでソートして、値のリストを返す
                return [names_data[i] for i in sorted(names_data.keys())]
            elif isinstance(names_data, list):
                # ['person', 'car'] のようなリスト形式の場合
                return names_data
            else:
                print(f"Error: classes.yaml内の'names'の形式が正しくありません。")
                return None
    except Exception as e:
        print(f"Error: {project_dir} 内の classes.yaml の読み込みに失敗しました。 {e}")
        return None

def load_approval_status(project_dir, image_dir_name):
    status_filename = f".{image_dir_name}_approval.json"
    status_file_path = os.path.join(project_dir, status_filename)
    try:
        with open(status_file_path, 'r') as f:
            return json.load(f), status_file_path
    except FileNotFoundError:
        return {}, status_file_path

def load_status(project_dir, image_dir_name):
    # 旧互換性維持のため残していますが、基本は load_approval_status を使用
    status_filename = f".{image_dir_name}_status.json"
    status_file_path = os.path.join(project_dir, status_filename)
    try:
        with open(status_file_path, 'r') as f:
            return json.load(f), status_file_path
    except FileNotFoundError:
        return {}, status_file_path

def save_status(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)