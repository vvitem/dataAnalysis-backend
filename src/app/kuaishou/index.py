import json
import re
from bs4 import BeautifulSoup
import httpx
from src.utils import get_analyze_logger, config
from src.utils.index import find_url
from src.utils.response import Response


logger = get_analyze_logger()


class Kuaishou:
    def __init__(self, text, type):
        self.text = text
        self.type = type
        self.url = find_url(text)
        self.description = ""
        self.video = ""
        self.image_list = []
        self.image_prefix = "https://tx2.a.kwimgs.com/"
        self.title = ""  # 初始化标题为空字符串，而不是使用页面默认标题
        if not self.url:
            error_msg = f"无法从文本 '{text}' 中提取 URL"
            logger.error(error_msg)
            raise ValueError(error_msg)
        try:
            # 尝试两种 User-Agent，优先使用移动设备 UA
            headers_list = [
                # 移动设备 UA
                {
                    "User-Agent": config.MOBILE_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Referer": "https://www.google.com/",
                },
                # PC 设备 UA
                {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Referer": "https://www.google.com/",
                }
            ]
            
            # 尝试不同的 UA 请求
            html = ""
            response = None
            for headers in headers_list:
                try:
                    response = httpx.get(
                        self.url, follow_redirects=True, headers=headers, timeout=10.0
                    )
                    html = response.text
                    logger.info(f"快手请求成功，内容长度: {len(html)}")
                    if "window.INIT_STATE" in html:
                        break
                except Exception as e:
                    logger.warning(f"快手请求失败，尝试其他 UA: {e}")
                    continue
            
            # 如果所有请求都失败，使用最后一次的响应
            if not html and response:
                html = response.text
            
            self.html = html
            self.soup = BeautifulSoup(self.html, "html.parser")
            
            # 提取页面内容
            self.extract_kuaishou_data()
        except Exception as e:
            logger.error(f"获取快手内容失败: {e}")
            raise e

    def extract_kuaishou_data(self):
        """提取快手内容"""
        try:
            # 提取页面内容
            self.image_data = {}
            self.video_data = {}
            
            # 方法 1: 从 window.INIT_STATE 提取数据
            scripts = self.soup.find_all("script")
            data_found = False
            
            for script in scripts:
                if script.string and "window.INIT_STATE" in script.string:
                    try:
                        data_text = script.string.split("window.INIT_STATE = ")[1]
                        # 处理可能的 JS 代码结束位置
                        if ";" in data_text:
                            data_text = data_text.split(";")[0]
                            
                        # 提取出来的数据转成dict
                        data_dict = json.loads(data_text)
                        self.data_dict = data_dict
                        self.get_dict_data()
                        data_found = True
                        break
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析 INIT_STATE JSON 失败: {e}")
                    except Exception as e:
                        logger.warning(f"处理 INIT_STATE 数据失败: {e}")
            
            # 方法 2: 如果没有找到初始数据，尝试从页面中提取信息
            if not data_found:
                logger.info("使用备用方法提取快手数据")
                self.extract_data_from_html()
                
        except Exception as e:
            logger.error(f"提取快手数据失败: {e}")
            raise e
    
    def extract_data_from_html(self):
        """从 HTML 页面直接提取数据"""
        try:
            # 提取用户名称
            user_name = ""
            
            # 尝试从 meta 标签提取用户名
            meta_author = self.soup.find("meta", property="og:site_name")
            if meta_author and meta_author.get("content") and meta_author.get("content") != "快手":
                user_name = meta_author.get("content")
            
            # 如果没有找到用户名，尝试从其他元素获取
            if not user_name:
                user_elements = self.soup.select('.user-name, .author-name, .creator-name, .nickname')
                for elem in user_elements:
                    text = elem.get_text().strip()
                    if text and len(text) > 1 and text != "快手":
                        user_name = text
                        break
            
            # 从脚本中提取用户名
            if not user_name:
                for script in self.soup.find_all("script"):
                    if script.string:
                        user_patterns = [
                            r'"userName":"([^"]+)"',
                            r'"authorName":"([^"]+)"',
                            r'"nickname":"([^"]+)"',
                            r'"user":\{[^}]*"name":"([^"]+)"',
                        ]
                        for pattern in user_patterns:
                            user_matches = re.findall(pattern, script.string)
                            if user_matches:
                                u_name = user_matches[0].replace('\\n', ' ').replace('\\t', ' ')
                                u_name = u_name.replace('\\u002F', '/').replace('\\/', '/').replace('\\', '')
                                if u_name and len(u_name) > 1 and u_name != "快手":
                                    user_name = u_name
                                    break
                        if user_name:
                            break
            
            # 直接设置标题为用户名
            if user_name:
                self.title = user_name
            
            # 获取视频描述
            video_description = ""
            
            # 尝试从 meta 标签提取描述
            meta_description = self.soup.find("meta", attrs={"name": "description"})
            if meta_description and meta_description.get("content"):
                video_description = meta_description.get("content")
                self.description = video_description
            
            # 尝试从 meta 标签提取描述 (OpenGraph)
            if not video_description:
                og_description = self.soup.find("meta", property="og:description")
                if og_description and og_description.get("content"):
                    video_description = og_description.get("content")
                    self.description = video_description
            
            # 如果原始链接中有文本描述，使用它作为描述信息
            if not video_description and " http" in self.text:
                # 提取链接前面的文本作为描述
                desc_text = self.text.split(" http")[0].strip()
                if desc_text and len(desc_text) > 2:  # 确保文本有意义
                    video_description = desc_text
                    self.description = video_description
            
            # 如果没有用户名但有描述信息，尝试从描述中提取可能的用户名
            if not self.title and self.description:
                # 尝试查找"@用户名"格式
                at_matches = re.findall(r'@([^\s#]+)', self.description)
                if at_matches:
                    self.title = at_matches[0]
            
            # 从脚本中查找更多信息
            for script in self.soup.find_all("script"):
                if script.string:
                    # 查找视频描述
                    if not self.description:
                        # 尝试查找caption或description字段
                        desc_patterns = [
                            r'"caption":"([^"]+)"',
                            r'"description":"([^"]+)"', 
                            r'"desc":"([^"]+)"',
                            r'"title":"([^"]+)"'
                        ]
                        
                        for pattern in desc_patterns:
                            desc_matches = re.findall(pattern, script.string)
                            if desc_matches:
                                desc_text = desc_matches[0].replace('\\n', ' ').replace('\\t', ' ')
                                desc_text = desc_text.replace('\\u002F', '/').replace('\\/', '/').replace('\\', '')
                                if desc_text and len(desc_text) > 2:  # 确保文本有意义
                                    self.description = desc_text
                                    break
                        
                    # 查找视频 URL
                    video_matches = re.findall(r'"url":"(https?://[^"]+\.mp4[^"]*)"', script.string)
                    if video_matches:
                        self.video = video_matches[0].replace('\\u002F', '/').replace('\\/', '/')
                    
                    # 查找图片 URL，特别是封面图
                    if not self.image_list:
                        # 特别查找封面图片，通常包含"cover"或"poster"关键词
                        cover_matches = re.findall(r'"(poster|cover|coverUrl|thumbnail)":"(https?://[^"]+\.(jpg|jpeg|png|webp)[^"]*)"', script.string, re.IGNORECASE)
                        if cover_matches:
                            for match in cover_matches:
                                image_url = match[1].replace('\\u002F', '/').replace('\\/', '/')
                                # 排除用户头像
                                if "uhead" not in image_url and image_url not in self.image_list:
                                    self.image_list.append(image_url)
                                    break
                        
                        # 如果没找到明确的封面图，则查找一般图片
                        if not self.image_list:
                            img_matches = re.findall(r'"url":"(https?://[^"]+\.(jpg|jpeg|png|webp)[^"]*)"', script.string)
                            for img_match in img_matches:
                                image_url = img_match[0].replace('\\u002F', '/').replace('\\/', '/')
                                # 排除用户头像
                                if "uhead" not in image_url and image_url not in self.image_list:
                                    self.image_list.append(image_url)
                                    break
            
            # 尝试从页面文本内容中提取描述
            if not self.description:
                # 查找可能包含描述的元素
                elements = self.soup.select('.video-info, .caption, .description, .desc, .title, h1, h2')
                for elem in elements:
                    text = elem.get_text().strip()
                    if text and len(text) > 2 and text != "快手":
                        self.description = text
                        break
                        
            # 尝试从 meta 标签提取封面图
            if not self.image_list:
                meta_image = self.soup.find("meta", property="og:image")
                if meta_image and meta_image.get("content"):
                    image_url = meta_image.get("content")
                    # 排除可能的用户头像
                    if not "uhead" in image_url:
                        self.image_list.append(image_url)
            
            # 如果还没有图片，尝试从 img 标签获取
            if not self.image_list:
                # 首先尝试查找带有封面相关类名或ID的图片
                cover_imgs = self.soup.select("img.cover, img.poster, img.thumbnail, img#cover, img#poster, img#thumbnail")
                if cover_imgs:
                    for img in cover_imgs:
                        src = img.get("src")
                        if src and "uhead" not in src:
                            self.image_list.append(src)
                            break
                
                # 如果没找到明确的封面图，查找所有图片
                if not self.image_list:
                    for img in self.soup.find_all("img"):
                        src = img.get("src")
                        if src and ("jpg" in src or "jpeg" in src or "png" in src or "webp" in src) and "uhead" not in src:
                            self.image_list.append(src)
                            break
            
            # 如果还是没有标题，使用默认值
            if not self.title:
                self.title = "快手用户"
        
        except Exception as e:
            logger.warning(f"从 HTML 提取数据失败: {e}")

    def get_dict_data(self):
        """获取dict数据"""
        try:
            # 尝试提取用户名
            user_name = ""
            
            # 尝试不同的数据结构路径
            # 路径 1: 原始路径
            data_list = list(self.data_dict.values())
            if len(data_list) > 2:
                obj1_data = data_list[2]
                obj2_data = obj1_data.get("photo", {})
                
                # 尝试获取用户名称
                user_info = obj1_data.get("user", {}) or obj2_data.get("user", {})
                if user_info:
                    possible_user_fields = ["userName", "name", "author", "nickname"]
                    for field in possible_user_fields:
                        if field in user_info and user_info[field]:
                            user_name = user_info[field]
                            break
                
                # 直接设置标题为用户名
                if user_name:
                    self.title = user_name
                
                obj3_data = obj2_data.get("manifest", {})
                obj4_data = obj2_data.get("ext_params", {})
                
                # 获取描述
                caption = obj2_data.get("caption", "")
                if caption and len(caption) > 2:
                    self.description = caption
                
                # 获取视频数据
                if len(obj3_data) > 0:
                    self.get_video_data(obj3_data)
                
                # 获取图片数据
                if len(obj4_data) > 0:
                    self.get_image_data(obj4_data)
            
            # 路径 2: 扁平化查找
            if not self.video or not self.image_list or not self.description or not self.title or not user_name:
                self.flat_search_data(self.data_dict, user_name)
            
            # 如果还是没有标题，使用默认值
            if not self.title:
                self.title = "快手用户"
        
        except Exception as e:
            logger.error(f"处理快手数据字典失败: {e}")
            raise e
    
    def flat_search_data(self, data_dict, user_name=""):
        """递归扁平化搜索数据"""
        if isinstance(data_dict, dict):
            # 尝试查找用户名
            for key in ["userName", "authorName", "nickname", "author"]:
                if key in data_dict and isinstance(data_dict[key], str) and len(data_dict[key]) > 1:
                    user_name = data_dict[key]
                    # 直接设置标题为用户名
                    if not self.title:
                        self.title = user_name
                    break
            
            # 查找用户信息对象
            if "user" in data_dict and isinstance(data_dict["user"], dict):
                user_dict = data_dict["user"]
                for key in ["name", "userName", "nickname"]:
                    if key in user_dict and isinstance(user_dict[key], str) and len(user_dict[key]) > 1:
                        user_name = user_dict[key]
                        # 直接设置标题为用户名
                        if not self.title:
                            self.title = user_name
                        break
            
            # 设置描述
            for key in ["caption", "description", "desc", "title"]:
                if not self.description and key in data_dict:
                    desc_text = data_dict[key]
                    if isinstance(desc_text, str) and len(desc_text) > 2:
                        self.description = desc_text
                        break
            
            # 搜索可能的视频
            if not self.video and "manifest" in data_dict:
                self.get_video_data(data_dict["manifest"])
            
            # 搜索可能的图片
            if not self.image_list and "ext_params" in data_dict:
                self.get_image_data(data_dict["ext_params"])
            
            # 继续递归搜索
            for key, value in data_dict.items():
                if isinstance(value, (dict, list)):
                    self.flat_search_data(value, user_name)
        
        elif isinstance(data_dict, list):
            for item in data_dict:
                if isinstance(item, (dict, list)):
                    self.flat_search_data(item, user_name)

    def get_video_data(self, obj3_data):
        """获取视频数据"""
        try:
            adaptationSet = obj3_data.get("adaptationSet", [])
            if adaptationSet and len(adaptationSet) > 0:
                adaptationSet_item = adaptationSet[0]
                representation = adaptationSet_item.get("representation", [])
                if representation and len(representation) > 0:
                    representation_item = representation[0]
                    backupUrl = representation_item.get("backupUrl", [])
                    if backupUrl and len(backupUrl) > 0:
                        self.video = backupUrl[0]
                    # 如果没有 backupUrl，尝试使用 url
                    elif representation_item.get("url"):
                        self.video = representation_item.get("url")
        except Exception as e:
            logger.error(f"获取快手视频数据失败: {e}")
            raise e

    def get_image_data(self, obj4_data):
        """获取图片数据"""
        try:
            atlas = obj4_data.get("atlas", {})
            id_list = atlas.get("list", [])
            if id_list and len(id_list) > 0:
                for item in id_list:
                    if item:
                        image_url = self.image_prefix + item
                        # 确保不是用户头像
                        if "uhead" not in image_url and image_url not in self.image_list:
                            self.image_list.append(image_url)
            
            # 尝试其他可能的图片数据格式
            if not self.image_list:
                # 查找封面图片
                for key in ["coverUrls", "coverUrl", "poster", "thumbnail", "thumbs"]:
                    if key in obj4_data:
                        cover_data = obj4_data[key]
                        if isinstance(cover_data, list) and cover_data:
                            for url in cover_data:
                                if isinstance(url, str) and "uhead" not in url:
                                    self.image_list.append(url)
                                    break
                                elif isinstance(url, dict) and "url" in url:
                                    img_url = url["url"]
                                    if "uhead" not in img_url:
                                        self.image_list.append(img_url)
                                        break
                        elif isinstance(cover_data, str) and "uhead" not in cover_data:
                            self.image_list.append(cover_data)
                            break
                        elif isinstance(cover_data, dict) and "url" in cover_data:
                            img_url = cover_data["url"]
                            if "uhead" not in img_url:
                                self.image_list.append(img_url)
                                break
        except Exception as e:
            logger.error(f"获取快手图片数据失败: {e}")
            raise e

    def to_dict(self):
        """将对象转换为字典，用于 API 返回"""
        try:
            # 如果没有标题，使用默认值
            if not self.title:
                self.title = "快手用户"
                
            result = {
                "url": self.url,
                "final_url": "",
                "title": self.title,
                "description": self.description,
                "image_list": self.image_list,
                "video": self.video,
                "app_type": "kuaishou",
            }
            return Response.success(result, "获取成功")
        except Exception as e:
            logger.error(f"快手转换为字典时出错: {str(e)}", exc_info=True)
            return Response.error("获取失败")
