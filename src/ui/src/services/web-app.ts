import { get, post, ssePost } from '@/utils/request'
import type {
  AccessTokenWithExLink,
  GetWebAppConversationsResponse,
  GetWebAppResponse,
  WebAppChatRequest,
  WebAppExLinkRequest
} from '@/models/web-app'
import type { BaseResponse } from '@/models/base'

// 根据标识获取指定 WebApp 基础信息
export const getWebApp = (token: string) => {
  return get<GetWebAppResponse>(`/web-apps/${token}`)
}

// 与指定 WebApp 进行对话
export const webAppChat = (
  token: string,
  req: WebAppChatRequest,
  onData: (event_response: Record<string, any>) => void,
) => {
  return ssePost(`/web-apps/${token}/chat`, { body: req }, onData)
}

// 停止与指定 WebApp 进行对话
export const stopWebAppChat = (token: string, task_id: string) => {
  return post<BaseResponse<any>>(`/web-apps/${token}/chat/${task_id}/stop`)
}

// 获取指定应用的会话列表 
export const getWebAppConversations = (token: string, is_pinned: boolean = false) => {
  return get<GetWebAppConversationsResponse>(`/web-apps/${token}/conversations`, {
    params: { is_pinned },
  })
}

//获取外链对话列表 
export const getExLinkWebAppConversations = (exLinkToken: string, end_user_id: string, is_pinned: boolean = false) => {
  return get<GetWebAppConversationsResponse>(`/web-apps/${exLinkToken}/conversations/${end_user_id}/ex-link`, {
    params: { is_pinned },
  })
}

//根据ex_link_token生成外链可用的access_token
export const generateAccessTokenWithExLink = (exLinkToken: string) => {
  return post<BaseResponse<AccessTokenWithExLink>>(`/web-apps/${exLinkToken}/generate-access-token`)
}

// 与指定 ex_link_web_app 进行对话
export const webAppExLinkChat = (
  exLinktoken: string,
  req: WebAppExLinkRequest,
  onData: (event_response: Record<string, any>) => void,
) => {
  return ssePost(`/web-apps/${exLinktoken}/ex-link/chat`, { body: req }, onData)
}

export const getWebAppWithExLinkToken = (
  exLinkToken: string
) => {
  return get<GetWebAppResponse>(`/web-apps/${exLinkToken}/ex-link`)
}

// 停止与指定 WebApp 进行对话
export const stopWebAppChatWithExLinkToken = (exLinkToken: string, task_id: string) => {
  return post<BaseResponse<any>>(`/web-apps/${exLinkToken}/ex-link/chat/${task_id}/stop`)
}
