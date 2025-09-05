import os.path
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import requests
from injector import inject
from langchain_community.document_loaders import UnstructuredExcelLoader, UnstructuredMarkdownLoader, \
    UnstructuredPDFLoader, UnstructuredHTMLLoader, UnstructuredCSVLoader, UnstructuredPowerPointLoader, \
    UnstructuredXMLLoader, UnstructuredFileLoader, TextLoader
from langchain_core.documents import Document as LCDocument

from internal.model import UploadFile
from internal.service import CosLocalService


@inject
@dataclass
class FileExtractor:
    cos_service: CosLocalService

    def load(self,
             upload_file: UploadFile,
             return_text: bool = False,
             is_unstructured: bool = True) -> Union[list[LCDocument], str]:
        """加载传入的upload_file记录，返回langchain文档列表"""
        # 1. 创建临时文件夹
        with tempfile.TemporaryDirectory() as temp_dir:
            # 2. 构建一个临时文件路径
            file_path = os.path.join(temp_dir, os.path.basename(upload_file.key))
            # 3. 将对象下载到本地
            self.cos_service.download_file(upload_file.key, file_path)
            # 4. 从指定路径加载文件
            return self.load_from_file(file_path, return_text, is_unstructured)

    @classmethod
    def load_from_url(cls, url: str, return_text: bool = False) -> Union[list[LCDocument], str]:
        """从传入的URL中去加载数据，并返回langchain文档"列表"""
        resp = requests.get(url)

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, os.path.basename(url))
            with open(file_path, "wb") as file:
                file.write(resp.content)
        return cls.load_from_file(file_path, return_text)

    @classmethod
    def load_from_file(cls, file_path: str,
                       return_text: bool = False,
                       is_unstructured: bool = True):
        """从文件中加载数据，返回langchain文档列表"""
        delimiter = "\n\n"
        file_extension = Path(file_path).suffix.lower()

        if file_extension in [".xlsx", "xls"]:
            loader = UnstructuredExcelLoader(file_path)
        elif file_extension in [".md", ".markdown"]:
            loader = UnstructuredMarkdownLoader(file_path)
        elif file_extension == ".pdf":
            loader = UnstructuredPDFLoader(file_path)
        elif file_extension in [".html", ".htm"]:
            loader = UnstructuredHTMLLoader(file_path)
        elif file_extension == ".csv":
            loader = UnstructuredCSVLoader(file_path)
        elif file_extension in [".ppt", ".pptx"]:
            loader = UnstructuredPowerPointLoader(file_path)
        elif file_extension == ".xml":
            loader = UnstructuredXMLLoader(file_path)
        else:
            loader = UnstructuredFileLoader(file_path) if is_unstructured else TextLoader(file_path)

        return delimiter.join([doc.page_content for doc in loader.load()]) if return_text else loader.load()
