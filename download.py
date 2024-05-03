import sqlite3, os, subprocess, re, datetime, threading, asyncio
import tkinter as tk
from tkinter import ttk, filedialog
from concurrent.futures import ThreadPoolExecutor


db_file = "models.db"
uuids_to_download = []
files_to_download = {}


# 全局变量，用于存储进度条变量
global_progress_var = None
global_num_of_files_to_download = 0

# 添加当前页码变量
# current_page = None
# max_page = None


def get_tag_id_from_name(tag_name):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tag WHERE name = ?", (tag_name,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]  # 返回tag_id
    else:
        return None


def get_unique_values(table_name, column_name):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(f"SELECT DISTINCT {column_name} FROM {table_name}")
    values = [row[0] for row in cursor.fetchall()]
    conn.close()
    values.insert(0, "All")
    if table_name == "tag":
        values.insert(1, "None")
    return values


def query_data_task(combobox_vars, root, page=1, page_size=100):
    tree = root.nametowidget(".middle.tree_frame.tree")
    label_msg = root.nametowidget(".bottom.label_msg")
    button2 = root.nametowidget(".middle.button_frame.download_button")
    # button_prev = root.nametowidget(".middle.tree_frame.page_button_frame.prev")
    # button_next = root.nametowidget(".middle.tree_frame.page_button_frame.next")
    label_paging = root.nametowidget(".middle.tree_frame.paging_frame.label_paging")
    combo_paging = root.nametowidget(".middle.tree_frame.paging_frame.combo_paging")

    # 清空Treeview中的所有数据
    for i in tree.get_children():
        tree.delete(i)

    values = {}
    for label, var in combobox_vars.items():
        values[label] = var.get()
        print(f"{label} {var.get()}")

    model_type = values["Model Type:"]
    base_type = values["Base Type:"]
    category = values["Catetory:"]
    older_than = int(values["Older than (days):"])
    num_of_downloads = int(values["Num of downloads:"])

    # 连接数据库并查询
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 构建查询条件
    conditions = []
    params = []
    if model_type != "All":
        conditions.append("model.type_name = ?")
        params.append(model_type)

    if base_type != "All":
        conditions.append("model.base_type_name = ?")
        params.append(base_type)

    if category != "All":
        conditions.append("model.tags LIKE ?")
        if category == "None":
            params.append("[]")
        else:
            selected_tag = get_tag_id_from_name(category)
            params.append(f"%{selected_tag}%")

    conditions.append("version.download_count >= ?")
    params.append(num_of_downloads)

    conditions.append("julianday('now') - julianday(version.create_time) >= ?")
    params.append(older_than)

    # 构建查询语句
    query = "SELECT DISTINCT model.uuid, version.id FROM model JOIN version ON model.uuid = version.model_uuid"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # 执行查询
    cursor.execute(query, params)
    rows = cursor.fetchall()
    model_uuids = [row[0] for row in rows]
    version_ids = [row[1] for row in rows]

    model_uuids = list(dict.fromkeys(model_uuids))
    version_ids = list(dict.fromkeys(version_ids))

    print(f"有{len(model_uuids)}个uuid")
    print(f"有{len(version_ids)}个version id")

    global files_to_download
    files_to_download = version_ids

    # global max_page
    # max_page = tk.IntVar()
    # max_page.set(len(model_uuids) / page_size + 1)

    button2.config(text=f"下载全部版本")

    # if len(model_uuids) >= 100:
    #     label_msg.config(
    #         text=f"共有{len(model_uuids)}个模型的{len(files_to_download)}个版本，只显示前{page_size}条。"
    #     )
    # else:
    label_msg.config(
        text=f"共有{len(model_uuids)}个模型的{len(files_to_download)}个版本，每页显示{page_size}条。"
    )

    total_pages = int(len(model_uuids) / page_size + 1)
    print(f"共有{total_pages}页")
    label_paging.config(text=f"共有{total_pages}页，选择页数：")

    pages = [page1 for page1 in range(1, total_pages + 1)]
    combo_paging["values"] = pages

    combo_paging.set(page)
    
    
    combo_paging.bind("<<ComboboxSelected>>", lambda event: on_page_selected(combobox_vars, root))

    # 计算偏移量
    offset = (page - 1) * page_size

    # uuids_100 = model_uuids[:100]
    uuids_current_page = model_uuids[offset : offset + page_size]

    # 查询model表中的name, type_name, base_type_name
    for uuid in uuids_current_page:
        cursor.execute(
            f"SELECT name, author, type_name, base_type_name, uuid FROM model WHERE uuid = ?",
            (uuid,),
        )
        result = cursor.fetchone()
        if result:
            tree.insert(
                "",
                tk.END,
                text=result[4],
                values=(result[0], result[1], result[2], result[3]),
            )

        tree.bind("<<TreeviewSelect>>", lambda e: on_tree_select(root, e))

    # 关闭数据库连接
    conn.close()


def on_page_selected(combobox_vars, root):
    combo_paging = root.nametowidget(".middle.tree_frame.paging_frame.combo_paging")
    selected_page = combo_paging.get()
    print(f"选择了第{selected_page}页")
    query_data(combobox_vars, root, int(selected_page))
    
    

def on_tree_select(root, event):
    button2 = root.nametowidget(".middle.button_frame.download_button")
    label_msg = root.nametowidget(".bottom.label_msg")

    selected_items = event.widget.selection()  # 获取当前选中的行ID
    selected_uuids = []
    for item_id in selected_items:
        item_data = event.widget.item(item_id)  # 获取选中行的数据
        uuid = item_data["text"]  # 获取标签（tag）中的uuid
        selected_uuids.append(uuid)
        print(f"选中的行数据: {item_data['values']}, UUID: {uuid}")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    query = """
        SELECT DISTINCT version.id 
        FROM version 
        WHERE model_uuid IN ({})
        """.format(
        ",".join(["?"] * len(selected_uuids))
    )
    cursor.execute(query, selected_uuids)
    results = cursor.fetchall()

    global files_to_download
    files_to_download = [result[0] for result in results]
    label_msg.config(
        text=f"当前选中{len(selected_items)}个模型的{len(files_to_download)}个版本。"
    )
    button2.config(text=f"下载所有选中的")


def query_data(combobox_vars, root, page=1):
    button2 = root.nametowidget(".middle.button_frame.download_button")
    button2.config(state=tk.NORMAL)

    label_msg = root.nametowidget(".bottom.label_msg")
    label_msg.config(text="正在查询……")

    tree = root.nametowidget(".middle.tree_frame.tree")
    threading.Thread(
        target=query_data_task,
        args=(combobox_vars, root, page),
    ).start()


def start_async_download(root):
    try:
        # 启动一个新线程来运行asyncio事件循环
        import threading

        download_thread = threading.Thread(
            target=lambda: asyncio.run(download(root)), daemon=True
        )
        download_thread.start()
    except Exception as e:
        print("Error", str(e))


async def download_other_files(
    version_cover_image, cover_image_file_path, version_desc
):
    # 保存该版本的说明信息
    description_file = os.path.join(
        os.path.dirname(cover_image_file_path), "readme.htm"
    )
    directory = os.path.dirname(description_file)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    with open(description_file, "w", encoding="utf-8") as desc_file:
        desc_file.write(version_desc + "\n")

    if os.path.exists(cover_image_file_path):
        print(f"文件 {cover_image_file_path} 已存在，跳过下载。")
        return

    # 构造aria2c命令
    command = [
        "aria2c",
        "--allow-overwrite=true",
        "--continue",
        "-d",
        os.path.dirname(cover_image_file_path),
        "-o",
        os.path.basename(cover_image_file_path),
        version_cover_image,
    ]

    # 创建一个子进程来执行aria2c下载命令
    proc = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    # 等待进程完成
    stdout, stderr = await proc.communicate()


async def download_model_file(root, url, file_path, total_files):
    global global_progress_var

    # 此时global_num_of_files_to_download应等于0
    global global_num_of_files_to_download

    label_msg = root.nametowidget(".bottom.label_msg")

    if os.path.exists(file_path):
        print(f"文件 {file_path} 已存在，跳过下载。")

        global_num_of_files_to_download += 1
        label_msg.config(
            text=f"第{global_num_of_files_to_download}/{total_files}个文件下载已完成"
        )
        global_progress_var.set(global_num_of_files_to_download / total_files * 100)
        return

    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    # 构造aria2c命令
    command = [
        "aria2c",
        "--allow-overwrite=true",
        "--continue",
        "-d",
        os.path.dirname(file_path),
        "-o",
        os.path.basename(file_path),
        url,
    ]

    # 创建一个子进程来执行aria2c下载命令
    proc = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    # 等待进程完成
    stdout, stderr = await proc.communicate()

    if proc.returncode == 0:
        print(f"Download completed: {file_path}")
        # 更新进度条
        global_num_of_files_to_download += 1
        label_msg.config(
            text=f"第{global_num_of_files_to_download}/{total_files}个文件下载已完成"
        )
        global_progress_var.set(global_num_of_files_to_download / total_files * 100)
    else:
        print(f"Error downloading {file_path}: {stderr.decode()}")


async def download(root):
    root_dir = filedialog.askdirectory()
    global files_to_download
    global global_progress_var
    global global_num_of_files_to_download
    print(f"有{len(files_to_download)}个文件等待下载")
    global_progress_var.set(0)
    global_num_of_files_to_download = 0

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    label_msg = root.nametowidget(".bottom.label_msg")
    # progress_bar = root.nametowidget(".bottom.progress_bar")
    # global_progress_var = progress_bar['variable']  # 设置全局进度条变量
    label_msg.config(text=f"开始下载{len(files_to_download)}个文件")

    tasks = []

    for id in files_to_download:
        cursor.execute(
            f"SELECT model.name, model.type_name, model.base_type_name, version.url, version.name, version.file_name, version.cover_image, version.description FROM model JOIN version ON model.uuid = version.model_uuid WHERE version.id = ?",
            (id,),
        )
        result = cursor.fetchone()
        if result:
            model_name = result[0]
            model_type_name = result[1]
            model_base_type_name = result[2]
            version_url = result[3]
            version_name = result[4]
            version_file_name = result[5]
            version_cover_image = result[6]
            version_desc = result[7]

            model_name = re.sub(r'[\\/*?:"<>|丨·]', "_", model_name)
            model_name = model_name.replace(" ", "")

            version_name = re.sub(r'[\\/*?:"<>|丨·]', "_", version_name)
            version_name = version_name.replace(" ", "")

            version_file_name = os.path.basename(version_file_name)
            version_file_name_base, version_file_name_ext = os.path.splitext(
                version_file_name
            )

            model_dir = os.path.join(
                root_dir,
                model_base_type_name,
                model_type_name,
                model_name,
                version_name,
            )

            url_base, url_ext = os.path.splitext(version_url)

            model_file_name = version_file_name_base + url_ext
            model_file_path = os.path.join(model_dir, model_file_name)

            cover_image_url_base, cover_image_url_ext = os.path.splitext(
                version_cover_image
            )

            cover_image_file_name = version_file_name_base + cover_image_url_ext
            cover_image_file_path = os.path.join(model_dir, cover_image_file_name)

            task = asyncio.ensure_future(
                download_other_files(
                    version_cover_image, cover_image_file_path, version_desc
                )
            )
            tasks.append(task)

            task = asyncio.ensure_future(
                download_model_file(
                    root, version_url, model_file_path, len(files_to_download)
                )
            )
            tasks.append(task)

    await asyncio.gather(*tasks)

    label_msg.config(text="下载完成！")


# 创建UI
def create_ui():
    window_width = 480
    window_height = 620

    # 创建Tkinter窗口
    root = tk.Tk()
    root.title("Liblib Downloader")
    root.geometry(f"{window_width}x{window_height}")
    # root.resizable(False, False)

    # 获取屏幕宽度和高度
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # 计算窗口位置，使其位于屏幕中心
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)

    # 设置窗口位置
    root.geometry(f"+{x}+{y}")

    frame_top = tk.Frame(root, height=100, name="top")
    frame_top.pack(fill="x")

    frame_middle = tk.Frame(root, height=460, name="middle")
    frame_middle.pack(fill="x")

    frame_bottom = tk.Frame(root, height=40, name="bottom")
    frame_bottom.pack(fill="x")

    # 定义控件数据，用于创建 Label 和 Combobox
    controls = [
        ("Model Type:", get_unique_values("model", "type_name"), True),
        ("Older than (days):", [0, 7, 14, 30, 90, 180, 365], False),
        ("Base Type:", get_unique_values("model", "base_type_name"), True),
        ("Num of downloads:", [0, 50, 100, 500, 1000, 5000, 10000], False),
        ("Catetory:", get_unique_values("tag", "name"), True),
    ]

    combobox_vars = {}

    # 使用grid布局在top_frame中添加Label和Combobox
    for i, (label_text, combo_options, is_readonly) in enumerate(controls):
        # 计算行和列
        row = i // 2  # 整除得到行号
        col = i % 2 * 2  # 模2得到列号，乘2是因为每组控件占用两列

        # 创建并放置Label
        label = tk.Label(frame_top, text=label_text)
        label.grid(row=row, column=col, padx=5, pady=5, sticky="e")

        var = tk.StringVar(root)
        # 创建并放置Combobox
        combobox = ttk.Combobox(frame_top, textvariable=var, values=combo_options)
        combobox["state"] = "readonly" if is_readonly else "normal"
        combobox.current(0)
        combobox.grid(row=row, column=col + 1, padx=5, pady=5, sticky="w")
        combobox_vars[label_text] = var

        # 让combobox在水平方向上填充和扩展
        frame_top.grid_columnconfigure(col + 1, weight=1)

    button_frame = tk.Frame(frame_middle, name="button_frame")
    button_frame.pack(pady=2)
    tree_frame = tk.Frame(frame_middle, name="tree_frame")
    # tree_frame.configure(background='blue')
    tree_frame.pack(fill="x")
    button_frame2 = tk.Frame(tree_frame, name="paging_frame")
    # button_frame2.configure(background='red')
    button_frame2.pack(side="bottom")

    button1 = ttk.Button(
        button_frame,
        text="查询",
        command=lambda: query_data(combobox_vars, root),
        name="query_button",
    )
    button1.pack(side="left", padx=10)
    button2 = ttk.Button(
        button_frame,
        text="下载",
        command=lambda: start_async_download(root),
        name="download_button",
    )
    button2.config(state=tk.DISABLED)
    button2.pack(side="right", padx=10)

    # 创建Treeview控件
    tree = ttk.Treeview(
        tree_frame,
        height=20,
        columns=("Name", "Author", "Type", "Base"),
        show="headings",
        name="tree",
    )
    # 定义列
    tree.heading("Name", text="Name")
    tree.heading("Author", text="Author")
    tree.heading("Type", text="Type")
    tree.heading("Base", text="Base")
    # 设置列的宽度
    tree.column("Name", width=220)
    tree.column("Author", width=80)
    tree.column("Type", width=100)
    tree.column("Base", width=60)
    tree.pack(pady=(5, 0))

    # button_prev = ttk.Button(button_frame2, text="上一页", name="prev")
    # button_prev.config(state=tk.DISABLED)
    # button_prev.pack(side="left", padx=2)
    # button_next = ttk.Button(button_frame2, text="下一页", name="next")
    # button_next.config(state=tk.DISABLED)
    # button_next.pack(side="right", padx=2)

    label_paging = ttk.Label(
        button_frame2, anchor="w", text=f"共有0页，选择分页：", name="label_paging"
    )
    label_paging.pack(side="left", padx=2)
    # var = tk.StringVar()
    combo_paging = ttk.Combobox(button_frame2, width=4, name="combo_paging")
    combo_paging["state"] = "readonly"
    combo_paging.pack(side="right", padx=2)

    label_msg = ttk.Label(
        frame_bottom, text="", anchor="w", foreground="green", name="label_msg"
    )
    label_msg.pack(side="left", fill="x", padx=10, pady=5, expand=True)

    # 创建进度条
    global global_progress_var
    global_progress_var = tk.IntVar()
    progress_bar = ttk.Progressbar(
        frame_bottom, variable=global_progress_var, maximum=100, name="progress_bar"
    )
    progress_bar.pack(side="right", fill="x", padx=(0, 10), pady=5, expand=True)

    # global current_page
    # current_page = tk.IntVar()
    # current_page.set(1)  # 设置初始页码为1

    return root


# 主程序
def main():
    # 创建UI
    root = create_ui()

    root.mainloop()


if __name__ == "__main__":
    main()
