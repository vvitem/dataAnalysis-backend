import json
from bs4 import BeautifulSoup
import httpx
import re
from src.utils import get_analyze_logger, config
from src.utils.index import find_url
from src.utils.response import Response


logger = get_analyze_logger()


class Douyin:
    def __init__(self, text, type):
        self.text = text
        self.type = type
        self.url = find_url(text)
        self.description = ""
        self.image_list = []
        self.video = ""
        self.title = ""  # 初始化标题为空字符串，用于存放用户名
        
        if not self.url:
            error_msg = f"无法从文本 '{text}' 中提取 URL"
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
            
            # 提取页面内容
            self.extract_douyin_data()
        except Exception as e:
            logger.error(f"获取抖音内容失败: {e}")
            raise e

    def extract_douyin_data(self):
        """提取抖音内容"""
        try:
            # 首先尝试提取用户名称
            self.extract_user_name()
            
            # 提取页面内容
            self.image_data = {}
            self.video_data = {}
            scripts = self.soup.find_all("script")
            for script in scripts:
                if script.string and "window._ROUTER_DATA" in script.string:
                    data_text = script.string.split("window._ROUTER_DATA = ")[1]
                    # 判断有没有note_(id)/page, 没有的话取video_(id)/page
                    loaderData = json.loads(data_text).get("loaderData", {})
                    if "note_(id)" in data_text:
                        data_dict = loaderData.get("note_(id)/page", {})
                    else:
                        data_dict = loaderData.get("video_(id)/page", {})

                    self.get_dict_data(data_dict)
                    break
        except Exception as e:
            raise e
            
    def extract_user_name(self):
        """尝试从页面提取用户名称"""
        try:
            # 方法1: 从meta标签提取
            meta_author = self.soup.find("meta", property="og:site_name")
            if meta_author and meta_author.get("content") and meta_author.get("content") != "抖音":
                self.title = meta_author.get("content")
                return
                
            # 方法2: 尝试从页面中提取用户名元素
            user_elements = self.soup.select('.author-name, .user-name, .nickname, .user-info-name')
            for elem in user_elements:
                text = elem.get_text().strip()
                if text and len(text) > 1 and text != "抖音":
                    self.title = text
                    return
            
            # 方法3: 从脚本数据中提取用户名
            for script in self.soup.find_all("script"):
                if script.string:
                    # 尝试找到用户名相关的数据
                    user_patterns = [
                        r'"nickname":"([^"]+)"',
                        r'"author":"([^"]+)"',
                        r'"userName":"([^"]+)"',
                        r'"user":\{[^}]*"name":"([^"]+)"'
                    ]
                    for pattern in user_patterns:
                        matches = re.findall(pattern, script.string)
                        if matches:
                            user_name = matches[0].replace('\\n', ' ').replace('\\t', ' ')
                            user_name = user_name.replace('\\u002F', '/').replace('\\/', '/').replace('\\', '')
                            if user_name and len(user_name) > 1 and user_name != "抖音":
                                self.title = user_name
                                return
            
            # 如果还没有找到用户名，尝试从页面标题中提取
            if self.soup.title and self.soup.title.text:
                page_title = self.soup.title.text.strip()
                # 尝试提取页面标题中的用户名部分
                title_patterns = [
                    r'^(.*?)的主页$',
                    r'^(.*?)的抖音视频$',
                    r'^(.*?)创作的视频$'
                ]
                for pattern in title_patterns:
                    title_match = re.search(pattern, page_title)
                    if title_match:
                        user_name = title_match.group(1).strip()
                        if user_name and len(user_name) > 1:
                            self.title = user_name
                            return
            
        except Exception as e:
            logger.warning(f"提取抖音用户名失败: {e}")

    def get_dict_data(self, data_dict):
        """获取抖音内容"""
        try:
            videoInfoRes = data_dict.get("videoInfoRes", {})
            item_list = videoInfoRes.get("item_list", [])
            item_data = item_list[0] if len(item_list) > 0 else {}
            self.description = item_data.get("desc", "")
            
            # 从数据中提取用户名
            if not self.title:
                author = item_data.get("author", {})
                if author:
                    user_name = author.get("nickname", "")
                    if user_name and len(user_name) > 1:
                        self.title = user_name

            get_image_data = item_data.get("images", [])
            if get_image_data:
                self.get_image_data(get_image_data)

            get_video_data = item_data.get("video", {})
            if get_video_data:
                self.get_video_data(get_video_data)
                
            # 如果描述中包含@用户名，尝试提取作为备选用户名
            if not self.title and self.description:
                at_matches = re.findall(r'@([^\s#]+)', self.description)
                if at_matches:
                    self.title = at_matches[0]
                    
            # 如果仍然没有标题，使用默认值
            if not self.title:
                self.title = "抖音用户"
        except Exception as e:
            raise e

    def get_image_data(self, get_image_data):
        """获取图片数据"""
        try:
            for item in get_image_data:
                self.image_list.append(item.get("url_list", [])[0])
        except Exception as e:
            raise e

    def get_video_data(self, get_video_data):
        """获取视频数据"""
        try:
            video_data = get_video_data.get("play_addr", {})
            video_url = video_data.get("url_list", [])[0] if video_data else ""
            if 'mp3' in video_url:
                self.video = ""
            else:
                self.video = video_url.replace("playwm", "play")
            
            # 获取视频封面图
            cover_data = get_video_data.get("cover", {})
            if cover_data:
                cover_url = cover_data.get("url_list", [])[0] if cover_data else ""
                if cover_url:
                    self.image_list.append(cover_url)
            
            # 如果没有封面，尝试获取原始封面
            if not self.image_list:
                origin_cover = get_video_data.get("origin_cover", {})
                if origin_cover:
                    origin_cover_url = origin_cover.get("url_list", [])[0] if origin_cover else ""
                    if origin_cover_url:
                        self.image_list.append(origin_cover_url)
                        
            # 尝试从动态封面获取
            if not self.image_list:
                dynamic_cover = get_video_data.get("dynamic_cover", {})
                if dynamic_cover:
                    dynamic_cover_url = dynamic_cover.get("url_list", [])[0] if dynamic_cover else ""
                    if dynamic_cover_url:
                        self.image_list.append(dynamic_cover_url)
        except Exception as e:
            raise e

    def to_dict(self):
        """将对象转换为字典，用于 API 返回"""
        try:
            # 确保有标题
            if not self.title:
                self.title = "抖音用户"
                
            result = {
                "url": self.url,
                "final_url": "",
                "title": self.title,
                "description": self.description,
                "image_list": self.image_list,
                "video": self.video,
                "app_type": "douyin",
            }
            return Response.success(result, "获取成功")
        except Exception as e:
            logger.error(f"抖音转换为字典时出错: {str(e)}", exc_info=True)
            return Response.error("获取失败")
