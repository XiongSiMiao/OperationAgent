import streamlit as st
import requests
import json
import re
import datetime
from datetime import timedelta
import pandas as pd
from typing import Optional, Tuple

"""
负责处理LDM日志解析
"""

def real_query(start: str, end: str, f11: str, f32: str) -> Tuple[str, str]:
    headers = {'Content-Type': 'application/json'}
    query_gscs = f'''search index=gscs_applog*,gscssett* (`time` BETWEEN "{start}" AND "{end}") "{f11}*" "{f32}" '''
    body = {"query": query_gscs}
    try:
        response = requests.post("http://184.86.0.96:9910/rest/v4/union/_q", headers=headers, data=json.dumps(body), timeout=30)
        if response.status_code != 200:
            return "ERROR", f"LDM查询失败: {response.status_code}"
        data = response.json()
        id = 1
        msg=""
        core_log=""
        for item in data['data']['result']['values']:
            temp=f"@Message:\n {item['source']['@message']}\n"
            msg+=temp
            #print(temp)
            pos = temp.find('logId')
            if pos != -1:
                bracket_pos = temp.find(']',pos)
                if bracket_pos != -1:
                    core = temp[bracket_pos+1:].strip()
                    core_log+=f"seq{id}: {core}\n"
                    #print(f"核心问题：{core}\n")
            id+=1
        return (core_log, msg) if msg else ("NO_LOGS", "未找到日志")
    except Exception as e:
        return "ERROR", str(e)


def analyze_with_ai(logs: str, full_msgs: str,resp_def: str, pre_req: str):
    if logs:
        # 有logs走deepseek-r1 --> 速度更快
        # 但是就需要外挂报文解读功能 -->  from ai import call_api
        #                              result = call_api(logs)
        # deepseek-r1
        #DEEPSEEK_URL = "http://184.86.48.49:25073/v1/chat/completions"
        #MODEL = "deepseek-r1"

        # 现阶段考虑精准度
        # 使用deepseek-v3
        DEEPSEEK_URL = "http://184.86.52.4:25059/v1/chat/completions"
        MODEL = "deepseek-v3"
        DEEPSEEK_API_KEY = "168F649870A0FfC4c415aAe2F6Df2E5B"
        #importance = core_log_agent(logs)
        from ai import call_api
        # 报文解读
        result = call_api(logs)
        prompt = f"""
        你是一名专业的ISO8583报文系统专家。请仔细阅读以下核心报错原因，分析交易失败的根本原因。
    		日志核心报错内容: {logs}
            
            请参考该交易的响应码定义: {resp_def}，以及该响应码的历史解决经验:{pre_req}，
            历史解决经验可能包含多种情况，请仔细比对报错日志、日志重要性与历史解决经验的场景。
            
        请直接给出分析结论。
        报文解读：xxx
        报错根本原因：XXX
        建议处理：XXX
        """
        payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
        }
        try:
            res = requests.post(DEEPSEEK_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}, json=payload, timeout=90)
            ans = res.json()['choices'][0]['message']['content']
            # 去除think标签
            return re.sub(r'<think>.*?</think>', '', ans, flags=re.DOTALL).strip()
        except:
            return "AI分析调用异常"
    else:
        # 无logs走deepseek-v3直接读
        DEEPSEEK_URL = "http://184.86.52.4:25059/v1/chat/completions"
        MODEL = "deepseek-v3"
        DEEPSEEK_API_KEY = "168F649870A0FfC4c415aAe2F6Df2E5B"
        prompt = f"""
        你是一名专业的ISO8583报文系统专家。请仔细阅读以下核心报错原因，分析交易失败的根本原因。
    		日志报错内容: {full_msgs}
            请参考该交易的响应码定义: {resp_def}，以及该响应码的历史解决经验:{pre_req}，
            历史解决经验可能包含多种情况，请仔细比对日志与历史解决经验，再比对报错日志与历史解决经验的场景。
            
        请直接给出分析结论。
        报文解读：xxx
        报错根本原因：XXX
        建议处理：XXX
        """
        payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
        }
        try:
            res = requests.post(DEEPSEEK_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}, json=payload, timeout=90)
            ans = res.json()['choices'][0]['message']['content']
            # 去除think标签
            return re.sub(r'<think>.*?</think>', '', ans, flags=re.DOTALL).strip()
        except:
            return "AI分析调用异常"
    
