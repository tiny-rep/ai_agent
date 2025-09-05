import { ref } from 'vue'
import { generateAccessTokenWithExLink, getExLinkWebAppConversations, getWebApp, getWebAppConversations, 
  getWebAppWithExLinkToken, stopWebAppChat, webAppChat, webAppExLinkChat, stopWebAppChatWithExLinkToken } from '@/services/web-app'
import type { AccessTokenWithExLink, WebAppChatRequest, WebAppExLinkRequest } from '@/models/web-app'

export const useGetWebApp = () => {
  // 1.定义自定义hooks所需数据
  const loading = ref(false)
  const web_app = ref<Record<string, any>>({})

  // 2.定义加载数据处理器
  const loadWebApp = async (token: string, isExLink: boolean) => {
    try {
      loading.value = true
      const resp = await (isExLink ? getWebAppWithExLinkToken(token) : getWebApp(token))
      web_app.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, web_app, loadWebApp }
}

export const useWebAppChat = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义WebApp对话处理器
  const handleWebAppChat = async (
    token: string,
    req: WebAppChatRequest,
    onData: (event_response: Record<string, any>) => void,
  ) => {
    try {
      loading.value = true
      await webAppChat(token, req, onData)
    } finally {
      loading.value = false
    }
  }

  //外链对话处理器
  const handleExLinkWebAppChat = async (
    token: string,
    req: WebAppExLinkRequest,
    onData: (event_response: Record<string, any>) => void,
  ) => {
    try {
      loading.value = true
      await webAppExLinkChat(token, req, onData)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleWebAppChat, handleExLinkWebAppChat }
}

export const useStopWebAppChat = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义停止WebApp对话处理器
  const handleStopWebAppChat = async (token: string, task_id: string, isExLink: boolean) => {
    try {
      loading.value = true
      await (isExLink ? stopWebAppChatWithExLinkToken(token, task_id) : stopWebAppChat(token, task_id))
    } finally {
      loading.value = false
    }
  }

  return { loading, handleStopWebAppChat }
}

export const useGetAppConversations = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const pinned_conversations = ref<Record<string, any>[]>([])
  const unpinned_conversations = ref<Record<string, any>[]>([])

  // 2.定义加载数据处理器
  const loadWebAppConversations = async (token: string, end_user_id: string, isExLink: boolean) => {
    try {
      loading.value = true
      const [pinned_resp, unpinned_resp] = await ( isExLink ?  
        Promise.all([
          getExLinkWebAppConversations(token, end_user_id, true),
          getExLinkWebAppConversations(token, end_user_id, false)
        ])
        : 
        Promise.all([
          getWebAppConversations(token, true),
          getWebAppConversations(token, false),
        ]))

      pinned_conversations.value = pinned_resp.data
      unpinned_conversations.value = unpinned_resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, pinned_conversations, unpinned_conversations, loadWebAppConversations }
}

export const useGenerateAccessTokenWithExlink = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const accessTokenWithExLink = ref<AccessTokenWithExLink>()

  // 2.定义停止WebApp对话处理器
  const handleExlinkGenerateAccessToken = async (ex_link_token: string) => {
    try {
      loading.value = true
      const resp = await generateAccessTokenWithExLink(ex_link_token)
      accessTokenWithExLink.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, accessTokenWithExLink, handleExlinkGenerateAccessToken }
}
