# main.py
from app_ui import AnnotationApp

# --- 設定 ---
# 自動アノテーションに使うYOLOv8転移学習モデルのパス
# オリジナルのモデルを使わない場合は 'yolov8n.pt' のままでOK
# YOUR_MODEL_PATH = "best.pt" 
YOUR_MODEL_PATH = "yolov8n.pt" 

if __name__ == "__main__":
    app = AnnotationApp(model_path=YOUR_MODEL_PATH)
    app.mainloop()