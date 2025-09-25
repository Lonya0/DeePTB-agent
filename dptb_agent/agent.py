from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
import os
from dp.agent.adapter.adk import CalculationMCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams
from dptb_agent.utils import get_sha

def bohrium_executor(email, pwd, pid, image_name: str=None, scass_type: str=None):
    return {
        "type": "dispatcher",
        "machine": {
            "batch_type": "Bohrium",
            "context_type": "Bohrium",
            "remote_profile": {
                "email": email,
                "password": pwd,
                "program_id": int(pid),
                "input_data": {
                    "image_name": "registry.dp.tech/dptech/dp/native/prod-19853/dpa-mcp:0.0.0" if image_name is None else image_name,
                    "job_type": "container",
                    "platform": "ali",
                    "scass_type": "1 * NVIDIA V100_32g" if scass_type is None else scass_type
                }
            }
        }
    }

def bohrium_storage(email, pwd, pid):
    return {
        "type": "bohrium",
        "username": email,
        "password": pwd,
        "project_id": int(pid)
    }

def mcp_tools(mcp_tools_url, bohr_exe, bohr_sto):
    return CalculationMCPToolset(
        connection_params=SseServerParams(url=mcp_tools_url),
        storage=bohr_exe,
        executor=bohr_sto
    )

model_config = {
    'model': os.getenv("DEEPSEEK_MODEL_NAME"),
    'api_base': os.getenv("DEEPSEEK_API_BASE"),
    'api_key': os.getenv("DEEPSEEK_API_KEY")
}

def create_llm_agent(userinfo: dict, mcp_tools_url: str, mode: str) -> LlmAgent:
    """根据用户信息创建LlmAgent"""

    if mode == "bohr":
        agent = LlmAgent(
            model=LiteLlm(**model_config),
            name=f"deeptb_agent_{get_sha(userinfo)[:8]}",
            description=f"DeePTB agent for project {userinfo['project_id']}.",
            instruction=(
                f"You are an expert in materials science and computational chemistry. "
                f"Help user {userinfo['username']} execute DeePTB tasks for project {userinfo['project_id']}. "
                "You are currently in Bohrium integrated mode, when using mcp tools, task will be run on Bohrium nodes."
                "This mean files input actually happens on Bohrium nodes, with path on them."
                f"The path is {userinfo['file_path']}, when using mcp tools use them as file path, otherwise the user give you a path."
                "You cannot access the file on Bohrium nodes, but to guide user to check on their Bohrium storage."
                f"Use default parameters if the users do not mention, but let users confirm them before submission. "
                f"Always verify the input parameters to users and provide clear explanations of results."
            ),
            tools=[mcp_tools(mcp_tools_url=mcp_tools_url,
                             bohr_exe=bohrium_executor(userinfo["username"],userinfo["password"],userinfo["project_id"]),
                             bohr_sto=bohrium_storage(userinfo["username"],userinfo["password"],userinfo["project_id"]))]
        )
    elif mode == "local":
        # TODO
        agent = LlmAgent(
            model=LiteLlm(**model_config),
            name=f"deeptb_agent_{get_sha(userinfo)[:8]}",
            description=f"DeePTB agent for project {userinfo['project_id']}.",
            instruction=(
                f"You are an expert in materials science and computational chemistry. "
                f"Help user {userinfo['username']} execute DeePTB tasks for project {userinfo['project_id']}. "
                f"Project files are stored at: {userinfo['file_path']}. "
                f"Use default parameters if the users do not mention, but let users confirm them before submission. "
                f"Always verify the input parameters to users and provide clear explanations of results."
            ),
            tools=[mcp_tools(mcp_tools_url=mcp_tools_url,
                             bohr_exe=bohrium_executor(userinfo["username"], userinfo["password"],
                                                       userinfo["project_id"]),
                             bohr_sto=bohrium_storage(userinfo["username"], userinfo["password"],
                                                      userinfo["project_id"]))]
        )
    else:
        raise "Mode illegal!!!"

    return agent


