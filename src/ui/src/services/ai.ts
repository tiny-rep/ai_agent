import {post, ssePost} from '@/utils/request'
import {type BaseResponse} from '@/models/base'

export const optimizePrompt = (
  prompt: string,
  onData: (event_response:Record<string, any>) => void
) => {
  return ssePost(`/ai/optimize-prompt`, {body: {prompt}}, onData)
}

export const generateSuggestedQuesions = (message_id: string) => {
  return post<BaseResponse<string[]>>(`/ai/suggested-questions`, {body:{message_id}})
}

export const generateSuggestedQuesionsWithExLink = (end_user_id: string, message_id: string) => {
  return post<BaseResponse<string[]>>(`/ai/${end_user_id}/suggested-questions/ex-link`, {body:{message_id}})
}