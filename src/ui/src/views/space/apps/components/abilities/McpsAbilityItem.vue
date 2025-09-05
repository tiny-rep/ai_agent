<script setup lang="ts">
import { nextTick, type PropType, ref, watch } from 'vue'
import { useUpdateDraftAppConfig } from '@/hooks/use-app'
import { cloneDeep, isEqual } from 'lodash'
import { Message } from '@arco-design/web-vue'
import { useGetMcpToolsWithPage } from '@/hooks/use-mcp-tool'

// 1.定义自定义组件所需数据
const props = defineProps({
  app_id: { type: String, default: '', required: true },
  mcps: {
    type: Array as PropType<
      {
        id: string
        name: string
        icon: string
        description: string
      }[]
    >,
    default: [],
    required: true,
  },
})
const emits = defineEmits(['update:mcps'])
const { loading: updateDraftAppConfigLoading, handleUpdateDraftAppConfig } =
  useUpdateDraftAppConfig()
const { loading, paginator, mcp_tools: apiMcpTools, loadMcpTools } = useGetMcpToolsWithPage()
const mcpsModalVisible = ref(false)
const isMcpsInit = ref(false)
const activateMcps = ref<Record<string, any>[]>([])
const originMcps = ref<Record<string, any>[]>([])

// 2.定义滚动数据分页处理器
const handleScroll = async (event: UIEvent) => {
  // 2.1 获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 2.2 判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (loading.value) return
    await loadMcpTools(false, '')
  }
}

// 3.定义判断Mcp tool数据是否发生变化函数
const isMcpsModified = () => {
  return isEqual(activateMcps.value, originMcps.value)
}

// 4.定义取消模态窗处理器
const handleCancelMcpsModal = () => {
  // 4.1 隐藏模态窗
  mcpsModalVisible.value = false

  // 4.2 还原初始值
  activateMcps.value = originMcps.value
  isMcpsInit.value = false
}

// 7.Mcp Tool选择处理器
const handleSelectMcps = (idx: number) => {
  // 7.1 提取对应的mcp id
  const mcp = apiMcpTools.value[idx]

  // 7.2 检测id是否选中，如果是选中则删除
  if (activateMcps.value.some((activateMcp) => activateMcp.id === mcp.id)) {
    activateMcps.value = activateMcps.value.filter(
      (activateMcp) => activateMcp.id !== mcp.id,
    )
  } else {
    // 7.3 检测已关联的mcp tool数量
    if (activateMcps.value.length >= 5) {
      Message.warning('关联Mcp tool已超过5个，无法继续关联')
      return
    }
    // 7.4 添加数据到激活mcp列表
    activateMcps.value.push({
      id: mcp.id,
      name: mcp.name,
      icon: mcp.icon,
      description: mcp.description,
    })
  }
}

// 8.提交更新关联MCP服务
const handleSubmitMcps = async () => {
  try {
    // 8.1 处理数据并完成API接口提交
    await handleUpdateDraftAppConfig(props.app_id, {
      mcps: activateMcps.value.map((activateMcp) => activateMcp.id),
    })

    // 8.2 接口更新更新成功，同步表单信息
    originMcps.value = activateMcps.value
    await nextTick()

    // 8.3 双向同步更新props中的数据
    emits('update:mcps', activateMcps.value)

    // 8.4 隐藏模态窗
    handleCancelMcpsModal()
  } catch (e) {}
}

// 10.监听草稿配置关联的工作流列表
watch(
  () => props.mcps,
  (newValue) => {
    // 10.1 检测数据是否初始化
    if (!isMcpsInit.value || !isMcpsModified()) {
      // 10.2 判断草稿配置是否已传递配置
      if (newValue && newValue.length > 0) {
        // 10.3 赋初始值
        const initData = props.mcps.map((mcp) => {
          return {
            id: mcp.id,
            name: mcp.name,
            icon: mcp.icon,
            description: mcp.description,
          }
        })
        activateMcps.value = cloneDeep(initData)
        originMcps.value = cloneDeep(initData)

        // 10.4 修改初始化状态
        isMcpsInit.value = true
      }
    }
  },
  { immediate: true, deep: true },
)

// 12.监听知识库模态窗显示or隐藏
watch(
  () => mcpsModalVisible.value,
  async (newValue) => {
    // 12.1 显示状态，重新加载数据，获取最新的知识库列表
    if (newValue) {
      await loadMcpTools(true, '')
    } else {
      // 12.2 隐藏状态，清空数据
      apiMcpTools.value.splice(0, apiMcpTools.value.length)
    }
  },
)
</script>

<template>
  <div class="">
    <a-collapse-item key="mcps" class="app-ability-item">
      <template #header>
        <div class="text-gray-700 font-bold">MCP服务</div>
      </template>
      <template #extra>
        <a-button
          size="mini"
          type="text"
          class="!text-gray-700"
          @click.stop="mcpsModalVisible = true"
        >
          <template #icon>
            <icon-plus />
          </template>
        </a-button>
      </template>
      <div v-if="props.mcps?.length > 0" class="flex flex-col gap-1">
        <div
          v-for="(mcp, idx) in props.mcps"
          :key="mcp.id"
          class="flex items-center justify-between bg-white p-3 rounded-lg cursor-pointer hover:shadow-sm group"
        >
          <!-- 左侧Mcp信息 -->
          <div class="flex items-center gap-2">
            <!-- 图标 -->
            <a-avatar
              :size="36"
              shape="square"
              class="rounded flex-shrink-0"
              :image-url="mcp.icon"
            />
            <!-- 名称与描述信息 -->
            <div class="flex flex-col flex-1 gap-1 h-9">
              <div class="text-gray-700 font-bold leading-[18px] line-clamp-1 break-all">
                {{ mcp.name }}
              </div>
              <div class="text-gray-500 text-xs line-clamp-1 break-all">
                {{ mcp.description }}
              </div>
            </div>
          </div>
          <!-- 右侧删除按钮 -->
          <a-button
            size="mini"
            type="text"
            class="hidden group-hover:block flex-shrink-0 ml-2 !text-red-700 rounded"
            @click="
              async () => {
                // 1.清除props中指定的数据
                const newMcps = [...props.mcps]
                newMcps.splice(idx, 1)
                activateMcps.splice(idx, 1)

                // 2.提交草稿配置到接口
                await handleUpdateDraftAppConfig(props.app_id, {
                  mcps: newMcps.map((item) => item.id),
                })

                // 3.更新数据并确保数据完成更新
                isMcpsInit = false
                emits('update:mcps', newMcps)
              }
            "
          >
            <template #icon>
              <icon-delete />
            </template>
          </a-button>
        </div>
      </div>
      <div v-else class="text-xs text-gray-500 leading-[22px]">
        Mcp服务提供Mcp协议访问第三方业务系统。
      </div>
    </a-collapse-item>
    <!-- 工作流模态窗 -->
    <a-modal
      :visible="mcpsModalVisible"
      hide-title
      :footer="false"
      :width="400"
      class="mcps-modal"
      modal-class="h-[calc(100vh-32px)] right-4"
      @cancel="handleCancelMcpsModal"
    >
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between mb-6">
        <div class="text-lg font-bold text-gray-700">选择关联Mcp服务</div>
        <a-button
          type="text"
          class="!text-gray-700"
          size="small"
          @click="handleCancelMcpsModal"
        >
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 中间工作流容器 -->
      <div class="h-[calc(100vh-180px)] mb-4 overflow-scroll scrollbar-w-none">
        <a-spin
          :loading="loading"
          class="block h-full w-full scrollbar-w-none overflow-scroll"
          @scroll="handleScroll"
        >
          <!-- 工作流列表 -->
          <div class="flex flex-col gap-2">
            <!-- 有数据UI状态 -->
            <div
              v-for="(mcp, idx) in apiMcpTools"
              :key="mcp.id"
              :class="`flex items-center gap-2 border px-3 py-2 rounded-lg cursor-pointer hover:bg-blue-50 hover:border-blue-700 ${activateMcps.some((activateMcp) => activateMcp.id === mcp.id) ? 'bg-blue-50 border-blue-700' : ''}`"
              @click="() => handleSelectMcps(idx)"
            >
              <a-avatar
                :size="24"
                shape="square"
                class="flex-shrink-0 rounded"
                :image-url="mcp.icon"
              />
              <div class="line-clamp-1 text-gray-500 flex-1">{{ mcp.name }}</div>
            </div>
            <!-- 无数据UI状态 -->
            <a-empty
              v-if="apiMcpTools.length === 0"
              description="没有可用的Mcp服务"
              class="h-[400px] flex flex-col items-center justify-center"
            />
          </div>
          <!-- 加载器 -->
          <a-row v-if="paginator.total_page >= 2">
            <!-- 加载数据中 -->
            <a-col
              v-if="paginator.current_page <= paginator.total_page"
              :span="24"
              class="!text-center"
            >
              <a-space class="my-4">
                <a-spin />
                <div class="text-gray-400">加载中</div>
              </a-space>
            </a-col>
            <!-- 数据加载完成 -->
            <a-col v-else :span="24" class="!text-center">
              <div class="text-gray-400 my-4">数据已加载完成</div>
            </a-col>
          </a-row>
        </a-spin>
      </div>
      <!-- 底部选中Mcp及按钮 -->
      <div class="flex items-center justify-between">
        <!-- 左侧提示文字 -->
        <div class="">{{ activateMcps.length }} 个Mcp服务被选中</div>
        <!-- 按钮组 -->
        <a-space :size="12">
          <a-button class="rounded-lg" @click="handleCancelMcpsModal">取消</a-button>
          <a-button
            :loading="updateDraftAppConfigLoading"
            type="primary"
            class="rounded-lg"
            @click="handleSubmitMcps"
          >
            添加
          </a-button>
        </a-space>
      </div>
    </a-modal>
  </div>
</template>

<style>
.mcps-modal {
  .arco-modal-wrapper {
    text-align: right;
  }
}
</style>
