import logging
import os.path
import shutil
import tempfile
import urllib.request
import uuid
from datetime import datetime
from typing import Any, Optional, Type

import mistune
from docx.shared import RGBColor
from langchain_core.tools import BaseTool
from pptx import presentation, Presentation
from pptx.util import Length, Inches, Pt
from pydantic import BaseModel, Field

from internal.lib.helper import add_attribute


class PPTRenderer(mistune.HTMLRenderer):
    """Markdown转PPT"""
    prs: presentation.Presentation
    font_name: str
    image_folder: str
    content_left: Length
    content_top: Length
    content_width: Length
    line_height: Length

    def __init__(self,
                 prs: presentation.Presentation,
                 image_folder: str):
        super().__init__()

        self.prs = prs
        self.current_slide = None
        self.font_name = "微软雅黑"
        self.image_folder = image_folder
        self.content_left = Inches(1)
        self.content_top = Inches(1.5)
        self.content_width = Inches(8.5)
        self.line_height = Pt(24)

    def heading(self, text: str, level: int, **attrs: Any) -> str:
        if level == 1:
            # 新建布局并添加封面页
            slide = self.prs.slides.add_slide(self.prs.slide_layouts[0])

            title = slide.shapes.title
            sub_title = slide.placeholders[1]
            title.text = text.strip()
            title.text_frame.paragraphs[0].font.name = self.font_name
            sub_title.text = "Ai Agent平台生成"
            self.current_slide = None
        else:
            # 内容页创建带有标题的空白页
            slide_layout = self.prs.slide_layouts[5]
            self.current_slide = self.prs.slides.add_slide(slide_layout)

            # 设置页面标题内容与字体
            title_shape = self.current_slide.shapes.title
            title_shape.text = text.strip()
            title_shape.text_frame.paragraphs[0].font.name = self.font_name

            # 更新当前内容距离顶部的距离
            self.content_top = Inches(1.5)

        return ""

    def paragraph(self, text: str) -> str:
        text = text.strip()

        if self.current_slide and len(text):
            self.check_new_slide()

            text_height = self.estimate_text_height(text, font_size=18)

            text_box = self.current_slide.shapes.add_textbox(
                self.content_left,
                self.content_top,
                self.content_width,
                text_height
            )

            tf = text_box.text_frame
            tf.word_wrap = True

            if tf.paragraphs:
                tf.paragraphs[0]._element.getparent().remove(tf.paragraphs[0]._element)

            p = tf.add_paragraph()
            p.text = text
            p.font.name = self.font_name
            p.font.size = Pt(18)

            self.content_top += text_height

        return ""

    def list(self, text: str, ordered: bool, **attrs: Any) -> str:

        if self.current_slide:
            self.check_new_slide()

            text_box = self.current_slide.shapes.add_textbox(
                self.content_left,
                self.content_top,
                self.content_width,
                Inches(4)
            )

            tf = text_box.text_frame
            tf.word_wrap = True
            tf.clear()

            items = text.strip().split("\n")
            total_height = 0

            for item in items:
                self.check_new_slide()

                p = tf.add_paragraph()
                p.text = item.strip().replace("<li>", "").replace("</li>", "")
                p.level = 0
                p.font.name = self.font_name
                p.font.size = Pt(18)

                item_height = self.estimate_text_height(item, font_size=18)
                total_height += item_height
                self.content_top += item_height

            # 如果文本溢出，自动换页
            if total_height > Inches(4):
                self.check_new_slide()

        return ""

    def image(self, text: str, url: str, title: Optional[str] = None) -> str:
        try:
            if self.current_slide:
                self.check_new_slide()

                if url.startswith("http"):
                    local_path = os.path.join(self.image_folder, os.path.basename(url))
                    urllib.request.urlretrieve(url, local_path)
                else:
                    local_path = url

                pic = self.current_slide.shapes.add_picture(
                    local_path,
                    (self.prs.slide_width - Inches(4)) / 2,
                    self.content_top,
                    width=Inches(4)
                )

                self.content_top += pic.height + Inches(0.5)

        except Exception as error:
            logging.error("PPTRender处理图片异常，${error}s", {"error": error}, exc_info=True)

        return ""

    def block_code(self, code: str, info: Optional[str] = None) -> str:
        if self.current_slide:
            self.check_new_slide()

            text_box = self.current_slide.shapes.add_textbox(
                self.content_left,
                self.content_top,
                self.content_width,
                Inches(2)
            )

            tf = text_box.text_frame
            p = tf.add_paragraph()
            p.text = code.strip()
            p.font.name = "Console"
            p.font.size = Pt(1.4)
            p.font.color.rgb = RGBColor(0x33, 0x55, 0x99)

            self.content_top += self.line_height * (code.count("\n") + 2)

        return ""

    def check_new_slide(self) -> None:
        # 判断页面当前内容的高度是否>=6
        if self.content_top >= Inches(6):
            title = ""
            if self.current_slide:
                title_shape = self.current_slide.shapes.title
                if title_shape and title_shape.text:
                    title = title_shape.text

            # 创建新幻灯片并更新内容高度
            self.current_slide = self.prs.slides.add_slide(self.prs.slide_layouts[5])
            self.content_top = Inches(1.5)

            if title:
                new_title_shape = self.current_slide.shapes.title
                if new_title_shape:
                    new_title_shape.text = title
                    new_title_shape.text_frame.paragraphs[0].font.name = self.font_name

    @classmethod
    def estimate_text_height(cls, text: str, font_size: int = 20, avg_char_per_line: int = 30) -> float:
        # 根据文本内容、文字大小、行平均字数估算文本的高度
        lines = max(1, (len(text) // avg_char_per_line) + text.count("\n"))

        line_height = Pt(font_size * 1.2)

        return (lines + 0.3) * line_height


class MarkdownToPPTXArgsSchema(BaseModel):
    markdown: str = Field(description="需要生成PPT内容的markdown文档字符串")


class MarkdownToPPTXTool(BaseTool):
    name: str = "markdown to pptx"
    description: str = "这是一个可以将markdown文本转换成PPT的工具，传递的参数是markdown对应的文本字符串，返回的参数是PPT的下载地址。"
    args_schema: Type[BaseModel] = MarkdownToPPTXArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                prs = Presentation()

                renderer = PPTRenderer(prs, temp_dir)
                markdown = mistune.Markdown(renderer)
                markdown(kwargs.get("markdown"))

                filename = str(uuid.uuid4()) + ".pptx"
                filepath = os.path.join(temp_dir, filename)
                prs.save(filepath)

                now = datetime.now()
                current_path = os.path.abspath(__file__)
                current_path = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
                current_path = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
                current_path = os.path.dirname(current_path)
                base_file_path = f"{now.year}/{now.month:02d}/{now.day:02d}"
                dest_file_path = f"{current_path}/storage/file_storage/{base_file_path}/{filename}"
                shutil.copy(filepath, dest_file_path)

                return f"{os.getenv('SERVICE_API_PREFIX')}/static/{base_file_path}/{filename}"

        except Exception as error:
            logging.error("markdown to pptx出错：${error}s", {"error": error}, exc_info=True)
            return f"生成PPT失败，错误原因：{str(error)}"


@add_attribute('arg_schema', MarkdownToPPTXArgsSchema)
def markdown_to_pptx(**kwargs) -> BaseTool:
    return MarkdownToPPTXTool()
