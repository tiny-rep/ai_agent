from dataclasses import dataclass

from flask_login import login_required, current_user
from injector import inject

from internal.schema.audio_service import AudioToTextReq, MessageToAudioReq
from internal.service import AudioService
from pkg.reponse import validate_error_json, success_json, compact_generate_response


@inject
@dataclass
class AudioHandler:
    """语音服务"""
    audio_service: AudioService

    @login_required
    def audio_to_text(self):
        req = AudioToTextReq()
        if not req.validate():
            return validate_error_json(req.errors)
        text = self.audio_service.audio_to_text(req.file.data)
        return success_json({"text": text})

    @login_required
    def message_to_audio(self):
        req = MessageToAudioReq()
        if not req.validate():
            return validate_error_json(req.errors)
        resp = self.audio_service.message_to_audio(req.message_id.data, current_user)
        return compact_generate_response(resp)
