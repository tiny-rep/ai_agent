import hashlib
import os.path
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime

from injector import inject
from werkzeug.datastructures.file_storage import FileStorage

from internal.entity.upload_file_entity import ALLOWED_IMAGE_EXTENSION, ALLOWED_DOCUMENT_EXTENSION
from internal.exception import FailException
from internal.model import Account, UploadFile
from .cos_abc_service import CosAbcService
from .upload_file_service import UploadFileService


@inject
@dataclass
class CosLocalService(CosAbcService):
    """对象本地存储"""
    upload_file_service: UploadFileService

    def upload_file(self, file: FileStorage, account: Account, only_image: bool = False) -> UploadFile:
        """上传文件到腾讯云Cos，上传后返回文件信息"""
        account_id = str(account.id)

        # 1. 提取文件扩展名并检测是否可以上传
        filename = file.filename
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        if extension.lower() not in (ALLOWED_IMAGE_EXTENSION + ALLOWED_DOCUMENT_EXTENSION):
            raise FailException(f"该.{extension}扩展的文件不允许上传")
        elif only_image and extension not in ALLOWED_IMAGE_EXTENSION:
            raise FailException(f"该.{extension}扩展的文件不允许上传，请上传正确的图片")

        # 3. 生成一个随机名字
        random_filename = str(uuid.uuid4()) + "." + extension
        now = datetime.now()

        # 4.本地存储
        file_content = file.stream.read()
        current_path = os.path.abspath(__file__)
        current_path = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
        base_file_path = f"{now.year}/{now.month:02d}/{now.day:02d}"
        dir_path = f"{current_path}/storage/file_storage/{base_file_path}"
        upload_filename = f"{base_file_path}/{random_filename}"
        upload_file_path = f"{dir_path}/{random_filename}"

        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        try:
            with open(upload_file_path, "wb") as inline_file:
                inline_file.write(file_content)
        except Exception as e:
            print(e)
            raise FailException("上传文件失败，请稍等重试")

        return self.upload_file_service.create_upload_file(
            account_id=account_id,
            name=filename,
            key=upload_filename,
            size=len(file_content),
            extension=extension,
            mime_type=file.mimetype,
            hash=hashlib.sha3_256(file_content).hexdigest()
        )

    def download_file(self, key: str, target_file_path: str):

        current_path = os.path.abspath(__file__)
        current_path = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
        file_path = f"{current_path}/storage/file_storage/{key}"
        if os.path.exists(file_path):
            shutil.copy(file_path, target_file_path)

    @classmethod
    def get_file_url(cls, key: str) -> str:
        return f"{os.getenv('COS_DOMAIN')}/static/{key}"
