from dptb_agent.host import create_interface
import os
import argparse
import sys
from typing import Dict
from dotenv import load_dotenv
import logging


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="DPTB Agent 启动程序")

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=50005,
        help="服务器端口号 (默认: 50005)"
    )

    parser.add_argument(
        "--host", "-l",
        type=str,
        default="0.0.0.0",
        help="服务器主机地址 (默认: 0.0.0.0)"
    )

    parser.add_argument(
        "--mcp_tools",
        type=str,
        default="http://0.0.0.0:50001/sse",
        help="DeePTB agent tools 的 mcp tools链接 (默认: http://0.0.0.0:50001/sse)"
    )

    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["local", "bohr"],
        default="local",
        help="运行模式: local(本地模式, 存储将会从本地读取) 或 bohr(Bohrium模式，存储将存储于bohr存储) (默认: local)"
    )

    parser.add_argument(
        "--share", "-s",
        action="store_true",
        help="是否生成公共分享链接 (默认: False)"
    )

    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Gradio开启debug模式 (默认: False)"
    )

    parser.add_argument(
        "--api-key",
        type=str,
        help="Google API密钥 (优先级高于环境变量)"
    )

    return parser.parse_args()

def set_logging(debug: bool):
    if debug:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            datefmt='%d %H:%M:%S',
                            filename='dptb_agent.log',
                            filemode='w')
    else:
        logging.basicConfig(level=logging.WARNING,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            datefmt='%d %H:%M:%S',
                            filename='dptb_agent.log',
                            filemode='w')


def main():
    """主函数"""
    if load_dotenv():
        print("环境变量已根据`.env`文件读入")
    else:
        print("未找到`.env`文件或无任何变量被读入")

    args = parse_arguments()
    set_logging(args.debug)
    logging.debug(f"启动参数: {args}")

    # 设置API密钥（命令行参数优先）
    if args.api_key:
        os.environ["GOOGLE_API_KEY"] = args.api_key
    elif not os.getenv("GOOGLE_API_KEY"):
        print("警告: GOOGLE_API_KEY环境变量未设置，请通过--api-key参数设置或设置环境变量")

    # 创建并启动界面
    demo = create_interface(user_mode=args.mode,
                            mcp_tools_url=args.mcp_tools)

    print(f"启动参数: 主机={args.host}, 端口={args.port}, 模式={args.mode}, 分享={args.share}, 调试={args.debug}")

    try:
        demo.launch(
            server_name=args.host,
            server_port=args.port,
            share=args.share,
            debug=args.debug
        )
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()