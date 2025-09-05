<script setup lang="ts">

import { computed, type PropType,nextTick, ref, watch, onMounted, onUnmounted } from 'vue'
// @ts-ignore
import MarkdownIt from 'markdown-it'
import DotFlashing from '@/components/DotFlashing.vue'
import { useAudioPlayer } from '@/hooks/use-audio'
import AgentThought from './AgentThought.vue'
import "github-markdown-css"
import { echartsPlugin } from '@/extends/markdown-it-echarts-plugin'
import type { ECharts } from 'echarts'
import * as echarts from 'echarts'

//1. 定义变量
const props = defineProps({
  app: {type: Object, default: {}, required: true},
  message_id: { type: String, default: '', required: false },
  enable_text_to_speech: { type: Boolean, default: false, required: false },
  answer: {type: String, default: '', required: true},
  loading: {type: Boolean, default: false, required: false},
  latency:{type: Number, default: 0, required: false},
  total_token_count: {type: Number, default: 0, required: false},
  agent_thoughts: {type: Array as PropType<Record<string, any>[]>, default: [], required: true},
  suggested_questions: {type: Array as PropType<string[]>, default: [], required: false},
  message_class: { type: String, default: '!bg-gray-100', required: false }
})
const containerRef = ref<HTMLElement>()
const chartInstances = ref(new Map<string, ECharts>())
const { textToAudioLoading, isPlaying, startAudioStream, stopAudioStream } = useAudioPlayer()
const emits = defineEmits(['selectSuggestedQuestion'])
const md = MarkdownIt()
let loadingDot = ['.  ', '.. ', '...']
let dotIndex = 0

echartsPlugin(md)

const computedMarkdown = computed(() => {
  return md.render(props.answer)
})


/**
 * 绘制图表
 */
const drawEcharts = async () => {
  await nextTick()
  if (!containerRef.value) return

  const containers = containerRef.value.querySelectorAll(
    '.echarts-container:not([data-rendered="true"])'
  )

  containers.forEach((container) => {
    try {
      if (chartInstances.value.has(container.id)) return

      const loader = container.querySelector('.chart-loading')
      loader?.classList.add('loading-active')

      const rawOption = container.getAttribute('data-option')
      if (!rawOption) return

      const decodedOption = decodeURIComponent(rawOption)
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")

      const option = JSON.parse(decodedOption)
      const chart = echarts.init(container as HTMLElement)

      container.setAttribute('data-rendered', 'true')
      chart.setOption(option)
      chartInstances.value.set(container.id, chart)

      loader?.remove()
      setTimeout(() => chart.resize(), 200)
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误'
      container.innerHTML = `
        <div class="flex justify-center items-center h-full chart-error" style="white-space: pre;">
          ${props.loading ? '图表加载中' + loadingDot[dotIndex] : `图表加载失败: ${errorMessage}`}
        </div>
      `
      dotIndex = (dotIndex + 1) % loadingDot.length
    }
  })
}
/**
 * 销毁图表
 */
const destroyCharts = () => {
  if (!containerRef.value) return

  containerRef.value.querySelectorAll('.echarts-container').forEach((container) => {
    const chart = chartInstances.value.get(container.id)
    chart?.dispose()
  })
  chartInstances.value.clear()
}

watch(
  () => props.answer,
  async () => {
    destroyCharts()
    await drawEcharts()
  },
  { flush: 'post' }
)
onMounted (async () => {
  await drawEcharts()
})
onUnmounted(() => {
  destroyCharts()
})


</script>

<template>
  <div ref="containerRef" class="flex gap-2 group">
    <a-avatar :size="30" shape="circle" class=" flex-shrink-0" :image-url="props.app?.icon" />
    <div class="flex flex-col items-start gap-2">
      <div class="text-gray-700 font-bold">{{ props.app?.name }}</div>
      <agent-thought :agent_thoughts="props.agent_thoughts" :loading="props.loading" />
      <!--AI 消息-->
      <div v-if="props.loading && props.answer.trim() === ''"
          :class="`${props.message_class} bg-gray-100 border border-gray-200 text-gray-700 px-4 py-3 rounded-2x1 break-all`">
          <dot-flashing/>
      </div>
      <div v-else
        :class="`${props.message_class} markdown-body border border-gray-200 text-gray-700 px-4 py-3 rounded-2x1 break-all`"
        v-html="computedMarkdown"
        >
      </div>
      <!--消息提示-->
      <div class="w-full flex items-center justify-between">
        <a-space class=" text-xs" >
          <template #split>
            <a-divider direction="vertical" class="m-0" />
          </template>
          <div class="flex items-center gap-1 text-gray-500">
            <icon-check />
            {{ props.latency.toFixed(2) }}s
          </div>
          <div class="text-gray-500">{{ props.total_token_count }} Tokens</div>
        </a-space>
        <!-- 播放音频&暂停播放 -->
        <div v-if="props.enable_text_to_speech" class="flex items-center gap-2">
          <template v-if="textToAudioLoading">
            <icon-loading class=" hidden group-hover:block text-gray-500" />
          </template>
          <template v-else>
            <icon-pause
              v-if="isPlaying"
              class=" hidden group-hover:block text-blue-700 cursor-pointer hover:text-blue-700"
              @click="() => stopAudioStream()"
            />
            <icon-play-circle
              v-else
              class=" hidden group-hover:block text-gray-400 cursor-pointer hover:text-gray-700"
              @click="() => startAudioStream(props.message_id)"
            />
          </template>
        </div>
      </div>
      <!--建议问题-->
      <div class="flex flex-col gap-2" v-if="props.suggested_questions.length > 0">
        <div
          v-for="(suggested_question, idx) in props.suggested_questions"
          :key="idx"
          class="px-4 py-1.5 border rounded-lg text-gray-700 cursor-pointer hover:bg-gray-50"
          @click="() => emits('selectSuggestedQuestion', suggested_question)"
        >
          {{ suggested_question }}
        </div>
      </div>
    </div>
  </div>
</template>
<style>
.markdown-body {
  font-size: 14px;
}
.markdown-body pre {
  @apply bg-gray-700 text-white
}
</style>