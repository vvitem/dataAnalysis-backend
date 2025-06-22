#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入 Kuaishou 类
from src.app.kuaishou.index import Kuaishou

def test_kuaishou_extraction():
    print("测试快手视频数据提取")
    url = "https://v.kuaishou.com/2ErAl0v 初入社会以为自由翱翔，现实教我清醒成长！#成长必经课 #现实与理想较量"
    print(f"测试链接: {url}")
    
    try:
        ks = Kuaishou(url, 'url')
        result = ks.to_dict()
        print(result)
        if result.get("code") == 200:
            data = result.get("data", {})
            print("\n提取结果:")
            print(f"标题: {data.get('title', '未获取到标题')}")
            print(f"描述: {data.get('description', '未获取到描述')}")
            print(f"视频链接: {data.get('video', '未获取到视频链接')}")
            print(f"图片列表: {data.get('image_list', '未获取到图片')}")
        else:
            print(f"获取失败: {result.get('message', '未知错误')}")
    except Exception as e:
        print(f"测试出错: {e}")

if __name__ == "__main__":
    test_kuaishou_extraction() 