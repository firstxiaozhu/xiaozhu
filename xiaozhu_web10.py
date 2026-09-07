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

def save_chat_history(role, content):
    with open("chat_history.txt", "a", encoding="utf-8") as f:
        f.write(role + ":" + content + "\n")

def load_chat_history():
    try:
        with open("chat_history.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

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

def search_chat_history(keyword):
    history = load_chat_history()
    if not history:
        return []

    result = []
    for line in history.strip().split("\n"):
        if keyword in line:
            result.append(line)

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
                          "动作只能是：add、delete、modify、view、search、progress、chat\n"
             "add：用户提供了新的个人信息或重要事情，需要记住\n"
             "delete：用户想删除某条记忆\n"
             "modify：用户想修改某条记忆\n"
             "view：用户想查看记忆\n"
             "search：用户想回忆以前说过或聊过的事情\n"
             "progress：用户想梳理某件事的进展或阶段\n"
             "chat：普通聊天，不需要操作记忆\n\n"
             "分类只能是：基本情况、目标计划、习惯偏好、正在学习、重要事情、聊天笔记\n"
             "如果不是记忆操作，category、content、old、new都返回空字符串。\n"
             "search时，old返回用户想回忆的关键词。\n"
             "只返回JSON，不要解释。"},
            {"role": "user", "content": user_input}
        ]
    )
    result = response.choices[0].message.content
    return json5.loads(result)

def analyze_note(user_input, ai_reply):
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是小猪的笔记整理模块。\n"
             "根据洋哥和小猪的这段对话，判断有没有值得记到聊天笔记里的内容。\n"
             "如果值得记，返回JSON：{\"note\": true, \"content\": \"笔记内容\"}。\n"
             "如果不值得记，返回：{\"note\": false, \"content\": \"\"}。\n"
             "笔记要简洁，只记事实、决定、想法或进展，不要评价。\n"
             "只返回JSON，不要解释。"},
            {"role": "user", "content": "洋哥：" + user_input + "\n小猪：" + ai_reply}
        ]
    )
    result = response.choices[0].message.content
    return json5.loads(result)

st.set_page_config(page_title="小猪", page_icon="🐷", layout="wide")

st.markdown("""
<style>
    .main-title {
        font-size: 1.6rem;
        font-weight: bold;
        color: #333;
        margin-bottom: 0.5rem;
    }
    .stChatMessage {
        border-radius: 12px;
    }
    @media only screen and (max-width: 768px) {
        .main-title {
            font-size: 1.3rem;
        }
        section.main {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🐷 小猪</div>', unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

    history = load_chat_history()
    if history:
        for line in history.strip().split("\n"):
            if line.startswith("user:"):
                st.session_state.messages.append({"role": "user", "content": line[5:]})
            elif line.startswith("assistant:"):
                st.session_state.messages.append({"role": "assistant", "content": line[10:]})

if "pending_delete" not in st.session_state:
    st.session_state.pending_delete = None

if "pending_modify" not in st.session_state:
    st.session_state.pending_modify = None

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

col1, col2 = st.columns([1, 5])

col1, col2 = st.columns(2)

with col1:
    if st.button("今日小结", use_container_width=True):
        history = load_chat_history()

        if not history:
            ai_reply = "洋哥，今天还没有聊天记录。"
        else:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是小猪。请根据洋哥今天的聊天记录，生成一份简洁的每日小结。\n"
                     "包括：今天聊了什么、有什么重要事情、有什么需要后续关注的。\n"
                     "只根据聊天记录总结，不能编造。\n"
                     "用简洁的条目列出。"},
                    {"role": "user", "content": "以下是今天的聊天记录：\n" + history}
                ]
            )
            ai_reply = response.choices[0].message.content

        with st.chat_message("assistant"):
            st.write(ai_reply)

        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
        save_chat_history("assistant", ai_reply)
        st.rerun()

    if st.button("习惯打卡", use_container_width=True):
        data = read_memory()
        habits = data.get("习惯偏好", [])

        if not habits:
            ai_reply = "洋哥，你还没有告诉我什么习惯想坚持。\n你可以先说，比如：我想坚持早睡早起。"
        else:
            habit_text = "\n".join(habits)

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是小猪。下面是洋哥想坚持的习惯，请帮他做一次简单的习惯打卡回顾。\n"
                     "用鼓励的语气，提醒他坚持。不要编造打卡数据。\n"
                     "可以问他今天做得怎么样。"},
                    {"role": "user", "content": "洋哥的习惯：\n" + habit_text}
                ]
            )
            ai_reply = response.choices[0].message.content

        with st.chat_message("assistant"):
            st.write(ai_reply)

        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
        save_chat_history("assistant", ai_reply)
        st.rerun()

with col2:
    if st.button("本周复盘", use_container_width=True):
        history = load_chat_history()

        if not history:
            ai_reply = "洋哥，暂时还没有聊天记录。"
        else:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是小猪。请根据洋哥近期的聊天记录，生成一份周复盘。\n"
                     "包括：这周主要聊了什么、有哪些重要事情、有什么进展、下周可能需要注意什么。\n"
                     "只根据聊天记录总结，不能编造。\n"
                     "用简洁的条目列出。"},
                    {"role": "user", "content": "以下是近期的聊天记录：\n" + history}
                ]
            )
            ai_reply = response.choices[0].message.content

        with st.chat_message("assistant"):
            st.write(ai_reply)

        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
        save_chat_history("assistant", ai_reply)
        st.rerun()

    if st.button("学习计划", use_container_width=True):
        data = read_memory()
        learning = data.get("正在学习", [])

        if not learning:
            ai_reply = "洋哥，你还没有告诉我你正在学什么。\n你可以先说，比如：我在学Python。"
        else:
            learning_text = "\n".join(learning)

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是小猪。下面是洋哥正在学习的内容，请帮他制定一份简单可行的学习计划。\n"
                     "要结合他目前的基础，不要太难，也不要太笼统。\n"
                     "只根据提供的内容制定，不要编造。"},
                    {"role": "user", "content": "洋哥正在学习：\n" + learning_text}
                ]
            )
            ai_reply = response.choices[0].message.content

        with st.chat_message("assistant"):
            st.write(ai_reply)

        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
        save_chat_history("assistant", ai_reply)
        st.rerun()

user_input = st.chat_input("洋哥，请说")

if user_input:
    with st.chat_message("user"):
        st.write(user_input)

    st.session_state.messages.append({"role": "user", "content": user_input})
    save_chat_history("user", user_input)

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
            save_chat_history("assistant", ai_reply)
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
            save_chat_history("assistant", ai_reply)
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
            save_chat_history("assistant", ai_reply)
            st.stop()

        if len(matches) == 1:
            target = matches[0]
            deleted = delete_memory_by_category_index(target["category"], target["index"])
            ai_reply = "洋哥，我已经把【" + target["category"] + "】里的“" + deleted + "”删掉了。"
            with st.chat_message("assistant"):
                st.write(ai_reply)
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            save_chat_history("assistant", ai_reply)
            st.stop()

        st.session_state.pending_delete = matches

        reply = "洋哥，我找到这些可能相关的：\n"
        for j, m in enumerate(matches, 1):
            reply += str(j) + ". 【" + m["category"] + "】" + m["content"] + "\n"
        reply += "你想删哪一条？回复：删第1条"

        with st.chat_message("assistant"):
            st.write(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        save_chat_history("assistant", reply)
        st.stop()

    elif action == "modify":
        matches = search_all_memory(old)

        if not matches:
            ai_reply = "洋哥，我在所有记忆里都没找到相关的。"
            with st.chat_message("assistant"):
                st.write(ai_reply)
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            save_chat_history("assistant", ai_reply)
            st.stop()

        if len(matches) == 1:
            target = matches[0]
            old_content = modify_memory_by_category_index(target["category"], target["index"], new)
            ai_reply = "洋哥，我已经把【" + target["category"] + "】里的“" + old_content + "”改成“" + new + "”了。"
            with st.chat_message("assistant"):
                st.write(ai_reply)
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            save_chat_history("assistant", ai_reply)
            st.stop()

        st.session_state.pending_modify = matches

        reply = "洋哥，我找到这些可能相关的：\n"
        for j, m in enumerate(matches, 1):
            reply += str(j) + ". 【" + m["category"] + "】" + m["content"] + "\n"
        reply += "你想改哪一条？回复：改第1条 新内容"

        with st.chat_message("assistant"):
            st.write(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        save_chat_history("assistant", reply)
        st.stop()

    elif action == "view":
        data = read_memory()
        memory_content = memory_to_text(data)
        ai_reply = "洋哥，这是我目前记住的：\n\n" + memory_content

        with st.chat_message("assistant"):
            st.write(ai_reply)

        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
        save_chat_history("assistant", ai_reply)
        st.stop()

    elif action == "progress":
        memory_matches = search_all_memory(old)
        chat_matches = search_chat_history(old)

        related = []

        for m in memory_matches:
            related.append("【" + m["category"] + "】" + m["content"])

        for c in chat_matches:
            related.append(c)

        if not related:
            ai_reply = "洋哥，我暂时没有找到关于“" + old + "”的记录，没法帮你梳理进度。"
            with st.chat_message("assistant"):
                st.write(ai_reply)
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            save_chat_history("assistant", ai_reply)
            st.stop()

        related_text = "\n".join(related)

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是小猪。下面是一些关于洋哥某件事的零散信息。\n"
                 "请根据这些信息，帮他梳理目前的进展或阶段。\n"
                 "只能根据提供的信息整理，不能编造。\n"
                 "如果信息不够完整，就如实说明目前只能看出这些。"},
                {"role": "user", "content": "洋哥想梳理关于“" + old + "”的进展。以下是相关信息：\n" + related_text}
            ]
        )

        ai_reply = response.choices[0].message.content

        with st.chat_message("assistant"):
            st.write(ai_reply)

        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
        save_chat_history("assistant", ai_reply)
        note_check = analyze_note(user_input, ai_reply)
 
        if note_check["note"]:
            add_to_category("聊天笔记", note_check["content"])
            st.toast("小猪记了一条聊天笔记")
        st.stop()

    elif action == "search":
        memory_matches = search_all_memory(old)
        chat_matches = search_chat_history(old)

        related = []

        for m in memory_matches:
            related.append("【" + m["category"] + "】" + m["content"])

        for c in chat_matches:
            related.append(c)

        if not related:
            ai_reply = "洋哥，我暂时没找到和“" + old + "”相关的内容。"
            with st.chat_message("assistant"):
                st.write(ai_reply)
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            save_chat_history("assistant", ai_reply)
            st.stop()

        related_text = "\n".join(related)

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是小猪。下面会给你一些找到的相关信息。\n"
                 "你只能根据这些信息回答，绝对不能编造、推测或补充不存在的内容。\n"
                 "如果相关信息很少，就只说你找到什么，不要展开想象。\n"
                 "如果相关信息里没有细节，就直接说“我只找到这些”。"},
                {"role": "user", "content": "洋哥想回忆关于“" + old + "”的内容。以下是找到的相关信息：\n" + related_text}
            ]
        )

        ai_reply = response.choices[0].message.content

        with st.chat_message("assistant"):
            st.write(ai_reply)

        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
        save_chat_history("assistant", ai_reply)
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
    save_chat_history("assistant", ai_reply)

    note_check = analyze_note(user_input, ai_reply)

    if note_check["note"]:
        added = add_to_category("聊天笔记", note_check["content"])
        if added:
            st.toast("小猪记了一条聊天笔记")
        else:
            st.toast("小猪：这条笔记已经记过了")