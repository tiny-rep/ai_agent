import { get, post } from '@/utils/request'
import type {
  GetConversationMessagesWithPageRequest,
  GetConversationMessagesWithPageResponse,
} from '@/models/conversation'
import type { BaseResponse } from '@/models/base'

// 获取指定会话的消息列表
export const getConversationMessagesWithExlink = (
  conversation_id: string,
  end_user_id: string,
  req: GetConversationMessagesWithPageRequest,
) => {
  return get<GetConversationMessagesWithPageResponse>(
    `/conversations/${conversation_id}/messages/ex-link/${end_user_id}`,
    { params: req },
  )
}

// 删除特定的会话
export const deleteConversationWithExlink = (conversation_id: string, end_user_id: string) => {
  return post<BaseResponse<any>>(`/conversations/${conversation_id}/delete/ex-link/${end_user_id}`)
}

// 删除特定会话下的指定消息
export const deleteMessageWithExlink = (conversation_id: string, end_user_id: string, message_id: string) => {
  return post<BaseResponse<any>>(`/conversations/${conversation_id}/messages/${message_id}/ex-link/${end_user_id}`)
}

// 获取指定会话的名称
export const getConversationNameWithExlink = (conversation_id: string, end_user_id: string) => {
  return get<BaseResponse<{ name: string }>>(`/conversations/${conversation_id}/name/ex-link/${end_user_id}`)
}

// 修改指定会话的名称
export const updateConversationNameWithExlink = (conversation_id: string, end_user_id: string, name: string) => {
  return post<BaseResponse<any>>(`/conversations/${conversation_id}/name/ex-link/${end_user_id}`, { body: { name } })
}

// 置顶或取消置顶某个会话
export const updateConversationIsPinnedWithExlink = (conversation_id: string, end_user_id: string, is_pinned: boolean) => {
  return post<BaseResponse<any>>(`/conversations/${conversation_id}/is-pinned/ex-link/${end_user_id}`, {
    body: { is_pinned },
  })
}

//初始化空会话
export const initNewConversation = (conversation_id: string, end_user_id: string, app_id: string) => {
  return get<BaseResponse<any>>(`/openapi/${end_user_id}/app/${app_id}/init-conversation/${conversation_id}`)
}

