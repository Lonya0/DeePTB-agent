import gradio as gr
import json
import os
from typing import Dict, List, Tuple
from dptb_agent.utils import get_sha
from dptb_agent.agent import create_agent
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
import asyncio
from dptb_agent import app_name

session_service = InMemorySessionService()

# 全局变量存储活跃的agents
active_agents: Dict[str, Agent] = {}


history_file_path = './chat_history'


def get_chat_history_file_path(sha_id: str) -> str:
    """获取聊天历史文件路径"""
    # 确保文件路径存在
    os.makedirs(history_file_path, exist_ok=True)
    return os.path.join(history_file_path, f"{sha_id[:16]}.json")


def load_chat_history(sha_id: str) -> List[List[str]]:
    """加载聊天历史记录"""
    history_file = get_chat_history_file_path(sha_id)

    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []


def save_chat_history(sha_id: str, history: List[List[str]]):
    """保存聊天历史记录"""
    history_file = get_chat_history_file_path(sha_id)

    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存聊天历史失败: {e}")


def login(username: str, password: str, project_id: str, file_path: str, mcp_tools_url, mode: str) -> Tuple[
    gr.update, gr.update, str, List[List[str]]]:
    """处理登录逻辑"""
    userinfo = zip_user_info(username, password, project_id, file_path)

    if not all([userinfo['username'], userinfo['password'], userinfo['project_id'], userinfo['file_path']]):
        return gr.update(visible=True), gr.update(visible=False), "请填写所有字段", []

    # 生成SHA ID
    sha_id = get_sha(userinfo)

    # 创建或获取agent
    if sha_id not in active_agents:
        try:
            agent = create_agent(userinfo, mcp_tools_url, mode=mode)
            active_agents[sha_id] = agent
        except Exception as e:
            return gr.update(visible=True), gr.update(visible=False), f"创建Agent失败: {str(e)}", []
    else:
        agent = active_agents[sha_id]

    # 加载聊天历史
    chat_history = load_chat_history(sha_id)

    # 返回更新后的界面和状态
    return (
        gr.update(visible=False),  # 隐藏登录界面
        gr.update(visible=True),  # 显示聊天界面
        f"登录成功! SHA ID: {sha_id[:16]}... 项目: {userinfo['project_id']}",  # 状态消息
        chat_history  # 聊天历史
    )

# modified from https://google.github.io/adk-docs/tutorials/agent-team/#step-1-your-first-agent-basic-weather-lookup
async def call_agent_async_stream(query: str, runner, user_id, session_id):
    """流式传输agent的响应"""
    content = types.Content(role='user', parts=[types.Part(text=query)])

    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        response_text = ""
        response_type = "info"
        
        # 提取事件中的文本内容
        if event.content and event.content.parts:
            response_text = event.content.parts[0].text if event.content.parts[0].text else ""
        
        # 根据事件类型分类
        if event.is_final_response():
            response_type = "final"
        elif event.actions and hasattr(event.actions, 'tool_calls') and event.actions.tool_calls:
            response_type = "tool_call"
            tool_names = [tool.name for tool in event.actions.tool_calls]
            response_text = f"🛠️ 调用工具: {', '.join(tool_names)}"
        elif "thinking" in str(type(event)).lower():
            response_type = "thinking"
            response_text = f"💭 {response_text}" if response_text else "💭 思考中..."
        
        # 如果有内容，yield出去
        if response_text:
            yield {"type": response_type, "text": response_text, "is_final": event.is_final_response()}

async def chat_with_agent_stream(message: str, history: List[List[str]], userinfo: dict):
    """流式处理与agent的聊天"""
    sha_id = get_sha(userinfo)

    if sha_id not in active_agents:
        yield history, "Agent未找到，请重新登录"
        return

    agent = active_agents[sha_id]
    session = await session_service.create_session(
        app_name=app_name,
        user_id=userinfo['username'],
        session_id=sha_id
    )

    runner = Runner(
        agent=agent,
        app_name=app_name,
        session_service=session_service
    )

    # 初始化响应文本
    full_response = ""
    new_history = history + [[message, ""]]  # 先添加空响应
    
    # 逐块获取响应并更新界面
    async for chunk in call_agent_async_stream(
        query=message, 
        runner=runner, 
        user_id=userinfo['username'], 
        session_id=sha_id
    ):
        # 根据类型格式化文本
        if chunk["type"] == "final":
            formatted_chunk = f"\n\n✅ {chunk['text']}"
        elif chunk["type"] == "tool_call":
            formatted_chunk = f"\n\n🛠️ {chunk['text']}"
        elif chunk["type"] == "thinking":
            formatted_chunk = f"\n💭 {chunk['text']}"
        else:
            formatted_chunk = f"\n{chunk['text']}"
        
        # 累加响应文本
        full_response += formatted_chunk
        
        # 更新聊天历史中的最后一条消息
        new_history[-1][1] = full_response.strip()
        
        # 实时更新界面
        yield new_history, ""

    # 最终保存聊天历史
    save_chat_history(sha_id, new_history)
    yield new_history, "完成"

def logout() -> Tuple[gr.update, gr.update, str, List[List[str]], str, str, str, str]:
    """处理登出逻辑"""
    return (
        gr.update(visible=True),  # 显示登录界面
        gr.update(visible=False),  # 隐藏聊天界面
        "已登出",  # 状态消息
        [],  # 清空聊天历史
        "", "", "", ""  # 清空登录表单
    )


def zip_user_info(username, password, project_id, file_path):
    return {
        'username': username,
        'password': password,
        'project_id': project_id,
        'file_path': file_path
    }


def create_interface(user_mode: str, mcp_tools_url: str):
    """创建Gradio界面"""
    with gr.Blocks(title="DeePTB Agent", theme=gr.themes.Soft()) as demo:
        # 状态变量
        sha_state = gr.State("")
        project_id_state = gr.State("")
        file_path_state = gr.State("")
        username_state = gr.State("")
        userinfo_state = gr.State({})
        mcp_tools_url_state = gr.State(mcp_tools_url)
        mode_state = gr.State(user_mode)

        gr.Markdown("# DeePTB Agent")

        with gr.Column(visible=True) as login_section:
            gr.Markdown("## 登录")

            with gr.Row():
                with gr.Column():
                    username = gr.Textbox(label="用户名", placeholder="请输入用户名")
                    password = gr.Textbox(label="密码", placeholder="请输入密码", type="password")
                    project_id = gr.Textbox(label="项目ID", placeholder="请输入项目ID")
                    file_path = gr.Textbox(
                        label="文件路径",
                        placeholder="请输入文件存储路径",
                        value="/personal"  # 默认路径
                    )

                    login_btn = gr.Button("登录", variant="primary")

            status_msg = gr.Textbox(label="状态", interactive=False)

        with gr.Column(visible=False) as chat_section:
            gr.Markdown("## 与DeePTB Agent协作")

            # 显示当前用户和项目信息
            current_info = gr.Textbox(
                label="当前会话信息",
                interactive=False,
                value=""
            )

            chatbot = gr.Chatbot(
                label="聊天记录",
                show_copy_button=True
            )

            with gr.Row():
                msg = gr.Textbox(
                    label="输入消息",
                    placeholder="输入你想对DeePTB Agent说的话...",
                    scale=4
                )
                send_btn = gr.Button("发送", variant="primary", scale=1)

            with gr.Row():
                clear_btn = gr.Button("清空对话")
                logout_btn = gr.Button("登出", variant="secondary")

            chat_status = gr.Textbox(label="聊天状态", interactive=False)

        # 更新会话信息显示
        def update_session_info(sha, username, project_id, file_path):
            if sha:
                return f"用户: {username} | 项目ID: {project_id} | 文件路径: {file_path}"
            return "未登录"

        # 登录按钮事件
        login_btn.click(
            fn=login,
            inputs=[username, password, project_id, file_path, mcp_tools_url_state, mode_state],
            outputs=[login_section, chat_section, status_msg, chatbot]
        ).then(
            lambda u, p, pid, fp:
            ({"username": u,
              "password": p,
              "project_id": pid,
              "file_path": fp},
             f"用户: {u} | 项目ID: {pid} | 文件路径: {fp}"),
            inputs=[username, password, project_id, file_path],
            outputs=[userinfo_state, current_info]
        )

        # 发送消息事件
        async def handle_send_message_stream(message, history, userinfo):
            if not message.strip():
                yield history, "消息不能为空"
            
            # 使用流式处理
            async for updated_history, status in chat_with_agent_stream(message, history, userinfo):
                yield updated_history, status

        # 修改按钮事件为流式处理
        send_btn.click(
            fn=handle_send_message_stream,
            inputs=[msg, chatbot, userinfo_state],
            outputs=[chatbot, chat_status]
        ).then(
            lambda: "",  # 清空输入框
            outputs=msg
        )

        # 修改回车事件为流式处理
        msg.submit(
            fn=handle_send_message_stream,
            inputs=[msg, chatbot, userinfo_state],
            outputs=[chatbot, chat_status]
        ).then(
            lambda: "",  # 清空输入框
            outputs=msg
        )

        # 清空对话
        clear_btn.click(
            fn=lambda sha, pid, fp: ([], "对话已清空"),
            inputs=[sha_state, project_id_state, file_path_state],
            outputs=[chatbot, chat_status]
        )

        # 登出按钮事件
        logout_btn.click(
            fn=logout,
            outputs=[
                login_section,
                chat_section,
                status_msg,
                chatbot,
                username,
                password,
                project_id,
                file_path
            ]
        ).then(
            lambda: ("", "", "", "", "未登录"),  # 清空状态
            outputs=[sha_state, username_state, project_id_state, file_path_state, current_info]
        )

    return demo
