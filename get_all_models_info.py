import time, requests, json, os, sqlite3, shutil, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone


# 100033表示建筑类
# 其它可选的值参见“查询用的参数见这里.json”
model_tag = None

base_url = "https://liblib-api.vibrou.com/api/www/model/search"
model_query_url = "https://liblib-api.vibrou.com/api/www/model/getByUuid/"
tag_query_url = "https://liblib-api.vibrou.com/api/www/public/tag/v2/search"

db_file = "models.db"


# 彩色输出的颜色代码
EXTENDED_ANSI_COLORS = {
    # 基本颜色
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    # 亮色
    "bright_black": "\033[90m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
    "bright_white": "\033[97m",
    # 其他颜色
    "orange": "\033[38;5;208m",  # 256色中的橙色
    "purple": "\033[38;5;93m",  # 256色中的紫色
    "brown": "\033[38;5;94m",  # 256色中的棕色
    "pink": "\033[38;5;207m",  # 256色中的粉色
    "gray": "\033[38;5;244m",  # 256色中的灰色
    # 重置代码
    "reset": "\033[0m",
}


def printc(color, text):
    """
    打印彩色文本的函数。

    :param color: 颜色名称，必须是ANSI_COLORS字典中的一个键。
    :param text: 要打印的文本。
    """
    # 打印彩色文本
    print(f"{EXTENDED_ANSI_COLORS[color]}{text}{EXTENDED_ANSI_COLORS['reset']}")


# 创建数据库文件，并调用创建表的函数来创建所有数据表
def create_db():
    # 检查数据库文件是否存在
    if os.path.exists(db_file):
        print("数据库已存在，跳过创建步骤。")
        return

    # 连接到SQLite数据库
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    table_definitions = [
        (
            "info",
            [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("count", "INTEGER"),
                ("last_run", "DATE"),
            ],
            None,  # 无外键
        ),
        (
            "tag",
            [
                ("id", "INTEGER PRIMARY KEY"),
                ("name", "TEXT"),
            ],
            None,  # 无外键
        ),
        (
            "model",
            [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("uuid", "TEXT UNIQUE"),
                ("name", "TEXT"),
                ("extracted", "INTEGER"),
                ("author", "TEXT"),
                ("type", "TEXT"),
                ("type_name", "TEXT"),
                ("base_type", "TEXT"),
                ("base_type_name", "TEXT"),
                ("tags", "TEXT"),
            ],
            None,  # 无外键
        ),
        (
            "version",
            [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("url", "TEXT"),
                ("file_name", "TEXT"),
                ("cover_image", "TEXT"),
                ("name", "TEXT"),
                ("download_count", "INTEGER"),
                ("run_count", "INTEGER"),
                ("base_type", "TEXT"),
                ("description", "TEXT"),
                ("create_time", "DATE"),
                ("model_uuid", "TEXT"),
            ],
            "FOREIGN KEY(model_uuid) REFERENCES model(uuid)",  # 添加外键
        ),
        (
            "not_downloadable",
            [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("uuid", "TEXT"),
                ("model_name", "TEXT"),
                ("version_name", "TEXT"),
            ],
            None,  # 无外键
        ),
        (
            "failed",
            [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("uuid", "TEXT UNIQUE"),
            ],
            None,  # 无外键
        ),
    ]

    try:
        for table_name, columns, foreign_key in table_definitions:
            # 创建表的SQL语句
            create_table_sql = f"CREATE TABLE {table_name} ("
            create_table_sql += ", ".join(
                [f"{column[0]} {column[1]}" for column in columns]
            )
            if foreign_key:
                create_table_sql += f", {foreign_key}"
            create_table_sql += ")"
            # 执行SQL语句
            c.execute(create_table_sql)

        # 提交事务
        conn.commit()
        print(f"已经创建数据库文件{db_file}")
    except Exception as e:
        print(f"创建数据库失败：{e}")
    finally:
        # 关闭数据库连接
        conn.close()


# 封装一个通用的liblib api查询请求
# 放心没有任何个人信息相关的参数
def lib_request(url, data):
    headers = {
        "Host": "liblib-api.vibrou.com",
        "Connection": "keep-alive",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "sec-ch-ua-platform": '"Windows"',
        "Origin": "https://www.liblib.art",
        "Referer": "https://www.liblib.art/",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh,en-US;q=0.9,en;q=0.8,en-GB;q=0.7,zh-CN;q=0.6",
    }
    response = requests.post(url, headers=headers, json=data)
    return response


# 先做一个小的请求，获得某个类别的模型总数
# models=1 表示Checkpoint，5 表示LoRA，等等
# types表示SD1.5/SDXL等
# tagV2Id=100033 表示建筑类
# tagsV2Id如需修改参见“查询用的参数见这里.json”
def get_total_number(models, types, tagV2Id):
    conn = sqlite3.connect(db_file)
    total_number = 0

    try:
        cursor = conn.cursor()
        data = {
            "page": 1,
            "pageSize": 10,
            "models": models,
            "types": types,
            "tagV2Id": tagV2Id,
        }
        response = lib_request(base_url, data)

        if response.status_code == 200:
            json_data = response.json()
            total_number = json_data["data"]["total"]

            current_utc_time = datetime.now(timezone.utc)
            formatted_time = current_utc_time.strftime("%Y-%m-%dT%H:%M:%S.000+00:00")
            # current_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '+00:00'
            cursor.execute(
                "INSERT INTO info (count, last_run) VALUES (?, ?)",
                (total_number, formatted_time),
            )
            conn.commit()
            print(f"tag为“{tagV2Id}”的模型数据共有{total_number}条")

        else:
            printc(
                "red",
                f"获取模型数量时http返回数据出错，http错误代码{response.status_code}",
            )
    except Exception as e:
        printc("red", f"获取模型数量时发生错误: {e}")
    finally:
        cursor.close()
        conn.close()

    return total_number


# 获取所有modelContent中的tag
def get_tag_info():
    conn = sqlite3.connect(db_file)

    try:
        c = conn.cursor()
        data = {"categoryCode": "modelContent", "page": 1, "pageSize": 50}
        response = lib_request(tag_query_url, data)

        if response.status_code == 200:
            json_data = response.json()
            tags = json_data["data"]["data"]
            print(f"已获取{len(tags)}条tag")
            for tag in tags:
                id = tag["id"]
                name = tag["name"]
                c.execute(
                    "INSERT OR IGNORE INTO tag (id, name) VALUES (?, ?)",
                    (id, name),
                )
            conn.commit()
            # conn.close()

    except Exception as e:
        printc("red", f"获取tag时发生错误: {e}")
    finally:
        c.close()
        conn.close()


def convert_base_type_to_name(number):
    base_type_to_name = {
        1: "SD1.5",
        2: "SD2.1",
        3: "SDXL",
        4: "Cascade Stage a",
        5: "Cascade Stage b",
        6: "Cascade Stage c",
    }
    return base_type_to_name.get(number, "Unknown")


def get_all_tags_from_tagsV2(uuid, tagsV2):
    # 初始化一个空列表来存储所有的tag_id
    tag_ids = []
    try:
        # 遍历tags数组
        for tag in tagsV2["modelContent"]:
            # 提取每个tag的id
            tag_id = tag["id"]
            # 将tag_id添加到tag_ids列表中
            tag_ids.append(tag_id)

    except Exception as e:
        printc("gray", f"获取{uuid}的tagsV2时发生错误：{type(e).__name__}")
    finally:
        return json.dumps(tag_ids)


# 获得每一页的50个uuid
def get_uuids_for_page(page):
    try:
        data = {
            "page": page,
            "pageSize": 50,
            "sort": 0,
            "models": [],
            "types": [],
            "tagV2Id": model_tag,
        }
        response = lib_request(base_url, data)
        time.sleep(0.5)

        # 来了不多于50条uuid
        if response.status_code == 200:
            data = response.json()
            if data["data"] is None or data["data"]["data"] is None:
                printc("yellow", f"第{page}页没有数据")
                return

            data_num = len(data["data"]["data"])
            print(".", end="", flush=True)

            conn = sqlite3.connect("models.db")
            c = conn.cursor()

            for num in range(data_num):
                uuid = data["data"]["data"][num]["uuid"]
                name = data["data"]["data"][num]["name"]
                nickname = data["data"]["data"][num]["nickname"]
                modelType = data["data"]["data"][num]["modelType"]
                modelTypeName = data["data"]["data"][num]["modelTypeName"]
                baseType = data["data"]["data"][num]["baseType"][0]
                baseTypeName = convert_base_type_to_name(baseType)
                # tags = get_all_tags_from_tagsV2(uuid, data["data"]["data"][num]["tagsV2"])
                c.execute(
                    "INSERT OR IGNORE INTO model (uuid, name, author, extracted, type, type_name, base_type, base_type_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        uuid,
                        name,
                        nickname,
                        0,
                        modelType,
                        modelTypeName,
                        baseType,
                        baseTypeName,
                        # tags,
                    ),
                )

            conn.commit()
            conn.close()
        else:
            printc("red", f"在第{page}页http返回错误: {response.status_code}")

    except Exception as e:
        printc("red", f"在第{page}页取到了无效数据: {e}")


def count_models():
    conn = sqlite3.connect("models.db")
    c = conn.cursor()
    # 执行查询以计算不同 uuid 的总数
    c.execute("SELECT COUNT(DISTINCT uuid) FROM model")
    total_unique_uuids = c.fetchone()[0]  # fetchone() 返回第一条记录的第一个字段
    conn.close()
    print(f"数据库中模型总数为：{total_unique_uuids}")


def count_models_by_type():
    conn = sqlite3.connect("models.db")
    c = conn.cursor()
    c.execute("SELECT type_name, COUNT(DISTINCT uuid) FROM model GROUP BY type")
    results = c.fetchall()
    conn.close()
    for result in results:
        print(f"{result[0]:<20}类型数量为{result[1]}")


# 多线程获取所有页（每页50个）的uuid
def get_all_uuids(total_number):
    total_pages = total_number // 50 + 1
    # total_pages = 2

    print(f"分页获取需要{total_pages}页")

    # 分页获取时不能多线程，否则在较多页数之后会获取到空数据
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = [
            executor.submit(get_uuids_for_page, page)
            for page in range(1, total_pages + 1)
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                printc("red", f"多线程获取所有uuid时发生错误: {e}")

    print("")
    count_models()
    count_models_by_type()


# 根据给定uuid获得模型的全部信息
def get_model_info_by_uuid(uuid):
    # print(f"正在处理uuid：{uuid}")
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    # 检查UUID是否已存在于数据库的'model'表中
    c.execute("SELECT uuid FROM model WHERE uuid = ? AND extracted = 1", (uuid,))
    existing_uuid = c.fetchone()

    if existing_uuid:
        # printc("yellow", f"UUID {uuid} 已处理过.")
        c.execute("DELETE FROM failed WHERE uuid = ?", (uuid,))
        conn.commit()

        return

    try:
        data = {}
        response = lib_request(model_query_url + uuid, data).json()
        time.sleep(0.5)

        if response["data"] is None:
            printc("yellow", f"在获取{uuid}时发现了空数据，跳过这个uuid")
            return

        model_uuid = response["data"]["uuid"]
        model_name = response["data"]["name"]
        model_type = response["data"]["modelType"]
        versions = response["data"]["versions"]
        tagsV2 = response["data"]["tagsV2"]

        for version in versions:
            if (
                version["attachment"] is not None
                and version["attachment"]["modelSource"] is not None
            ):
                # print(f"正在获取{model_uuid}")

                if (
                    version["attachment"]["modelSource"] is None
                    or version["attachment"]["modelSourceName"] is None
                ):
                    printc("yellow", "模型{}不包含文件信息")
                    continue

                version_file_url = version["attachment"]["modelSource"]
                version_file_name = version["attachment"]["modelSourceName"]

                if (
                    version["imageGroup"] is None
                    or version["imageGroup"]["coverUrl"] is None
                ):
                    version_cover_image = None
                else:
                    version_cover_image = version["imageGroup"]["coverUrl"]

                version_name = version["name"]
                version_download_count = version["downloadCount"]
                version_run_count = version["runCount"]
                version_base_type = version["baseType"]
                version_description = version["versionDesc"]
                version_create_time = version["createTime"]

                # 将版本信息插入到数据库的 'version' 表中
                c.execute(
                    "INSERT INTO version (url, file_name, cover_image, name, download_count, run_count, base_type, description, create_time, model_uuid) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        version_file_url,
                        version_file_name,
                        version_cover_image,
                        version_name,
                        version_download_count,
                        version_run_count,
                        version_base_type,
                        version_description,
                        version_create_time,
                        uuid,
                    ),
                )
                conn.commit()

            else:
                printc(
                    "gray",
                    f"这个模型（版本）不让下载：{uuid}，名称：{model_name}，版本：{version['name']}",
                )
                # 将不让下载的模型的UUID插入到 'not_downloadable' 表中
                c.execute(
                    "INSERT INTO not_downloadable (uuid, model_name, version_name) VALUES (?, ?, ?)",
                    (uuid, model_name, version["name"]),
                )
                conn.commit()

            c.execute("DELETE FROM failed WHERE uuid = ?", (uuid,))
            conn.commit()

            tags = get_all_tags_from_tagsV2(uuid, tagsV2)
            c.execute(
                "UPDATE model SET tags = ? WHERE uuid = ?",
                (
                    tags,
                    uuid,
                ),
            )
            conn.commit()

            # 在插入操作之后，更新 'model' 表中对应的 'extracted' 字段为1
            c.execute("UPDATE model SET extracted = 1 WHERE uuid = ?", (uuid,))
            conn.commit()

    except Exception as e:
        printc("red", f"在获取{uuid}时发生了错误：{type(e).__name__}")

        c.execute("INSERT OR IGNORE INTO failed (uuid) VALUES (?)", (uuid,))
        conn.commit()

    finally:
        c.close()
        conn.close()


# 返回一个uuid列表
def get_all_uuids_from_database(table):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT uuid FROM " + table)
    uuids = cursor.fetchall()
    conn.close()
    return [uuid[0] for uuid in uuids]


# 获取not_downloadable数据条数
def count_not_downloadable_records():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 执行SQL查询来获取not_downloadable表中的记录数
    cursor.execute("SELECT COUNT(*) FROM not_downloadable")
    count = cursor.fetchone()[0]  # 获取查询结果的第一行第一列的值

    conn.close()

    return count


def get_all_models_info(uuid_list):
    print(f"==========开始逐个获取uuid包含的模型信息==========")

    # 使用ThreadPoolExecutor来管理线程
    with ThreadPoolExecutor(max_workers=5) as executor:
        # 提交任务到线程池，并将uuid作为参数传递
        futures = {
            executor.submit(get_model_info_by_uuid, uuid): uuid for uuid in uuid_list
        }

        # 等待所有任务完成
        for future in as_completed(futures):
            uuid = futures[future]
            try:
                future.result()
            except Exception as e:
                # printc("red", f"多线程获取{uuid}包含的模型信息时发生错误: {e}")
                print("", end="", flush=True)
    print(f"=====================获取完毕=====================")


def process_failed():
    uuid_list = get_all_uuids_from_database("failed")
    if len(uuid_list) > 0:
        print(f"发现{len(uuid_list)}个获取失败的uuid，再来一遍")
        get_all_models_info(uuid_list)


def run_command(command):
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    else:
        print(f"Output: {result.stdout}")


def copy_and_publish_db_file():
    root_dir = "/root/"

    # 获取当前文件的完整路径
    current_file_path = os.path.abspath(__file__)
    # 获取当前文件所在的目录
    current_dir = os.path.dirname(current_file_path)
    dest_path = current_dir + "/" + db_file

    shutil.copy(root_dir + db_file, current_dir)

    date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # run_command("git lfs install")
    # run_command('git lfs track "*.db"')
    # run_command("git add .gitattributes")
    run_command(f"git add {dest_path}")
    run_command(f'git commit -m "自动上传models.db {date}"')
    run_command(f"git push origin master")


# 主入口
create_db()
get_tag_info()
total_number = get_total_number(models=[], types=[], tagV2Id=model_tag)
get_all_uuids(total_number)

uuid_list = get_all_uuids_from_database("model")
get_all_models_info(uuid_list)

process_failed()

copy_and_publish_db_file()
