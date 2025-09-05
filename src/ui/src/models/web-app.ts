import type { BaseResponse } from '@/models/base'

// 获取WebApp基础信息响应结构
export type GetWebAppResponse = BaseResponse<{
  id: string
  icon: string
  name: string
  description: string
  app_config: {
    opening_statement: string
    opening_questions: string[]
    suggested_after_answer: {
      enable: boolean
    }
  }
}>

// 获取WebApp会话消息列表响应结构
export type GetWebAppConversationsResponse = BaseResponse<
  {
    id: string
    name: string
    summary: string
    created_at: number
  }[]
>

// 与WebApp对话请求结构
export type WebAppChatRequest = {
  conversation_id?: string
  query: string
  image_urls: string[]
}

//WebApp外链应用对话请求结构
export type WebAppExLinkRequest = WebAppChatRequest & {
  end_user_id: string
  app_id: string
  stream: boolean
}

//ExLink webapp 生成外链访问Token
export type  AccessTokenWithExLink = {
  expire_at: number
  access_token: string
}