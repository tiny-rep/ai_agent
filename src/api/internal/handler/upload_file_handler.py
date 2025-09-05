from dataclasses import dataclass

from flask_login import login_required, current_user
from injector import inject

from internal.schema.upload_file_schema import UploadFileReq, UploadFileResp, UploadImageReq
from internal.service import CosLocalService
from pkg.reponse import validate_error_json, success_json


@inject
@dataclass
class UploadFileHandler:
    cos_service: CosLocalService

    @login_required
    def upload_file(self):
        """上传文件处理"""
        req = UploadFileReq()
        if not req.validate():
            return validate_error_json(req.errors)

        upload_file = self.cos_service.upload_file(req.file.data, current_user)

        resp = UploadFileResp()
        return success_json(resp.dump(upload_file))

    def upload_image(self):
        """上传文件"""
        req = UploadImageReq()
        if not req.validate():
            return validate_error_json(req.errors)

        upload_file = self.cos_service.upload_file(req.file.data, current_user, True)

        image_url = self.cos_service.get_file_url(upload_file.key)

        return success_json({
            "image_url": image_url
        })
