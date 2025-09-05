from abc import ABC, abstractmethod

from werkzeug.datastructures.file_storage import FileStorage

from internal.model import Account, UploadFile


class CosAbcService(ABC):
    """对象存储抽象类"""

    @abstractmethod
    def upload_file(self, file: FileStorage, account: Account, only_image: bool = False) -> UploadFile:
        pass

    @abstractmethod
    def download_file(self, key: str, target_file_path: str):
        pass
