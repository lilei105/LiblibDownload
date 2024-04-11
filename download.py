import json, os, subprocess, re, datetime
from dateutil.tz import tzutc

# 指定根文件夹，请修改成自己要存的目录，注意留够硬盘空间
root_folder = "D:\\Liblib\\"

# 100033代表“建筑与空间设计”类别，其他类别请修改
model_category = "100033"

# 获取当前时间，带时区信息
now = datetime.datetime.now(tzutc())


def download_file(url, file_path):
    # 检查文件是否已经存在
    if os.path.exists(file_path):
        print(f"File {file_path} already exists, skipping download.")
        return

    # 使用aria2c命令行工具下载文件，支持断点续传
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
    subprocess.run(command, check=True)


# 读取JSON文件
file_name = "all_models_" + model_category + ".json"
with open(file_name, "r", encoding="utf-8") as f:
    data = json.load(f)

# 遍历models数组
for model_data in data["models"]:
    model = model_data["model"]
    model_type = model["model_type"]
    model_name = model["model_name"]

    # 替换文件名中的非法字符并去掉空格
    model_name = re.sub(r'[\\/*?:"<>|丨]', "_", model_name)
    # model_name = re.sub(r'\|', '_', model_name)
    # model_name = model_name.rstrip()
    model_name = model_name.replace(" ", "")
    model_name = model_name.replace("|", "_")

    # 根据model_type在根文件夹下创建文件夹
    type_folder = os.path.join(root_folder, model_type)
    if not os.path.exists(type_folder):
        os.makedirs(type_folder)

    # 在model_type文件夹下创建model_name文件夹
    model_folder = os.path.join(type_folder, model_name)
    if not os.path.exists(model_folder):
        os.makedirs(model_folder)

    # 遍历versions数组
    for version in model["versions"]:
        version_name = version["version_name"]

        version_name = re.sub(r'[\\/*?:"<>|丨]', "_", version_name)
        version_name = version_name.replace(" ", "")

        version_folder = os.path.join(model_folder, version_name)
        if not os.path.exists(version_folder):
            os.makedirs(version_folder)

        # 比较version_create_time
        # version_create_time = datetime.datetime.fromisoformat(version["version_create_time"])
        # version_create_time = version_create_time.replace(tzinfo=tzutc())
        # if (now - version_create_time).days < 30:
        #     print(f"{model_name} 的 {version_name} 版本是菜鸟，出来还不足一个月，先不下载它")
        #     continue  # 如果version_create_time比当前时间早于一个月以上，则跳过下载

        # 如果下载量小于100则跳过下载
        version_download_count = version["version_download_count"]
        if version_download_count < 100:
            print(f"{model_name} 的 {version_name} 版本下载量不足100，不理它。")
            description_file = os.path.join(version_folder, "下载量不足100.txt")
            with open(description_file, "w", encoding="utf-8") as desc_file:
                desc_file.write("该版本下载量过少，所以不予下载。可以从这里手工下载：\n" + version["version_file_url"] + "\n")
            continue

        # 创建description.txt文件
        description_file = os.path.join(version_folder, "description.txt")
        with open(description_file, "w", encoding="utf-8") as desc_file:
            desc_file.write(version["version_description"] + "\n")

        # 下载version_cover_image并重命名
        image_url = version["version_cover_image"]
        url_base, url_ext = os.path.splitext(image_url)
        image_file = version["version_file_name"]
        file_base, file_ext = os.path.splitext(image_file)

        # 使用原始文件名和新扩展名重组文件名
        image_name_new = os.path.join(version_folder, file_base + url_ext)

        download_file(image_url, image_name_new)

        # 下载version_file_url并重命名
        file_url = version["version_file_url"]
        url_base, url_ext = os.path.splitext(file_url)
        file = version["version_file_name"]
        file_base, file_ext = os.path.splitext(file)

        # 使用原始文件名和新扩展名重组文件名
        file_name_new = os.path.join(version_folder, file_base + url_ext)

        download_file(file_url, file_name_new)
