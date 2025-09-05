<script setup lang="ts">

//@ts-ignore
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'

import { nextTick, onMounted, onUnmounted, type PropType, ref } from 'vue'
import { useRoute } from 'vue-router'
import AudioRecorder from 'js-audio-recorder'

import {
  useDebugChat,
  useDeleteDebugConversation,
  useGetDebugConversationMessagesWithPage,
  useStopDebugChat
} from '@/hooks/use-app'

import { useGenerateSuggestedQuesions } from '@/hooks/use-ai'
import { useAccountStore } from '@/stores/account'
import { Message } from '@arco-design/web-vue'
import { QueueEvent } from '@/config'
import AiMessage from '@/components/AiMessage.vue'
import HumanMessage from '@/components/HumanMessage.vue'
import { uploadImage } from '@/services/upload-file'
import { useAudioToText, useAudioPlayer } from '@/hooks/use-audio'

//1. 定义变量
const route = useRoute()
const props = defineProps({
  app: {type: Object, default: {}, required: true},
  suggested_after_answer: {
    type: Object as PropType<{enable: Boolean}>,
    default: {enable: true},
    required: true
  },
  opening_statement: {type: String, default: '', required: true},
  opening_questions: {type: Array as PropType<string[]>, default: [], required: true},
  text_to_speech: {
    type: Object, default: () => {
      return {
        enable: false,
        auto_play: false,
        voice: 'echo',
      }
    },
    required: false,
  }
})
const query = ref('')

//图片相关
const image_urls = ref<string[]>([])
const fileInput = ref<any>(null)
const uploadFileLoading= ref(false)

//音频
const isRecording = ref(false)  // 是否正在录音
const audioBlob = ref<any>(null)  // 录音后音频的blob
let recorder: any = null  // RecordRTC实例

const message_id = ref('')
const task_id = ref('')
const scroller = ref<any>(null)
const scrollHeight = ref(0)
const accountStore = useAccountStore()
const { loading: deleteDebugConversationLoading, handleDeleteDebugConversation } = useDeleteDebugConversation()
const {
  loading: getDebugConversationMessagesWithPageLoading,
  messages,
  loadDebugConversationMessages
} = useGetDebugConversationMessagesWithPage()
const { loading: debugChatLoading, handleDebugChat } = useDebugChat()
const { loading: stopDebugChatLoading, handleStopDebugChat } = useStopDebugChat()
const { suggested_questions, handleGenerateSUggestedQuesions } = useGenerateSuggestedQuesions()
const {
  loading: audioToTextLoading,
  text,
  handleAudioToText,
} = useAudioToText()
const { startAudioStream, stopAudioStream } = useAudioPlayer()

//2. 定义保存滚动高度函数
const saveScrollHeight = () => {
  scrollHeight.value = scroller.value.$el.scrollHeight
}

//3. 定义还原滚动高度函数
const restoreScrollPosition = () => {
  scroller.value.$el.scrollTop = scroller.value.$el.scrollHeight - scrollHeight.value
}

// 4. 定义滚动函数
const handleScroll = async (event: UIEvent) => {
  const { scrollTop } = event.target as HTMLElement
  if (scrollTop <= 0 && !getDebugConversationMessagesWithPageLoading.value) {
    saveScrollHeight()
    await loadDebugConversationMessages(String(route.params?.app_id), false)
    restoreScrollPosition()
  }
}

//5. 定义输入框提交函数
const handleSubmit = async () => {
  if (query.value.trim() === '') {
    Message.warning("用户提问不能为空")
    return
  }
  if (debugChatLoading.value) {
    Message.warning('上一次提问还未结束，请稍等')
    return
  }

  suggested_questions.value = []
  message_id.value = ''
  task_id.value = ''
  stopAudioStream()

  //5.4 添加基础人类消息
  messages.value.unshift({
    id: '',
    conversation_id: '',
    query: query.value,
    image_urls: image_urls.value,
    answer: '',
    total_token_count: 0,
    latency: 0,
    agent_thoughts: [],
    created_at: 0
  })

  //5.5 初始化推理过程数据，并清空输入数据
  let position = 0
  const humanQuery = query.value
  const humanImageUrls = image_urls.value
  query.value = ''
  image_urls.value = []


  //5.6 调用hooks请求
  await handleDebugChat(props.app?.id, humanQuery, humanImageUrls, (event_response) => {
    //5.7 提取流式事件响应数据以及事件名称
    const event = event_response?.event
    const data = event_response?.data
    const event_id = data?.id

    let agent_thoughts = messages.value[0].agent_thoughts

    //5.8 初始化数据检测与赋值
    if (message_id.value === '' && data?.message_id) {
      task_id.value = data?.task_id
      message_id.value = data?.message_id
      messages.value[0].id = data?.message_id
      messages.value[0].conversation_id = data?.conversation_id
    }

    //5.9 循环处理得到事件，记录聊ping之外的事件类型
    if (event !== QueueEvent.ping) {
      if (event === QueueEvent.agentMessage || event === QueueEvent.agentThink) {
        const agent_thought_idx = agent_thoughts.findIndex(item => item?.id === event_id)

        //5.12 数据不存在则添加
        if (agent_thought_idx === -1) {
          position += 1
          agent_thoughts.push({
            id: event_id,
            position: position,
            event: data?.event,
            thought: data?.thought,
            observation: data?.observation,
            tool: data?.tool,
            tool_input: data?.tool_input,
            latency: data?.latency,
            created_at: 0
          })
        } else {
          // 5.13 存在数据则叠加
          agent_thoughts[agent_thought_idx] = {
            ...agent_thoughts[agent_thought_idx],
            thought: agent_thoughts[agent_thought_idx]?.thought + data?.thought,
            latency: data?.latency
          }
        }

        // 5.14 更新、添加answer答案
        if (event == QueueEvent.agentMessage) {
          messages.value[0].answer += data?.thought
        }
        messages.value[0].latency = data?.latency
        messages.value[0].total_token_count = data?.total_token_count
      } else if (event === QueueEvent.error) {
        messages.value[0].answer = data?.observation
      } else if (event === QueueEvent.timeout) {
        messages.value[0].answer = '当前Agent执行已超时，无法得到答案，请重试'
      } else {
        position += 1
        agent_thoughts.push({
            id: event_id,
            position: position,
            event: data?.event,
            thought: data?.thought,
            observation: data?.observation,
            tool: data?.tool,
            tool_input: data?.tool_input,
            latency: data?.latency,
            created_at: 0
          })
      }

      //5.16 更新agent_thoughts
      messages.value[0].agent_thoughts = agent_thoughts
      scroller.value.scrollToBottom()
    }
  })

  //5.7 判断是否开启建议问题生成，如果开启就请求API
  if (props.suggested_after_answer.enable && message_id.value) {
    await handleGenerateSUggestedQuesions(message_id.value)
    setTimeout(() => {
      scroller.value && scroller.value.scrollToBottom()
    }, 100);
  }

  // 5.8 检测是否自动播放，如果是则调用hooks播放音频
  if (props.text_to_speech.enable && props.text_to_speech.auto_play && message_id.value) {
    startAudioStream(message_id.value)
  }
 
}

// 6. 定义停止调试会话函数
const handleStop = async () =>{
  if (task_id.value === '' || !debugChatLoading.value) return

  await handleStopDebugChat(props.app?.id, task_id.value)
}

//7. 定义问题提交函数
const handleSubmitQuestion = async (question: string) => {
  query.value = question

  await handleSubmit()
}

//8. 文件上传触发器
const triggerFileInput = () => {
  if (image_urls.value.length > 5) {
    Message.error("对话上传图片数量不能超过5张")
    return
  }
  fileInput.value.click()
}

//9. 文件变化监听器
const handleFileChange = async (event: Event) => {
  if (uploadFileLoading.value) return

  const input = event.target as HTMLInputElement
  const selectedFile = input.files?.[0]
  if (selectedFile) {
    try {
      uploadFileLoading.value = true
      const resp = await uploadImage(selectedFile)
      image_urls.value.push(resp.data.image_url)
      Message.success("图片上传成功")
    } finally {
      uploadFileLoading.value = false
    }
  }
}

// 10.开始录音处理器
const handleStartRecord = async () => {
  // 10.1 创建AudioRecorder
  recorder = new AudioRecorder()

  // 10.2 开始录音并记录录音状态
  try {
    isRecording.value = true
    await recorder.start()
    Message.success('开始录音')
  } catch (error: any) {
    Message.error(`录音失败: ${error}`)
    isRecording.value = false
  }
}

// 11.停止录音处理器
const handleStopRecord = async () => {
  if (recorder) {
    try {
      // 11.1 等待录音停止并获取录音数据
      await recorder.stop()
      audioBlob.value = recorder.getWAVBlob()

      // 11.2 调用语音转文本处理器并将文本填充到query中
      await handleAudioToText(audioBlob.value)
      Message.success('语音转文本成功')
      query.value = text.value
    } catch (error: any) {
      Message.error(`录音失败: ${error}`)
    } finally {
      isRecording.value = false // 标记为停止录音
    }
  }
}

//8. 页面DOM加载完成后初始化
onMounted(async () => {
  await loadDebugConversationMessages(String(route.params?.app_id), true)
  await nextTick(() => {
    if (scroller.value) {
      scroller.value.scrollToBottom()
    }
  })
})

onUnmounted(() => {
  stopAudioStream()
})

</script>

<template>
  <div>
    <!--历史对话列表-->
    <div :class="`flex flex-col px-6 ${image_urls.length > 0 ? 'h-[calc(100vh-288px)]' : 'h-[calc(100vh-238px)]'}`" v-if="messages.length > 0">
      <dynamic-scroller
        ref="scroller"
        :items="messages.slice().reverse()"
        :min-item-size="1"
        @scroll="handleScroll"
        class=" h-full scrollbar-w-none"
      >
        <template v-slot="{ item, index, active}">
          <dynamic-scroller-item :item="item" :active="active" :data-index="item.id">
            <div class="flex flex-col gap-6 py-6">
              <human-message :query="item.query" :image_urls="item.image_urls" :account="accountStore.account" />
              <ai-message
                :message_id="item.id"
                :enable_text_to_speech="props.text_to_speech.enable"
                :agent_thoughts="item.agent_thoughts"
                :answer="item.answer"
                :app="props.app"
                :suggested_questions="item.id === message_id ? suggested_questions: []"
                :loading="item.id===message_id && debugChatLoading"
                :latency="item.latency"
                :total_token_count="item.total_token_count"
                @select-suggested-question="handleSubmitQuestion"
              />
            </div>
          </dynamic-scroller-item>
        </template>
      </dynamic-scroller>
      <div class="flex items-center justify-center h-[50px]" v-if="task_id && debugChatLoading">
        <a-button :loading="stopDebugChatLoading" class=" rounded-lg px-2" @click="handleStop" >
          <template #icon>
            <icon-poweroff />
          </template>
          停止响应
        </a-button>
      </div>
    </div>
    <!--对话开场白-->
    <div :class="`flex flex-col p-6 gap-2 items-center justify-center ${image_urls.length > 0 ? 'h-[calc(100vh-288px)]' : 'h-[calc(100vh-238px)]'}`" v-else>
      <div class="flex flex-col items-center gap-2">
        <a-avatar :size="48" shape="square" class=" rounded-lg" :image-url="props.app?.icon" />
        <div class="text-lg text-gray-700">{{ props.app?.name }}</div>
      </div>
      <!--对话开场白-->
      <div class="w-full bg-gray-100 px-4 py-3 rounded-lg text-gray-700"
        v-if="props.opening_statement"
      >
        {{ props.opening_statement }}
      </div>
      <!--开场白建议问题-->
      <div class="flex items-center flex-wrap gap-2 w-full">
        <div 
          class="px-4 py-1.5 border rounded-lg text-gray-700 cursor-pointer hover:bg-gray-50"
          v-for="(opening_question, idx) in opening_questions.filter(item => item.trim() !== '')"
          :key="idx"
          @click="async() => await handleSubmitQuestion(opening_question)"
        >
          {{ opening_question }}
        </div>
      </div>
    </div>
    <!--对话输入框-->
    <div>
      <div class="flex flex-col w-full flex-shrink-0">
        <div class="px-6 flex items-center gap-4">
          <!--清除按钮-->
          <a-button
            :loading="deleteDebugConversationLoading"
            class=" flex-shrink-0 !text-gray-700"
            type="text"
            shape="circle"
            @click="async () => {
              await handleStop()
              await handleDeleteDebugConversation(props.app?.id)
              await loadDebugConversationMessages(props.app?.id, true)
            }"
          >
            <template #icon>
              <icon-empty :size="16" />
            </template>
          </a-button>
          <div :class="`${image_urls.length > 0 ? 'h-[100px]' : 'h-[50px]'} flex flex-col justify-center gap-2 px-4 flex-1 border border-gray-200 rounded-[24px]`">
            <!-- 图片列表 -->
            <div v-if="image_urls.length > 0" class="flex items-center gap-2">
              <div
                v-for="(image_url, idx) in image_urls"
                :key="image_url"
                class="w-10 h-10 relative rounded-lg overflow-hidden group cursor-pointer">
                <a-avatar
                  shape="square"
                  :image-url="image_url"
                />
                <div
                  class="hidden group-hover:flex items-center justify-center bg-gray-700/50 w-10 h-10 absolute top-0"
                >
                  <icon-close class="text-white" @click="() => image_urls.splice(idx, 1)" />
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <input v-model="query" type="text" class=" flex-1 outline-0" @keyup.enter="async () => { await handleSubmit() }" />
              <!-- 上传图片输入框 -->
              <input type="file" ref="fileInput" accept="image/*" @change="handleFileChange" class="hidden" />
              <a-button
                :loading="uploadFileLoading"
                size="mini"
                type="text"
                shape="circle"
                class="!text-gray-700"
                @click="triggerFileInput"
              >
                <template #icon>
                  <icon-plus />
                </template>
              </a-button>
              <!-- 语音转文本加载按钮 -->
              <template v-if="audioToTextLoading">
                <a-button
                  size="mini"
                  type="text"
                  shape="circle"
                >
                  <template #icon>
                    <icon-loading />
                  </template>
                </a-button>
              </template>
              <template v-else>
                <!-- 开始音频录制按钮 -->
                <a-button
                  v-if="!isRecording"
                  size="mini"
                  type="text"
                  shape="circle"
                  class="!text-gray-700"
                  @click="handleStartRecord"
                >
                  <template #icon>
                    <icon-voice />
                  </template>
                </a-button>
                <!-- 结束音频录制按钮 -->
                <a-button
                  v-else
                  size="mini"
                  type="text"
                  shape="circle"
                  @click="handleStopRecord"
                >
                  <template #icon>
                    <icon-pause />
                  </template>
                </a-button>
              </template>
              <a-button
                :loading="debugChatLoading"
                type="text"
                shape="circle"
                class="!text-gray-700"
                @click=" async () => { await handleSubmit() }"
              >
                <template #icon>
                  <icon-send :size="16" />
                </template>
              </a-button>
            </div>
          </div>
        </div>
      </div>
      <div class="text-center text-gray-500 text-xs py-4">
        内容由AI生成，无法确保真实准确，仅供参考。
      </div>
    </div>
    <!--停止会话按钮-->
  </div>
</template>
