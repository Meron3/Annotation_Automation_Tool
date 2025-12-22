# Annotation Automation Tool

Python (Tkinter/CustomTkinter) で動作する、YOLOv8を組み込んだ画像アノテーションツール自動化ツールです。YOLOによってバウンディングボックスを自動で設置するアノテーション機能に加え、**1. アノテーション → 2. 承認(Review) → 3. 修正(Fix) → 4. 再承認**(3, 4はループ可)の機能を実装しています。

詳細は以下の記事を読んでください。


--以下執筆途中--

![Screenshot](https://via.placeholder.com/800x450.png?text=App+Screenshot+Here)
## ✨ 主な機能

* **🚀 自動アノテーション:** YOLOv8モデル (`.pt`) を使用して、未ラベルの画像に自動でバウンディングボックスを付与。
* **🔄 ワークフロー管理:**
    * **Annotation:** 新規作成・自動付与
    * **Approval:** アノテーション結果の承認/却下 (OK/NG)
    * **Correction:** 却下された画像(NG)のみを抽出して修正
    * **Re-approval:** 修正された画像の最終確認
* **🖱️ 直感的な操作:**
    * ドラッグによるボックス作成・移動・リサイズ
    * クロスヘア（十字カーソル）による精密な位置合わせ
    * ショートカットキーによる高速操作
* **📊 ダッシュボード:** 進捗状況、ラベル数、NG数などをリアルタイムで可視化。
* **🎨 モダンなUI:** CustomTkinterを使用したダークモード対応の見やすいインターフェース。

## 🛠️ インストール

### 必要要件
* Python 3.8+
* 推奨: GPU環境 (YOLOv8の高速化のため。CPUでも動作可能)

### 依存ライブラリのインストール
以下のコマンドで必要なライブラリをインストールしてください。

```bash
pip install ultralytics customtkinter pillow pyyaml