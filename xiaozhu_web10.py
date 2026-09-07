import streamlit as st
from openai import OpenAI
import json5
import json
import re
import os

api_key = os.environ.get("DEEPSEEK_API_KEY", "")

if not api_key:
    try:
        with open("key.txt", "r", encoding="utf-8") as f:
            api_key = f.read().strip()
    except FileNotFoundError:
        api_key = ""

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

def read_memory():
    with open("memory.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(data):
    with open("memory.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def memory_to_text(data):
    text = ""
    for category, items in data.items():
        text += "【" + category + "】\n"
        if items:
            for i, item in enumerate(items, 1):
                text += str(i) + ". " + item + "\n"
        else:
            text += "暂无\n"
        text += "\n"
    return text

def add_to_category(category, content):
    data = read_memory()

    if category not in data:
        data[category] = []

    if content in data[category]:
        return False

    data[category].append(content)
    save_memory(data)
    return True

def is_similar(a, b):
    if a in b or b in a:
        return True

    common = set(a) & set(b)

    if len(a) <= 3:
        if len(common) >= 2:
            return True

    if len(common) >= max(2, min(len(a), len(b)) * 0.5):
        return True

    return False

def search_all_memory(keyword):
    data = read_memory()
    result = []

    for category, items in data.items():
        for i, item in enumerate(items):
            if keyword.strip() == "" or is_similar(keyword, item):
                result.append({
                    "category": category,
                    "index": i,
                    "content": item
                })

    return result

def delete_memory_by_category_index(category, index):
    data = read_memory()

    if category not in data:
        return None

    if index < 0 or index >= len(data[category]):
        return None

    deleted = data[category].pop(index)
    save_memory(data)
    return deleted

def modify_memory_by_category_index(category, index, new_content):
    data = read_memory()

    if category not in data:
        return None

    if index < 0 or index >= len(data[category]):
        return None

    old = data[category][index]
    data[category][index] = new_content
    save_memory(data)
    return old

def analyze_intent(user_input):
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是小猪的意图理解模块。\n"
             "根据洋哥的话，判断他的意图是什么。\n"
             "只能返回JSON，格式如下：\n"
             "{\"action\": \"动作\", \"category\": \"分类\", \"content\": \"内容\", \"old\": \"旧内容关键词\", \"new\": \"新内容\"}\n\n"
             "动作只能是：add、delete、modify、view、chat\n"
             "add：用户提供了新的个人信息或重要事情，需要记住\n"
             "delete：用户想删除某条记忆\n"
             "modify：用户想修改某条记忆\n"
             "view：用户想查看记忆\n"
             "chat：普通聊天，不需要操作记忆\n\n"
             "分类只能是：基本情况、目标计划、习惯偏好、正在学习、重要事情、聊天笔记\n"
             "old要尽量提取用户想删除或修改的旧内容关键词。\n"
             "如果不是记忆操作，category、content、old、new都返回空字符串。\n"
             "只返回JSON，不要解释。"},
            {"role": "user", "content": user_input}
        ]
    )
    result = response.choices[0].message.content
    return json5.loads(result)

st.title("小猪")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_delete" not in st.session_state:
    st.session_state.pending_delete = None

if "pending_modify" not in st.session_state:
    st.session_state.pending_modify = None

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("洋哥，请说")

if user_input:
    with st.chat_message("user"):
        st.write(user_input)

    st.session_state.messages.append({"role": "user", "content": user_input})

    if user_input.startswith("删第"):
        m = re.search(r"删第(\d+)条", user_input)
        if m and st.session_state.pending_delete:
            num = int(m.group(1)) - 1
            matches = st.session_state.pending_delete

            if num < 0 or num >= len(matches):
                ai_reply = "洋哥，这个序号不对。"
            else:
                target = matches[num]
                deleted = delete_memory_by_category_index(target["category"], target["index"])
                ai_reply = "洋哥，已经删掉了：【" + target["category"] + "】" + deleted

            with st.chat_message("assistant"):
                st.write(ai_reply)

            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            st.session_state.pending_delete = None
            st.stop()

    if user_input.startswith("改第"):
        m = re.search(r"改第(\d+)条\s*(.*)", user_input)
        if m and st.session_state.pending_modify:
            num = int(m.group(1)) - 1
            new_content = m.group(2).strip()
            matches = st.session_state.pending_modify

            if num < 0 or num >= len(matches):
                ai_reply = "洋哥，这个序号不对。"
            elif not new_content:
                ai_reply = "洋哥，新内容不能为空。"
            else:
                target = matches[num]
                old_content = modify_memory_by_category_index(target["category"], target["index"], new_content)
                ai_reply = "洋哥，已经把【" + target["category"] + "】里的“" + old_content + "”改成“" + new_content + "”了。"

            with st.chat_message("assistant"):
                st.write(ai_reply)

            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            st.session_state.pending_modify = None
            st.stop()

    intent = analyze_intent(user_input)
    action = intent["action"]
    category = intent["category"]
    content = intent["content"]
    old = intent["old"]
    new = intent["new"]

    if action == "add":
        added = add_to_category(category, content)
        if added:
            st.toast("小猪已记到" + category)
        else:
            st.toast("小猪：这个我已经记过了")

    elif action == "delete":
        matches = search_all_memory(old)

        if not matches:
            ai_reply = "洋哥，我在所有记忆里都没找到相关的。"
            with st.chat_message("assistant"):
                st.write(ai_reply)
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            st.stop()

        if len(matches) == 1:
            target = matches[0]
            deleted = delete_memory_by_category_index(target["category"], target["index"])
            ai_reply = "洋哥，我已经把【" + target["category"] + "】里的“" + deleted + "”删掉了。"
            with st.chat_message("assistant"):
                st.write(ai_reply)
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            st.stop()

        st.session_state.pending_delete = matches

        reply = "洋哥，我找到这些可能相关的：\n"
        for j, m in enumerate(matches, 1):
            reply += str(j) + ". 【" + m["category"] + "】" + m["content"] + "\n"
        reply += "你想删哪一条？回复：删第1条"

        with st.chat_message("assistant"):
            st.write(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.stop()

    elif action == "modify":
        matches = search_all_memory(old)

        if not matches:
            ai_reply = "洋哥，我在所有记忆里都没找到相关的。"
            with st.chat_message("assistant"):
                st.write(ai_reply)
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            st.stop()

        if len(matches) == 1:
            target = matches[0]
            old_content = modify_memory_by_category_index(target["category"], target["index"], new)
            ai_reply = "洋哥，我已经把【" + target["category"] + "】里的“" + old_content + "”改成“" + new + "”了。"
            with st.chat_message("assistant"):
                st.write(ai_reply)
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            st.stop()

        st.session_state.pending_modify = matches

        reply = "洋哥，我找到这些可能相关的：\n"
        for j, m in enumerate(matches, 1):
            reply += str(j) + ". 【" + m["category"] + "】" + m["content"] + "\n"
        reply += "你想改哪一条？回复：改第1条 新内容"

        with st.chat_message("assistant"):
            st.write(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.stop()

    elif action == "view":
        data = read_memory()
        memory_content = memory_to_text(data)
        ai_reply = "洋哥，这是我目前记住的：\n\n" + memory_content

        with st.chat_message("assistant"):
            st.write(ai_reply)

        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
        st.stop()

    data = read_memory()
    memory_text = memory_to_text(data)

    system_message = {
        "role": "system",
        "content": "你是小猪，洋哥的个人助手。\n"
                   "你的语气自然、踏实、不啰嗦。\n"
                   "你叫洋哥为“洋哥”。\n"
                   "你喜欢有条理地交流。\n"
                   "如果你对某件事没有把握，或者资料里没有相关信息，就直接说“这个我不太确定”，不要编造。\n\n"
                   "以下是洋哥的个人资料，请记住：\n" + memory_text
    }

    messages_to_send = [system_message] + st.session_state.messages

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages_to_send
    )

    ai_reply = response.choices[0].message.content

    with st.chat_message("assistant"):
        st.write(ai_reply)

    st.session_state.messages.append({"role": "assistant", "content": ai_reply})