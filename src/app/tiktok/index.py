import json
from bs4 import BeautifulSoup
import httpx
from src.utils import get_tiktok_logger, config
from src.utils.index import find_url
from src.utils.response import Response


logger = get_tiktok_logger()


class Tiktok:
    def __init__(self, text, type):
        self.text = text
        self.type = type
        self.url = find_url(text)
        self.description = ""
        self.image_list = []
        self.video = ""
        if not self.url:
            error_msg = f"无法从文本 '{text}' 中提取 URL"
            logger.error(error_msg)
            raise ValueError(error_msg)
        try:
            headers = {
                "User-Agent": config.MOBILE_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://www.google.com/",
            }
            response = httpx.get(
                self.url, follow_redirects=True, headers=headers, timeout=10.0
            )
            self.html = response.text
            self.soup = BeautifulSoup(self.html, "html.parser")
            # 提取页面标题
            self.title = self.soup.title.text if self.soup.title else ""

            # 提取页面内容
            self.extract_tiktok_data()
        except Exception as e:
            logger.error(f"获取抖音内容失败: {e}")
            raise e

    def extract_tiktok_data(self):
        """提取抖音内容"""
        try:
            # 提取页面内容
            self.image_data = {}
            self.video_data = {}
            scripts = self.soup.find_all("script")
            for script in scripts:
                if script.string and "window._ROUTER_DATA" in script.string:
                    data_text = script.string.split("window._ROUTER_DATA = ")[1]
                    logger.info(f"data_text: {data_text}")
                    # 判断有没有note_(id)/page, 没有的话取video_(id)/page
                    loaderData = json.loads(data_text).get("loaderData", {})
                    if "note_(id)" in data_text:
                        data_dict = loaderData.get("note_(id)/page", {})
                    else:
                        data_dict = loaderData.get("video_(id)/page", {})

                    self.get_dict_data(data_dict)
                    break
        except Exception as e:
            logger.error(f"提取抖音内容失败: {e}")
            raise e

    def get_dict_data(self, data_dict):
        """获取抖音内容"""
        try:
            videoInfoRes = data_dict.get("videoInfoRes", {})
            item_list = videoInfoRes.get("item_list", [])
            item_data = item_list[0] if len(item_list) > 0 else {}
            self.description = item_data.get("desc", "")

            get_image_data = item_data.get("images", [])
            if get_image_data:
                self.get_image_data(get_image_data)

            get_video_data = item_data.get("video", {})
            if get_video_data:
                self.get_video_data(get_video_data)
        except Exception as e:
            logger.error(f"获取抖音内容失败: {e}")
            raise e

    def get_image_data(self, get_image_data):
        """获取图片数据"""
        try:
            for item in get_image_data:
                self.image_list.append(item.get("url_list", [])[0])
        except Exception as e:
            logger.error(f"获取图片数据失败: {e}")
            raise e

    def get_video_data(self, get_video_data):
        """获取视频数据"""
        try:
            video_data = get_video_data.get("play_addr", {})
            video_url = video_data.get("url_list", [])[0] if video_data else ""
            self.video = video_url.replace("playwm", "play")
        except Exception as e:
            logger.error(f"获取视频数据失败: {e}")
            raise e

    def to_dict(self):
        """将对象转换为字典，用于 API 返回"""
        try:
            result = {
                "url": self.url,
                "final_url": "",
                "title": self.title,
                "description": self.description,
                "image_list": self.image_list,
                "video": self.video,
                "app_type": "tiktok",
            }
            return Response.success(result, "获取成功")
        except Exception as e:
            logger.error(f"转换为字典时出错: {str(e)}", exc_info=True)
            return Response.error("获取失败")
