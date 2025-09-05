import {
  type GetDebugConversationMessagesWithPageResponse,
  type UpdateDraftAppConfigRequest,
  type GetAppsWithPageResponse,
  type UpdateAppRequest,
  type CreateAppRequest
} from '@/models/app'
import { cancelPublish,
  debugChat,
  deleteDebugConversation,
  fallbackHistoryToDraft,
  getApp,
  getDebugConversationMessagesWithPage,
  getDebugConversationSummary,
  getDraftAppConfig,
  getPublishHistoriesWithPage,
  publish,
  stopDebugChat,
  updateDebugConversationSummary,
  UpdateDraftAppConfig,
  getAppsWithPage,
  updateApp,
  deleteApp,
  copyApp,
  createApp,
  regenerateWebAppToken,
  getPublishedConfig, 
  generateWebAppExlinkToken,
  cancelWebAppExlinkToken} from '@/services/app'
import { Message, Modal } from '@arco-design/web-vue'
import { ref } from 'vue'
import { useRouter } from 'vue-router'


//获取应用
export const useGetApp = () => {
  const loading = ref(false)
  const app = ref<Record<string,any>>({})

  const loadApp = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await getApp(app_id)
      const data = resp.data

      app.value = data
    } finally {
      loading.value = false
    }
  }

  return {loading, app, loadApp}
}


export const useGetAppsWithPage = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const apps = ref<GetAppsWithPageResponse['data']['list']>([])
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref({ ...defaultPaginator })

  // 2.定义加载数据函数
  const loadApps = async (init: boolean = false, search_word: string = '') => {
    // 2.1 判断是否是初始化，如果是的话则先初始化分页器
    if (init) {
      paginator.value = defaultPaginator
    } else if (paginator.value.current_page > paginator.value.total_page) {
      return
    }

    // 2.2 加载数据并更新
    try {
      // 2.3 将loading值改为true并调用api接口获取数据
      loading.value = true
      const resp = await getAppsWithPage({
        current_page: paginator.value.current_page,
        page_size: paginator.value.page_size,
        search_word: search_word,
      })
      const data = resp.data

      // 2.4 更新分页器
      paginator.value = data.paginator

      // 2.5 判断是否存在更多数据
      if (paginator.value.current_page <= paginator.value.total_page) {
        paginator.value.current_page += 1
      }

      // 2.6 追加或者是覆盖数据
      if (init) {
        apps.value = data.list
      } else {
        apps.value.push(...data.list)
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, apps, paginator, loadApps }
}

export const useCreateApp = () => {
  // 1.定义hooks所需数据
  const router = useRouter()
  const loading = ref(false)

  // 2.定义新增应用处理器
  const handleCreateApp = async (req: CreateAppRequest) => {
    try {
      loading.value = true
      const resp = await createApp(req)
      Message.success('新增Agent应用成功')
      await router.push({
        name: 'space-apps-detail',
        params: { app_id: resp.data.id },
      })
    } finally {
      loading.value = false
    }
  }

  return { loading, handleCreateApp }
}

export const useUpdateApp = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新数据处理器
  const handleUpdateApp = async (app_id: string, req: UpdateAppRequest) => {
    try {
      loading.value = true
      const resp = await updateApp(app_id, req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateApp }
}

export const useCopyApp = () => {
  // 1.定义hooks所需数据
  const router = useRouter()
  const loading = ref(false)

  // 2.定义拷贝应用副本处理器
  const handleCopyApp = async (app_id: string) => {
    try {
      // 2.1 修改loading并发起请求
      loading.value = true
      const resp = await copyApp(app_id)

      // 2.2 成功修改则进行提示并跳转页面
      Message.success('创建应用副本成功')
      await router.push({ name: 'space-apps-detail', params: { app_id: resp.data.id } })
    } finally {
      loading.value = false
    }
  }

  return { loading, handleCopyApp }
}

export const useDeleteApp = () => {
  const handleDeleteApp = async (app_id: string, callback?: () => void) => {
    Modal.warning({
      title: '要删除该应用吗?',
      content:
        '删除应用后，发布的WebApp、开放API以及关联的社交媒体平台均无法使用该Agent应用，如果需要暂停应用，可使用取消发布功能。',
      hideCancel: false,
      onOk: async () => {
        try {
          // 1.点击确定后向API接口发起请求
          const resp = await deleteApp(app_id)
          Message.success(resp.message)
        } finally {
          // 2.调用callback函数指定回调功能
          callback && callback()
        }
      },
    })
  }

  return { handleDeleteApp }
}

// 发布应用
export const usePublish = () => {
  const loading = ref(false)

  const handlePublish = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await publish(app_id)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }
  return {loading, handlePublish}
}

//取消发布
export const useCancelPublish = () => {
  const loading = ref(false)

  const handleCancelPublish = async (app_id: string, callback?: () => void) => {
    Modal.warning({
      title: "要取消发布该Agent应用吗？",
      content: "取消发布后，WebApp以及发布的社交平台均无法使用该Agent，如需要更新WebApp地址，请使用地址重新生成功能",
      hideCancel: false,
      onOk: async () => {
        try {
          loading.value = true
          const resp = await cancelPublish(app_id)
          Message.success(resp.message)
        } finally {
          loading.value = false
          callback && callback()
        }
      }
    })
  }

  return {loading, handleCancelPublish}
}

// 获取发布历史记录
export const useGetPublishHistoriesWithPage = () => {
  const loading = ref(false)
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0
  }

  const publishHistories = ref<Array<Record<string, any>>>([])
  const paginator = ref({...defaultPaginator})

  const loadPublishHistories =async (app_id:string, init: boolean = false) => {
    try {
      if(init) {
        paginator.value = defaultPaginator
      } else if (paginator.value.current_page > paginator.value.total_page) {
        return
      }
      loading.value = true

      const resp = await getPublishHistoriesWithPage(app_id, {
        current_page: paginator.value.current_page,
        page_size: paginator.value.page_size
      })
      const data = resp.data

      paginator.value = data.paginator

      if (paginator.value.current_page <= paginator.value.total_page) {
        paginator.value.current_page += 1
      }

      if (init) {
        publishHistories.value = data.list
      } else {
        publishHistories.value.push(...data.list)
      }
    } finally {
      loading.value = false
    }
  }

  return {loading, publishHistories, paginator, loadPublishHistories}
}

//回退历史版本到草稿
export const useFallbackHistoryToDraft = () => {
  const loading = ref(false)

  const handleFallbackHistoryToDraft = async (
    app_id: string,
    app_config_version_id: string,
    callback?: () => void
  ) => {
    try {
      loading.value = true
      const resp = await fallbackHistoryToDraft(app_id, app_config_version_id)
      Message.success(resp.message)
    } finally {
      loading.value = false
      callback && callback()
    }
  }
  return {loading, handleFallbackHistoryToDraft}
}

//获取草稿配置
export const useGetDraftAppConfig = () => {
  const loading = ref(false)
  const draftAppConfigForm = ref<Record<string, any>>({})

  const loadDraftAppConfig = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await getDraftAppConfig(app_id)
      const data = resp.data

     draftAppConfigForm.value = {
        dialog_round: data.dialog_round,
        model_config: data.model_config,
        preset_prompt: data.preset_prompt,
        long_term_memory: data.long_term_memory,
        opening_statement: data.opening_statement,
        opening_questions: data.opening_questions,
        suggested_after_answer: data.suggested_after_answer,
        review_config: data.review_config,
        datasets: data.datasets,
        mcps: data.mcps,
        retrieval_config: data.retrieval_config,
        tools: data.tools,
        workflows: data.workflows,
        speech_to_text: data.speech_to_text,
        text_to_speech: data.text_to_speech,
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, draftAppConfigForm, loadDraftAppConfig }
}

// 更新草稿配置
export const useUpdateDraftAppConfig = () =>{
  const loading = ref(false)

  const handleUpdateDraftAppConfig = async (
    app_id: string,
    draft_app_config: UpdateDraftAppConfigRequest
  ) => {
    try {
      loading.value = true
      const resp = await UpdateDraftAppConfig(app_id, draft_app_config)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return {loading, handleUpdateDraftAppConfig}
}

// 获取调试对话长忘记
export const  useGetDebugConversationSummary = () => {
  const loading = ref(false)
  const debug_conversation_summary = ref('')

  const loadDebugConversationSummary = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await getDebugConversationSummary(app_id)
      const data = resp.data

      debug_conversation_summary.value = data.summary
    } finally {
      loading.value = false
    }
  }
  return {loading, debug_conversation_summary, loadDebugConversationSummary}
}

// 更新调试对话长期记忆
export const useUpdateDebugConversationSummary = () => {
  const loading = ref(false)

  const handleUpdateDebugConversationSummary = async (app_id: string, summary: string) => {
    try {
      loading.value = true
      const resp = await updateDebugConversationSummary(app_id, summary)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return {loading, handleUpdateDebugConversationSummary}
}

//清空调试会话信息
export const useDeleteDebugConversation = () => {
  const loading = ref(false)

  const handleDeleteDebugConversation = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await deleteDebugConversation(app_id)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }
  return {loading, handleDeleteDebugConversation}
}

// 获取调试会话记录
export const useGetDebugConversationMessagesWithPage = () => {
  const loading = ref(false)
  const messages = ref<GetDebugConversationMessagesWithPageResponse['data']['list']>([])
  const created_at = ref(0)
  const defaultPaginator = {
    current_page: 1,
    page_size: 5,
    total_page: 0,
    total_record: 0
  }
  const paginator = ref({...defaultPaginator})

  const loadDebugConversationMessages = async (app_id: string, init: boolean = false) => {
    if (init) {
      paginator.value = {...defaultPaginator}
      created_at.value = 0 
    } else if (paginator.value.current_page > paginator.value.total_page) {
      return
    }

    try {
      loading.value = true
      const resp = await getDebugConversationMessagesWithPage(app_id, {
        current_page: paginator.value.current_page,
        page_size: paginator.value.page_size,
        created_at: created_at.value
      })
      const data = resp.data

      paginator.value = data.paginator

      if (paginator.value.current_page <= paginator.value.total_page) {
        paginator.value.current_page += 1
      }

      if (init) {
        messages.value = data.list
      } else {
        messages.value.push(...data.list)
        created_at.value = data.list[0]?.created_at ?? 0
      }
    } finally {
      loading.value = false
    }
  }
  return {loading, messages, paginator, loadDebugConversationMessages}
}

// 调试对话
export const useDebugChat = () => {
  const loading = ref(false)

  const handleDebugChat = async (
    app_id: string,
    query: string,
    image_urls: string[],
    onData: (event_response: Record<string, any>) => void
  ) => {
    try{
      loading.value = true
      await debugChat(app_id, query, image_urls, onData)

    } finally{
      loading.value = false
    }
  }

  return {loading, handleDebugChat}
}

//停止调试对话
export const useStopDebugChat = () => {
  const loading = ref(false)

  const handleStopDebugChat = async (app_id: string, task_id: string) => {
    try {
      loading.value = true
      await stopDebugChat(app_id, task_id)
    } finally {
      loading.value = false
    }
  }
  return {loading, handleStopDebugChat}
}

export const useGetPublishedConfig = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const published_config = ref<Record<string, any>>({})

  // 2.定义加载数据函数
  const loadPublishedConfig = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await getPublishedConfig(app_id)
      published_config.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, published_config, loadPublishedConfig }
}

export const useRegenerateWebAppToken = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const token = ref<string>('')

  // 2.定义重生成WebAppToken函数
  const handleRegenerateWebAppToken = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await regenerateWebAppToken(app_id)
      Message.success('重新生成WebApp访问链接成功')
      token.value = resp.data.token
    } finally {
      loading.value = false
    }
  }

  return { loading, token, handleRegenerateWebAppToken }
}

export const useGenerateWebAppExlinkToken = () => {
  const loading = ref(false)
  const exLinkToken = ref<string>('')

  const handleGenerateWebAppExlinkToken = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await generateWebAppExlinkToken(app_id)
      Message.success("外链WebApp访问链接生成成功")
      exLinkToken.value = resp.data?.web_app?.token
    } finally {
      loading.value = false
    }
  }

  return { loading, exLinkToken, handleGenerateWebAppExlinkToken }
}

export const useCancelWebAppExlinkToken = () => {
  const loading = ref(false)

  const handleCancelWebAppExlinkToken = async (app_id: string) => {
    try {
      loading.value = true
      const resp = await cancelWebAppExlinkToken(app_id)
      Message.success("取消外链WebApp链接成功")
    } finally {
      loading.value = false
    }
  }

  return { loading, handleCancelWebAppExlinkToken }
}
