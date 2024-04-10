import time
import requests, json

model_category = "100033"

base_url = "https://liblib-api.vibrou.com/api/www/model/search"
model_query_url = "https://liblib-api.vibrou.com/api/www/model/getByUuid/"
num_of_checkpoint_models = 0
num_of_lora_models = 0
num_of_not_downloadable = 0

model_type_mapping = {
    1: "Checkpoint",
    5: "LoRA"
}

base_type_mapping = {
    1: "SD1.5",
    3: "SDXL"
}


def lib_request(url, data):
    headers = {
        "Host": "liblib-api.vibrou.com",
        "Connection": "keep-alive",
        "Content-Length": "64",
        "sec-ch-ua": '"Microsoft Edge";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
        "sec-ch-ua-mobile": "?0",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "sec-ch-ua-platform": '"Windows"',
        "Origin": "https://www.liblib.art",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.liblib.art/",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh,en-US;q=0.9,en;q=0.8,en-GB;q=0.7,zh-CN;q=0.6",
    }
    response = requests.post(url, headers=headers, json=data)
    return response


# 获得某个类别的模型总数
# models=1 表示Checkpoint
# models=5 表示LoRA
# tagV2Id=100033 表示建筑类
def get_total_number(models, types, tagV2Id):
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
        print(f"共有{total_number}个模型数据")
    else:
        print(f"获取模型数量时出错，错误代码{response.status_code}")

    return total_number


# 根据模型总数，分页获取所有的模型uuid
def get_all_uuids(total_number):
    global num_of_checkpoint_models
    global num_of_lora_models

    total_pages = total_number // 50 + 1
    print(f"分页获取需要{total_pages}页")
    print("正在统计模型数量")

    all_uuids = []

    for page in range(1, total_pages + 1):
    # for page in range(1, 3 + 1):
        data = {
            "page": page,
            "pageSize": 50,
            "sort": 0,
            "models": [],
            "types": [],
            "tagV2Id": model_category,  # tagV2Id=100033 表示建筑类
        }
        response = lib_request(base_url, data)
        time.sleep(0.1)

        # 检查请求是否成功
        if response.status_code == 200:
            # 解析JSON数据
            data = response.json()
            data_num = len(data["data"]["data"])
            # print(f"本页共包含{data_num}条数据")
            print(".", end="", flush=True)

            for num in range(0, data_num):

                model_type = data["data"]["data"][num]["modelType"]
                if model_type == 1:
                    num_of_checkpoint_models += 1
                elif model_type == 5:
                    num_of_lora_models += 1

                # 提取数据
                uuid = data["data"]["data"][num]["uuid"]

                # 将数据添加到总列表中
                all_uuids.append(uuid)
        else:
            print(f"Error: {response.status_code}")
            break

    print("")
    print(
        f"共有{len(all_uuids)}个模型，其中CHECKPOINT类型{num_of_checkpoint_models}个，LORA类型{num_of_lora_models}个"
    )
    
    # 返回所有提取的uuid
    return all_uuids


# 根据给定uuid获得模型的全部信息，以json格式返回
def get_model_info_by_uuid(uuid):
    # print(f"正在处理uuid：{uuid}")

    data = {}
    response = lib_request(model_query_url + uuid, data).json()
    time.sleep(0.1)

    model_uuid = response["data"]["uuid"]
    model_name = response["data"]["name"]
    model_type = response["data"]["modelType"]
    versions = response["data"]["versions"]
    version_info_list = []
    global num_of_not_downloadable

    for version in versions:
        if (
            version["attachment"] is not None
            and version["attachment"]["modelSource"] is not None
        ):
            version_file_url = version["attachment"]["modelSource"]
            version_file_name = version["attachment"]["modelSourceName"]
            version_cover_image = version["imageGroup"]["coverUrl"]
            version_name = version["name"]
            version_download_count = version['downloadCount']
            version_base_type = version['baseType']

            # 创建一个字典来存储当前版本的信息
            version_info = {
                "version_file_url": version_file_url,
                "version_file_name": version_file_name,
                "version_cover_image": version_cover_image,
                "version_name": version_name,
                "version_download_count": version_download_count,
                "version_base_type": base_type_mapping.get(version_base_type, "Unknown"),
                # "version_description": version_description,
            }

            # 将当前版本的字典添加到列表中
            version_info_list.append(version_info)

        else:
            print(f"这个不让下载：{model_uuid}，名称：{model_name}，版本：{version["name"]}")
            num_of_not_downloadable += 1
            # continue

    # 只有当version_info_list不为空时，才创建model_info字典
    if version_info_list:
        model_info = {
            "model_uuid": model_uuid,
            "model_name": model_name,
            "model_type": model_type_mapping.get(model_type, "Unknown"),
            "versions": version_info_list,
        }
        json_result = json.dumps(model_info)
    else:
        json_result = None

    return json_result


# 根据uuid列表获得所有模型的全部信息，以json格式返回
def get_all_models_info(uuids):
    all_models_info = []

    for uuid in uuids:
        model = get_model_info_by_uuid(uuid)
        if model is not None:
            all_models_info.append({"model": json.loads(model)})
        # time.sleep(0.1)

    merged_json_data = {"models": all_models_info}
    print(f"有{num_of_not_downloadable}个模型（或版本）不让下载")

    return merged_json_data


# 主入口
total_number = get_total_number(models=[], types=[], tagV2Id=model_category)
uuids = get_all_uuids(total_number)
all_models_info = get_all_models_info(uuids)
file_name = "all_models_" + model_category + ".json"
with open(file_name, "w", encoding="utf-8") as json_file:
    json.dump(all_models_info, json_file, ensure_ascii=False, indent=4)
