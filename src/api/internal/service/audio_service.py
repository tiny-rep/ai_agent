import base64
import json
import logging
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Generator, Union
from uuid import UUID

from injector import inject
from openai import OpenAI
from werkzeug.datastructures import FileStorage

from internal.model import Account, Message, App, AppConfig, AppConfigVersion
from pkg.sqlalchemy import SQLAlchemy
from .app_service import AppService
from .base_service import BaseService
from ..entity.app_entity import AppStatus
from ..entity.conversation_entity import InvokeFrom
from ..exception import NotFoundException, FailException


@inject
@dataclass
class AudioService(BaseService):
    """语音服务"""
    db: SQLAlchemy
    app_service: AppService

    def audio_to_text(self, audio: FileStorage) -> str:
        file_content = audio.stream.read()
        audio_file = BytesIO(file_content)
        audio_file.name = "recording.wav"

        client = self._get_openapi_client()
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )

        return transcription.text

    def message_to_audio(self, message_id: UUID, account: Account) -> Generator:
        """消息转语音"""
        message: Message = self.get(Message, message_id)
        if not message or message.is_deleted or message.answer.strip() == "" \
                or message.created_by != account.id:
            raise NotFoundException("该消息不存在，请核实后重试")

        # 2. 校验消息归属的会话状态是否正常
        conversation = message.conversation
        if conversation is None or conversation.is_deleted or conversation.created_by != account.id:
            raise NotFoundException("该消息不存在，请核实后重试")

        # 3. 定义文本转语音启动配置，默认开启+echo音色
        enable = True
        voice = "echo"

        # 4. 根据会话信息获取会话归属的应用
        if message.invoke_from in [InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER]:
            app: App = self.get(App, conversation.app_id)
            if not app:
                raise NotFoundException("该消息会话归属应用不存在或校验失败，请核实后重试")
            if message.invoke_from == InvokeFrom.DEBUGGER is True and app.account_id != account.id:
                raise NotFoundException("该消息会话归属应用不存在或校验失败，请核实后重试")
            if message.invoke_from == InvokeFrom.WEB_APP is False and app.status != AppStatus.PUBLISHED:
                raise NotFoundException("该消息会话归属应用不存在或校验失败，请核实后重试")

            app_config: Union[AppConfig, AppConfigVersion] = (
                app.draft_app_config
                if message.invoke_from == InvokeFrom.DEBUGGER
                else app.app_config
            )
            text_to_speech = app_config.text_to_speech
            enable = text_to_speech.get("enable", False)
            voice = text_to_speech.get("voice", "echo")
        elif message.invoke_from == InvokeFrom.SERVICE_API:
            raise NotFoundException("开放API消息不支持文本转语音服务")

        # 6. 调用tts服务将消息answer转成流式事件输出语音
        try:
            client = self._get_openapi_client()
            resp = client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice=voice,
                response_format="mp3",
                input=message.answer.strip()
            )
        except Exception as error:
            logging.error(f"文本转语音失败：%{error}s", {"error": error}, exc_info=True)
            raise FailException("文本转语音失败，请稍后重试")

        def tts() -> Generator:
            """内部函数 ，流式输出"""
            common_data = {
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "audio": ""
            }
            for chunk in resp.__enter__().iter_bytes(1024):
                data = {**common_data, "audio": base64.b64encode(chunk).decode("utf-8")}
                yield f"event: tts_message\ndata:{json.dumps(data)}\n\n"
            yield f"event:tts_end\bdata:{json.dumps(common_data)}\n\n"

        return tts()

    @classmethod
    def _get_openapi_client(cls) -> OpenAI:
        return OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_API_BASE")
        )
