"""
TTS 配置测试脚本

用于测试讯飞 TTS 语音合成功能是否正确配置。
使用方法：python scripts/test_tts_config.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.integrations.tts.client import get_tts_client
from backend.settings import get_settings


async def test_tts():
    """测试 TTS 语音合成功能"""
    print("=" * 60)
    print("讯飞 TTS 语音合成配置测试")
    print("=" * 60)
    
    settings = get_settings()
    
    # 检查配置
    print("\n1. 检查配置信息：")
    print(f"   TTS_APP_ID: {'[OK]' if settings.tts_app_id else '[FAIL]'}")
    print(f"   TTS_API_KEY: {'[OK]' if settings.tts_api_key else '[FAIL]'}")
    print(f"   TTS_API_SECRET: {'[OK]' if settings.tts_api_secret else '[FAIL]'}")
    print(f"   TTS_WS_URL: {settings.tts_ws_url}")
    
    if not (settings.tts_app_id and settings.tts_api_key and settings.tts_api_secret):
        print("\n[ERROR] 请在 .env 文件中配置 TTS_APP_ID、TTS_API_KEY、TTS_API_SECRET")
        print("\n配置步骤：")
        print("1. 前往 https://console.xfyun.cn/services/tts 创建应用")
        print("2. 获取 APP_ID、API_KEY、API_SECRET")
        print("3. 在项目根目录创建 .env 文件，填入以下配置：")
        print("   TTS_APP_ID=你的 app_id")
        print("   TTS_API_KEY=你的 api_key")
        print("   TTS_API_SECRET=你的 api_secret")
        print("   TTS_WS_URL=wss://tts-api.xfyun.cn/v2/tts")
        return False
    
    client = get_tts_client()
    
    print(f"\n2. 客户端状态：{'[OK]' if client.configured else '[FAIL]'}")
    
    # 测试合成
    print("\n3. 测试语音合成：")
    test_text = "你好，欢迎使用 EduAgent 智能学习平台"
    test_voice = "x4_xiaoyan"  # 使用新音色参数
    
    print(f"   测试文本：{test_text}")
    print(f"   音色：{test_voice}")
    
    try:
        print("   正在合成音频...")
        audio_data = await client.synthesize(test_text, voice=test_voice)
        
        if audio_data:
            print(f"   [OK] 合成成功！音频大小：{len(audio_data)} bytes")
            
            # 保存测试文件
            output_path = Path(__file__).resolve().parent / "test_tts_output.mp3"
            with open(output_path, "wb") as f:
                f.write(audio_data)
            
            print(f"   [OK] 音频已保存至：{output_path}")
            print("\n[SUCCESS] TTS 配置测试通过！可以正常使用语音合成功能。")
            return True
        else:
            print("   [FAIL] 未返回音频数据")
            return False
            
    except Exception as e:
        print(f"   [FAIL] 合成失败：{e}")
        print("\n可能的原因：")
        print("1. 讯飞账号欠费或套餐包用尽")
        print("2. APP_ID、API_KEY、API_SECRET 填写错误")
        print("3. 音色参数名不正确（请使用控制台已开启的音色）")
        print("4. 网络连接问题")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_tts())
    sys.exit(0 if success else 1)
