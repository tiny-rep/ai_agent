import { ref } from "vue"
import { audioToText, messageToAudio } from "@/services/audio"
import { Message } from "@arco-design/web-vue"

export const useAudioToText = () => {
  const loading = ref(false)
  const text = ref('')

  const handleAudioToText = async (file: Blob) => {
    try {
      loading.value = true
      const resp = await audioToText(file)
      Message.success("语音转文本成功")
      text.value = resp.data.text
    } finally {
      loading.value = false
    }
  }

  return { loading, text, handleAudioToText } 
}

export const useMessageToAudio = () => {
  const loading = ref(false)

  const handleMessageToAudio = async (
    message_id: string,
    onData: (event_response: Record<string, any>) => void
  ) => {
    try {
      loading.value = true
      await messageToAudio(message_id, onData)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleMessageToAudio }
}

export const useAudioPlayer = () => {
  const audioContext = ref<AudioContext>() //音频上下文
  const mediaSource = ref<MediaSource>() //媒体资源
  const audioElement = ref<HTMLAudioElement>() //HTML音频元素
  const sourceBuffer = ref<SourceBuffer>() //资源缓冲
  const isAudioLoaded = ref(false) //是否加载音频完毕
  const isPlaying = ref(false) //是否正在播放
  const { loading: textToAudioLoading, handleMessageToAudio } = useMessageToAudio()

  //定义资源打开监听事件
  const onSourceOpen = () => {
    sourceBuffer.value = mediaSource.value?.addSourceBuffer('audio/mpeg')
  }

  const appendSourceBuffer = (base64Data: string) => {
    try {
      //1. base64 => binary
      const binaryString = atob(base64Data)
      const buffer = new ArrayBuffer(binaryString.length)
      const uint8Array = new Uint8Array(buffer)

      //2. binary => uint8array
      for (let i = 0; i< binaryString.length; i++) {
        uint8Array[i] = binaryString.charCodeAt(i)
      }

      //3. 数据存在 并且没有更新则插入数据
      if (sourceBuffer.value && !sourceBuffer.value.updating) {
        sourceBuffer.value.appendBuffer(uint8Array)
      } else {
        //如果sourceBuffer正在更新，则尝试稍后插入数据
        sourceBuffer.value?.addEventListener("updateend", () => {
          appendSourceBuffer(base64Data)
        }, { once: true })
      }

    } catch (err) {
      Message.error(`添加sourceBuffer错误：${err}`)
    }
  }

  //拉取音频流数据处理器
  const fetchAudioStream = async (messageId: string) => {
    await handleMessageToAudio(messageId, (event_response) => {
      const event = event_response?.event
      const data = event_response?.data

      if (event == 'tts_message') {
        appendSourceBuffer(data?.audio)
      }
    })
  }

  //定义开始播放音频流函数
  const startAudioStream = (messageId: string) => {
    // 1. 如果数据已经加载过且正在播放，则无需重复请求
    if (isAudioLoaded.value && audioElement.value?.paused === false) {
      // 2. 音频已加载并且正在播放，直接播放（重置播放时间为0）
      if (audioElement.value instanceof HTMLAudioElement) {
        audioElement.value.currentTime = 0
        audioElement.value.play().then(() => {
          isPlaying.value = true
        })
      }
      return
    }

    //3. 如果音频数据尚未加载，则初始化audioContext和MediaSource
    audioContext.value = new AudioContext()
    mediaSource.value = new MediaSource()

    //4. 使用new Audio 来播放音频流，而不是创建<audio>标签
    audioElement.value = new Audio()

    //5. 监听暂停与播放
    audioElement.value.addEventListener('play', onAudioPlay)
    audioElement.value.addEventListener('pause', onAudioPause)
    audioContext.value.addEventListener('ended', onAudioPause)

    //6. 为audio添加播放音频URL
    audioElement.value.src = URL.createObjectURL(mediaSource.value)

    //7. 为mediaSource添加事件监听
    mediaSource.value.addEventListener('sourceopen', onSourceOpen, { once: true })
    
    //8. 拉音频
    fetchAudioStream(messageId)

    //9. 标记音频数据已加载并播放音频
    isAudioLoaded.value = true
    audioElement.value.play().then( () => {
      isPlaying.value = true
    })
  }

  
  const stopAudioStream =() => {
    if (audioElement.value) {
      if (audioElement.value instanceof HTMLAudioElement) {
        audioElement.value.pause()
        audioElement.value.currentTime = 0
      }

      isPlaying.value = false
    }
  }

  const onAudioPlay = () => {
    isPlaying.value = true
  }

  const onAudioPause = () => {
    isPlaying.value = false
  }

  return { isAudioLoaded, isPlaying, startAudioStream, stopAudioStream, textToAudioLoading }
}