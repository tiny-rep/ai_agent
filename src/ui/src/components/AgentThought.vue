<script setup lang="ts">
import { type PropType, ref } from 'vue'
import { QueueEvent } from '@/config'

// 1.定义自定义组件所需数据
const props = defineProps({
  loading: { type: Boolean, default: false, required: true },
  agent_thoughts: { type: Array as PropType<Record<string, any>[]>, default: [], required: true },
})
const visible = ref(false)

const getWfNodeMsg = (msg:any) => {
  const msgobj = JSON.parse(msg.observation)
  // @ts-ignore
  const node_title = msgobj.value.node_results[0].node_data.title
  const wf_cn_name = msgobj.wf_cn_name
  return `${wf_cn_name}-${node_title}`
}

</script>

<template>
  <!-- 智能体推理步骤 -->
  <div :class="`flex flex-col rounded-2xl border ${visible ? 'w-[320px]' : 'w-[180px]'}`">
    <div
      :class="`flex items-center justify-between h-10 rounded-2xl bg-gray-100 px-4 text-gray-700 cursor-pointer w-auto ${visible ? 'rounded-bl-none rounded-br-none' : ''}`"
      @click="visible = !visible"
    >
      <!-- 左侧图标与标题 -->
      <div class="flex items-center gap-2">
        <icon-list />
        {{ visible ? '隐藏' : '显示' }}运行流程
      </div>
      <!-- 右侧图标 -->
      <div class="">
        <template v-if="props.loading">
          <icon-loading />
        </template>
        <template v-else>
          <icon-up v-if="visible" />
          <icon-down v-else />
        </template>
      </div>
    </div>
    <!-- 底部内容 -->
    <a-collapse  class="agent-thought" v-if="visible" destroy-on-hide :bordered="false">
      <a-collapse-item
        v-for="agent_thought in props.agent_thoughts.filter((item: any) =>
          [
            QueueEvent.longTermMemoryRecall,
            QueueEvent.agentThought,
            QueueEvent.datasetRetrieval,
            QueueEvent.agentAction,
            QueueEvent.agentMessage,
            QueueEvent.agentThink,
            QueueEvent.workflowNodeMessage
          ].includes(item.event),
        )"
        :key="agent_thought.id"
      >
        <template #expand-icon>
          <icon-file v-if="agent_thought.event === QueueEvent.longTermMemoryRecall" />
          <icon-language v-else-if="agent_thought.event === QueueEvent.agentThought" />
          <icon-storage v-else-if="agent_thought.event === QueueEvent.datasetRetrieval" />
          <icon-tool v-else-if="agent_thought.event === QueueEvent.agentAction" />
          <icon-message v-else-if="agent_thought.event === QueueEvent.agentMessage" />
          <icon-robot v-else-if="agent_thought.event === QueueEvent.agentThink" />
          <icon-relation v-else-if="agent_thought.event === QueueEvent.workflowNodeMessage" />
        </template>
        <template #header>
          <div class="text-gray-700" v-if="agent_thought.event === QueueEvent.longTermMemoryRecall">
            长期记忆召回
          </div>
          <div class="text-gray-700" v-if="agent_thought.event === QueueEvent.agentThought">
            智能体推理
          </div>
          <div class="text-gray-700" v-if="agent_thought.event === QueueEvent.datasetRetrieval">
            搜索知识库
          </div>
          <div class="text-gray-700" v-if="agent_thought.event === QueueEvent.agentAction">
            调用工具
          </div>
          <div class="text-gray-700" v-if="agent_thought.event === QueueEvent.agentMessage">
            智能体消息
          </div>
          <div class="text-gray-700" v-if="agent_thought.event === QueueEvent.agentThink">
            思考过程
          </div>
          <div class="text-gray-700 truncate" v-if="agent_thought.event === QueueEvent.workflowNodeMessage" :title="getWfNodeMsg(agent_thought)">
            工作流-{{ getWfNodeMsg(agent_thought) }}
          </div>
        </template>
        <template #extra>
          <div class="text-gray-500">{{ agent_thought.latency.toFixed(2) }}s</div>
        </template>
        <div
          v-if="['agent_thought', 'agent_message'].includes(agent_thought.event)"
          class="text-xs text-gray-500 line-clamp-4 break-all"
        >
          {{ agent_thought.thought || '-' }}
        </div>
        <a-scrollbar v-else-if="['agent_think'].includes(agent_thought.event)" class="h-[120px] overflow-auto" >
          <div class="text-xs text-gray-500 break-all">
            {{ agent_thought.thought || '-' }}
          </div>
        </a-scrollbar>
        <div v-else class="text-xs text-gray-500 line-clamp-4 break-all">
          {{ agent_thought.observation || '-' }}
        </div>
      </a-collapse-item>
    </a-collapse>
  </div>
</template>

<style scoped>
.agent-thought {
  .arco-collapse-item-content {
    padding: 0 16px;
  }
}
:deep(.arco-collapse-item-header-title) {
  width: 80%;
}
</style>
