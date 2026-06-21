from hybase_api import HybaseApi
import requests

HYBASE_DATABASE = "system.event_database_trs_cn2"
HYBASE_CONFIG = {
    "hybase_key": "Trsadmin19940802.",
    "hybase_host": "http://192.168.190.69:8555",
    "hybase_security_code": "Yu5iztekGyFOOp821JM8WQ=="
}

hydb = HybaseApi(HYBASE_CONFIG)

def get_vector_str(text):
    url = "http://192.168.152.51:8111/bge/embeddings"
    input_data = {"text": text, "type": "answer"}
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", 'Connection': 'close'}
    try:
        results = requests.post(url, input_data, headers=headers, timeout=1000).json()
    except Exception as e:
        print(f"获取向量时出错: {text}\n{e}")
        return ""
    vector = results.get("results", [])
    return ",".join(str(i) for i in vector)

# def get_vector_bge_m3(text):
#     url = "http://101.251.216.48/embedding_bge/v1/embeddings"
#     input_data = {"input": text, "model": "bge-m3-vllm"}
#     headers = {"Content-Type": "application/json; charset=UTF-8", 'Connection': 'close'}
#     try:
#         results = requests.post(url, input_data, headers=headers, timeout=1000).json()
#     except Exception as e:
#         print(f"获取向量时出错: {text}\n{e}")
#         return ""
#     vector = []
#     vector = results['data'][0]['embedding']
#     return ",".join(str(i) for i in vector)
def get_vector_bge_m3(text):
    url = "http://101.251.216.48/embedding_bge/v1/embeddings"
    input_data = {"input": text, "model": "bge-m3-vllm"}
    try:
        # 使用 json 参数发送 POST 请求，自动设置 Content-Type 为 application/json
        resp = requests.post(url, json=input_data, timeout=30)
        resp.raise_for_status()  # 如果 HTTP 状态码不是 2xx，抛出异常
        results = resp.json()
    except Exception as e:
        print(f"请求失败: {text}\n{e}")
        return ""

    # 检查响应结构是否符合预期
    if 'data' not in results:
        print(f"API 返回数据异常，缺少 'data' 字段: {results}")
        return ""
    
    if not results['data'] or 'embedding' not in results['data'][0]:
        print(f"API 返回的 'data' 结构不正确: {results}")
        return ""

    vector = results['data'][0]['embedding']
    return ",".join(str(i) for i in vector)

def get_hybase_retrieve_reuslts(database, query, return_fields, recordNum=100, search_type="vector", vector_query_field="vector"):
    results = []
    if search_type == "vector":
        resultSet = hydb.hybase_vector_executeSelect(database, query, start=0, recordNum=recordNum, vector_fields=vector_query_field)
    else:
        resultSet = hydb.hybase_executeSelect(database, query, start=0, recordNum=recordNum)
    i = 0
    while i < resultSet.size():
        resultSet.moveNext()
        re = resultSet.get()
        results_json = {}
        for return_f in return_fields:
            results_json.setdefault(return_f, re.getString(return_f))
        results.append(results_json)
        i += 1

    # 字段重命名映射
    field_mapping = {
        # 'TRS_EventDescription': '事件描述',
        # 'TRS_EventThemes': '事件泛化描述',        
        # 'TRS_EventType': '事件类型',
        # 'TRS_EventReasonGeneral': '事件泛化原因',
        # 'TRS_EventResult': '事件结果',
        # 'TRS_EventResultGeneral': '事件泛化结果',
    }
    
    # 重命名字段
    renamed_results = []
    for result in results:
        renamed_result = {}
        for key, value in result.items():
            new_key = field_mapping.get(key, key)
            renamed_result[new_key] = value
        renamed_results.append(renamed_result)
    
    search_results = renamed_results
    return search_results, resultSet.size()


event_general_theme = "王府井公司回复投资者关于西单商场改造项目工期延长的提问，解释原因并否认虚假承诺。"
query_field = "TRS_EventDescription"
vector_query_field = "TRS_EventVector"
return_fields = [
    'TRS_EventTitle',
    'TRS_EventTimeOriWord',
    'TRS_EventKeywords',
    'TRS_EventDescription',
]
recordNum = 10
param = {}

# query = f"{query_field}#LIKE: \"{event_general_theme}\"~50"   
# search_results, resultSet_size = get_hybase_retrieve_reuslts(HYBASE_DATABASE, query, return_fields=return_fields, recordNum=recordNum)
# print(f"search_results: {search_results}")
# print(f"检索到相关事件 {resultSet_size} 个")


query = f"{vector_query_field}: \"{get_vector_bge_m3(event_general_theme)}\""
search_results, resultSet_size = get_hybase_retrieve_reuslts(HYBASE_DATABASE, query, return_fields=return_fields, recordNum=recordNum, search_type="vector", vector_query_field=vector_query_field)
print(f"search_results: {search_results}")
print(f"检索到相关事件 {resultSet_size} 个")
