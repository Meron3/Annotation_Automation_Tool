# Annotation Automation Tool

Python (Tkinter/CustomTkinter) で動作する、YOLOv8を組み込んだ画像アノテーションツール自動化ツールです。YOLOによってバウンディングボックスを自動で設置するアノテーション機能に加え、**1. アノテーション → 2. 承認(Review) → 3. 修正(Fix) → 4. 再承認**(3, 4はループ可)の機能を実装しています。

詳細は以下の記事をお読みください。


![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3938248/b9ac1084-7b5b-482f-8cad-aa3a05045fad.png)
## 主な機能

* **自動アノテーション**： YOLOv8モデル (`.pt`) を使用して、未ラベルの画像に自動でバウンディングボックスを付与します。
* **ワークフロー管理:**
    * **Annotation:** 新規作成・自動付与
    * **Approval:** アノテーション結果の承認/却下 (OK/NG)
    * **Correction:** 却下された画像(NG)のみを抽出して修正
    * **Re-approval:** 修正された画像の最終確認
* **操作方法:**
    * ドラッグによるボックス作成・移動・リサイズ
    * ショートカットキーによる高速操作の実装

## インストール
本リポジトリからコード一式をダウンロードします(Windows PowerShellでの実行例)。

https://github.com/Meron3/Annotation_Automation_Tool

```terminal
git clone https://github.com/Meron3/Annotation_Automation_Tool
cd .\Annotation_Automation_Tool\
```
仮想環境を作ります(名前は自由です)。
```terminal
python3 -m venv Annotation
```
仮想環境を有効化します。

**Linuxの場合**
```terminal
source Annotation/bin/activate
```
**Windowsの場合**
```terminal
.\Annotation\Scripts\activate
```

以下のライブラリをインストールします。
```terminal
pip install ultralytics customtkinter pillow pyyaml
```
main.pyを実行します。
```
cd .\code\
python .\main.py
```


### 必要要件
* WindowsまたはUbuntu(バージョン不問)
* Anacondaでも可
* Python 3.8+
* 推奨: GPU環境 (YOLOv8の高速化のため。CPUでも動作可能)
