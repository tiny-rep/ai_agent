import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime

from injector import inject
from qcloud_cos import CosS3Client, CosConfig
from werkzeug.datastructures.file_storage import FileStorage

from internal.entity.upload_file_entity import ALLOWED_IMAGE_EXTENSION, ALLOWED_DOCUMENT_EXTENSION
from internal.exception import FailException
from internal.model import UploadFile, Account
from .cos_abc_service import CosAbcService
from .upload_file_service import UploadFileService


@inject
@dataclass
class CosService(CosAbcService):
    """腾讯去COS对象存储服务"""
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

        # 2.获取客户端+桶名字
        client = self._get_client()
        bucket = self._get_bucket()

        # 3. 生成一个随机名字
        random_filename = str(uuid.uuid4()) + "." + extension
        now = datetime.now()
        upload_filename = f"{now.year}/{now.month:02d}/{now.day:02d}/{random_filename}"

        # 4.流式读取上传的数据并将其上传到COS中
        file_content = file.stream.read()

        try:
            client.put_object(bucket, file_content, upload_filename)
        except Exception as e:
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
        """下载cos文件到本地指定路径"""
        client = self._get_client()
        bucket = self._get_bucket()

        client.download_file(bucket, key, target_file_path)

    @classmethod
    def get_file_url(cls, key: str) -> str:
        """获取文件访问路径"""
        cos_domain = os.getenv("COS_DOMAIN")
        if not cos_domain:
            bucket = os.getenv("COS_BUCKET")
            scheme = os.getenv("COS_SCHEME")
            region = os.getenv("COS_REGION")
            cos_domain = f"{scheme}://{bucket}.cos.{region}.myqcloud.com"
        return f"{cos_domain}/{key}"

    @classmethod
    def _get_client(cls) -> CosS3Client:
        conf = CosConfig(
            Region=os.getenv("COS_REGION"),
            SecretId=os.getenv("COS_SECRET_ID"),
            SecretKey=os.getenv("COS_SECRET_KEY"),
            Token=None,
            Scheme=os.getenv("COS_SCHEME")
        )
        return CosS3Client(conf)

    @classmethod
    def _get_bucket(cls) -> str:
        return os.getenv("COS_BUCKET")
