import sys
import os
import json

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入 Douyin 类
from src.app.douyin.index import Douyin

def test_douyin_video():
    """测试抖音视频数据提取"""
    # 测试用的抖音视频链接 - 直接使用完整 URL
    test_urls = [
        "https://v.douyin.com/bXIR7enaYbM/",  # 短链接
    ]
    
    for url in test_urls:
        print(f"\n===== 测试链接: {url} =====")
        try:
            print("创建 Douyin 对象...")
            douyin = Douyin(url, "webp")
            print(f"提取到的 URL: {douyin.url}")
            print("转换为字典...")
            result = douyin.to_dict()
            
            # 打印结果
            print("\n解析结果:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
            # 特别检查图片列表
            if result.get("data", {}).get("image_list"):
                print("\n获取到的图片列表:")
                for idx, img_url in enumerate(result["data"]["image_list"], 1):
                    print(f"{idx}. {img_url}")
            else:
                print("\n警告: 未获取到任何图片")
                
        except Exception as e:
            import traceback
            print(f"测试失败: {str(e)}")
            print(traceback.format_exc())

if __name__ == "__main__":
    test_douyin_video() 