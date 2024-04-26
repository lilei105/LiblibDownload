import os
import shutil

# 指定根目录
root_directory = "E:\\Liblib\\Checkpoint\\"

# 遍历根目录下的所有子目录
for folder_name in os.listdir(root_directory):
    folder_path = os.path.join(root_directory, folder_name)

    # 检查是否为目录
    if os.path.isdir(folder_path):
        # 去除空格
        new_folder_name = folder_name.replace("丨", "_")
        new_folder_path = os.path.join(root_directory, new_folder_name)

        # 如果新名字与旧名字不同，则重命名
        if new_folder_name != folder_name:
            try:
                shutil.move(folder_path, new_folder_path)
                print(f"Renamed directory: {folder_name} -> {new_folder_name}")
            except Exception as e:
                print(f"Error renaming directory {folder_name}: {e}")
