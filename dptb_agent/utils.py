import hashlib

def get_sha(userinfo: dict) -> str:
    """根据登录信息生成SHA256值"""
    combined_string = f"{userinfo['username']}:{userinfo['password']}"
    return hashlib.sha256(combined_string.encode()).hexdigest()