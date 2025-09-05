<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  useCreateMcpTool,
  useGetMcpToolsWithPage,
  useGetMcpTool,
  useDeleteMcpTool,
  useUpdateMcpTool
} from '@/hooks/use-mcp-tool'
import { useUploadImage } from '@/hooks/use-upload-file'
import moment from 'moment/moment'
import { typeMap } from '@/config'
import { type FileItem, Form, type ValidatedError } from '@arco-design/web-vue'
import type { CreateMcpToolRequest, UpdateMcpToolRequest } from '@/models/mcp-tool'
import { omit } from 'lodash'

// 1.定义额面所需数据
const route = useRoute()
const props = defineProps({
  createType: { type: String, required: true },
})
const emits = defineEmits(['update:create-type'])
const form = ref<{
  fileList: FileItem[]
  icon: string
  name: string
  transport_type: string
  description: string
  provider_name: string
  host: string
  headers: Record<string, any>[]
}>({
  fileList: [],
  icon: '',
  name: '',
  transport_type: 'sse',
  description: '',
  provider_name: '',
  host: '',
  headers: []
})
const { image_url, handleUploadImage } = useUploadImage()

const { loading: createMcpToolLoading, handleCreateMcpTool } = useCreateMcpTool()
const { loading: getMcpToolLoading, mcp_tools, loadMcpTools, paginator } = useGetMcpToolsWithPage()
const { loading: getMcpToolInfoLoading, mcp_tool, loadMcpTool: getMcpToolInfo } = useGetMcpTool()
const { handleDeleteMcpTool } = useDeleteMcpTool()
const { loading: updateMcpToolLoading, handleUpdateMcpTool } = useUpdateMcpTool()
 
const formRef = ref<InstanceType<typeof Form>>()
const showIdx = ref<number>(-1)
const loading = ref<boolean>(false)
const showUpdateModal = ref<boolean>(false)


// 2.定义滚动分页处理器
const handleScroll = (event: UIEvent) => {
  // 2.1 获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 2.2 判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (getMcpToolLoading.value) return
    loadMcpTools(false, String(route.query?.search_word ?? ''))
  }
}

// 3.定义打开更新模态窗
const handleUpdate = async () => {
  // 3.1 获取当前显示的provider_id
  const mcp_tool_id = mcp_tools.value[showIdx.value]['id']

  // 3.2 根据拿到的id获取该工具提供商的详情信息
  await getMcpToolInfo(mcp_tool_id)

  // 3.3 更新form表单数据
  formRef.value?.resetFields()
  form.value.fileList = [{ uid: '1', name: 'MCP服务图标', url: mcp_tool.value.icon }]
  form.value.icon = mcp_tool.value.icon
  form.value.name = mcp_tool.value.name
  form.value.description = mcp_tool.value.description
  form.value.provider_name = mcp_tool.value.provider_name
  form.value.host = mcp_tool.value.params.host
  form.value.headers = mcp_tool.value.params.headers
  form.value.transport_type = mcp_tool.value.transport_type


  showUpdateModal.value = true
}

// 4.定义删除工具提供者处理器
const handleDelete = () => {
  // 4.1 提取选中数据条目的提供者id
  const mcp_tool_id = mcp_tools.value[showIdx.value]['id']

  // 4.2 调用删除Api工具提供者处理器
  handleDeleteMcpTool(mcp_tool_id, () => {
    // 4.3 关闭模态窗+抽屉
    handleCancel()
    showIdx.value = -1

    // 4.4 重新加载数据
    loadMcpTools(true, String(route.query?.search_word ?? ''))
  })
}

// 提交模态窗处理器
const handleSubmit = async ({
  values,
  errors,
}: {
  values: Record<string, any>
  errors: Record<string, ValidatedError> | undefined
}) => {
  // 1.如果存在错误则直接结束
  if (errors) return

  const mcp_params = {
    "host": values["host"],
    "headers": values["headers"]
  }
  const formdata = omit(values, ['host', 'headers'])
  formdata['mcp_params'] = mcp_params

  // 2.根据不同的类型发起不同的请求
  if (props.createType === 'mcp-tool') {
    // 3.调用处理器发起创建请求
    await handleCreateMcpTool(formdata as CreateMcpToolRequest)
  } else if (showUpdateModal.value) {
    // 4.调用接口发起更新API工具请求
    await handleUpdateMcpTool(
      mcp_tools.value[showIdx.value]['id'],
      formdata as UpdateMcpToolRequest,
    )
  }

  // 5.执行后续操作，涵盖隐藏模态窗、隐藏抽屉
  handleCancel()
  showIdx.value = -1

  // 6.重新加载数据
  await loadMcpTools(true, String(route.query?.search_word ?? ''))
}

// 取消显示模态窗处理器
const handleCancel = () => {
  // 1.重置整个表单的数据
  formRef.value?.resetFields()

  // 2.隐藏表单模态窗
  emits('update:create-type', '')
  showUpdateModal.value = false
}

// 页面DOM加载完毕初始化数据
onMounted(() => loadMcpTools(true, String(route.query?.search_word ?? '')))

// 监听路由query变化
watch(
  () => route.query?.search_word,
  (newValue) => {
    loadMcpTools(true, String(newValue))
  },
)

// 监听路由create_type变化
watch(
  () => route.query?.create_type,
  (newValue) => {
    if (newValue === 'mcp-tool') emits('update:create-type', 'mcp-tool')
  },
  { immediate: true },
)
</script>

<template>
  <a-spin
    :loading="loading"
    class="block h-full w-full scrollbar-w-none overflow-scroll"
    @scroll="handleScroll"
  >
    <!-- Mcp列表 -->
    <a-row :gutter="[20, 20]" class="flex-1">
      <!-- 有数据的UI状态 -->
      <a-col v-for="(mcptool, idx) in mcp_tools" :key="mcptool.name" :span="6">
        <a-card hoverable class="cursor-pointer rounded-lg" @click="showIdx = Number(idx)">
          <!-- 顶部提供商名称 -->
          <div class="flex items-center gap-3 mb-3">
            <!-- 左侧图标 -->
            <a-avatar :size="40" shape="square" :image-url="mcptool.icon" />
            <!-- 右侧工具信息 -->
            <div class="flex flex-col">
              <div class="text-base text-gray-900 font-bold">{{ mcptool.name }}</div>
              <div class="text-xs text-gray-500 line-clamp-1">
                提供商 {{ mcptool.name }}
              </div>
            </div>
          </div>
          <!-- 提供商的描述信息 -->
          <div class="leading-[18px] text-gray-500 h-[72px] line-clamp-4 mb-2">
            {{ mcptool.description }}
          </div>
          <!-- 提供商的发布信息 -->
          <div class="flex items-center gap-1.5">
            <a-avatar :size="18" class="bg-blue-700">
              <icon-user />
            </a-avatar>
            <div class="text-xs text-gray-400">
              编辑时间
              {{ moment(mcptool.updated_at * 1000).format('MM-DD HH:mm') }}
            </div>
          </div>
        </a-card>
      </a-col>
      <!-- 没数据的UI状态 -->
      <a-col v-if="mcp_tools.length === 0" :span="24">
        <a-empty
          description="没有可用的MCP服务"
          class="h-[400px] flex flex-col items-center justify-center"
        />
      </a-col>
    </a-row>
    <!-- 加载器 -->
    <a-row v-if="paginator.total_page >= 2">
      <!-- 加载数据中 -->
      <a-col v-if="paginator.current_page <= paginator.total_page" :span="24" align="center">
        <a-space class="my-4">
          <a-spin />
          <div class="text-gray-400">加载中</div>
        </a-space>
      </a-col>
      <!-- 数据加载完成 -->
      <a-col v-else :span="24" align="center">
        <div class="text-gray-400 my-4">数据已加载完成</div>
      </a-col>
    </a-row>
    <!-- 卡片抽屉 -->
    <a-drawer
      :visible="showIdx != -1"
      :width="350"
      :footer="false"
      title="MCP服务详情"
      :drawer-style="{ background: '#F9FAFB' }"
      @cancel="showIdx = -1"
    >
      <!-- 外部容器，用于判断showIdx是否为-1，为-1的时候就不显示 -->
      <div v-if="showIdx != -1" class="">
        <!-- 顶部提供商名称 -->
        <div class="flex items-center gap-3 mb-3">
          <!-- 左侧图标 -->
          <a-avatar :size="40" shape="square" :image-url="mcp_tools[showIdx].icon" />
          <!-- 右侧MCP服务信息 -->
          <div class="flex flex-col">
            <div class="text-base text-gray-900 font-bold">
              {{ mcp_tools[showIdx].name }}
            </div>
            <div class="text-xs text-gray-500 line-clamp-1">
              提供商 {{ mcp_tools[showIdx].provider_name }}
            </div>
          </div>
        </div>
        <!-- MCP服务的描述信息 -->
        <div class="leading-[18px] text-gray-500 mb-4">
          {{ mcp_tools[showIdx].description }}
        </div>
        <!-- 编辑按钮 -->
        <a-button
          :loading="getMcpToolInfoLoading"
          type="dashed"
          long
          class="mb-2 rounded-lg"
          @click="handleUpdate"
        >
          <template #icon>
            <icon-settings />
          </template>
          编辑工具
        </a-button>
        <!-- 分隔符 -->
        <hr class="my-4" /> 
        <!-- 工具列表 -->
        <a-card
          :key="mcp_tools[showIdx].name"
          class="cursor-pointer flex flex-col rounded-xl"
        >
          <!-- MCP服务参数 -->
          <div class="flex items-center gap-2 my-4">
            <div class="text-xs font-bold text-gray-500">参数</div>
            <hr class="flex-1" />
          </div>
          <!-- 参数列表 -->
          <div class="flex flex-col gap-4" v-if="mcp_tools[showIdx].transport_type === 'sse'">
            <!-- 上半部分 -->
            <div class="flex items-center gap-2 text-xs">
              <div class="text-gray-900 font-bold">MCP地址</div>
              <div class="text-gray-500">{{ mcp_tools[showIdx].params.host }}</div>
              <div class="text-red-700">必填</div>
            </div>
            <!-- 参数描述信息 -->
            <div class="text-xs text-gray-500">MCP服务器访问地址</div>
          </div>
        </a-card>
      </div>
    </a-drawer>
    <!-- 新建/修改模态窗 -->
    <a-modal
      :width="630"
      :visible="props.createType === 'mcp-tool' || showUpdateModal"
      hide-title
      :footer="false"
      modal-class="rounded-xl"
      @cancel="handleCancel"
    >
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between">
        <div class="text-lg font-bold text-gray-700">
          {{ props.createType === 'mcp-tool' ? '新建' : '更新' }}MCP服务
        </div>
        <a-button type="text" class="!text-gray-700" size="small" @click="handleCancel">
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 中间表单 -->
      <div class="pt-6">
        <a-form ref="formRef" :model="form" @submit="handleSubmit" layout="vertical">
          <a-form-item
            field="fileList"
            hide-label
            :rules="[{ required: true, message: 'Mcp服务图标不能为空' }]"
          >
            <a-upload
              :limit="1"
              list-type="picture-card"
              accept="image/png, image/jpeg"
              class="!w-auto mx-auto"
              v-model:file-list="form.fileList"
              image-preview
              :custom-request="
                (option:any) => {
                  const uploadTask = async () => {
                    const { fileItem, onSuccess, onError } = option
                    await handleUploadImage(fileItem.file as File)
                    form.icon = image_url
                    onSuccess(image_url)
                  }

                  uploadTask()

                  return {}
                }
              "
              :on-before-remove="
                async (fileItem:any) => {
                  form.icon = ''
                  return true
                }
              "
            />
          </a-form-item>
          <a-form-item
            field="name"
            label="名称"
            asterisk-position="end"
            :rules="[{ required: true, message: 'MCP服务名称不能为空' }]"
          >
            <a-input
              v-model="form.name"
              placeholder="请输入MCP服务名称，确保名称含义清晰"
              show-word-limit
              :max-length="60"
            />
          </a-form-item>
          <a-form-item
            field="provider_name"
            label="提供者"
            asterisk-position="end"
            :rules="[{ required: true, message: 'MCP服务提供者名称不能为空' }]"
          >
            <a-input
              v-model="form.provider_name"
              placeholder="请输入MCP服务提供者"
              show-word-limit
              :max-length="160"
            />
          </a-form-item>
          <a-form-item
            field="host"
            label="服务地址"
            asterisk-position="end"
            :rules="[{ required: true, message: 'MCP服务地址不能为空' }]"
          >
            <a-input
              v-model="form.host"
              placeholder="请输入MCP服务访问地址"
              show-word-limit
              :max-length="200"
            />
          </a-form-item>
          <a-form-item label="headers">
            <!-- 请求头表单 -->
            <div class="rounded-lg border border-gray-200 w-full overflow-x-auto">
              <table class="w-full leading-[18px] text-xs text-gray-700 font-normal mb-3">
                <thead class="text-gray-500">
                  <tr class="border-b border-gray-200">
                    <th class="p-2 pl-3 font-medium">Key</th>
                    <th class="p-2 pl-3 font-medium">Value</th>
                    <th class="p-2 pl-3 font-medium w-[50px]">操作</th>
                  </tr>
                </thead>
                <tbody v-if="form.headers && form.headers.length > 0" class="border-b border-gray-200">
                  <tr
                    v-for="(header, idx) in form.headers"
                    :key="idx"
                    class="border-b last:border-0 border-gray-200"
                  >
                    <td class="p-2 pl-3">
                      <a-form-item :field="`headers[${idx}].key`" hide-label class="m-0">
                        <a-input v-model="header.key" placeholder="请输入请求头键名" />
                      </a-form-item>
                    </td>
                    <td class="p-2 pl-3">
                      <a-form-item :field="`headers[${idx}].value`" hide-label class="m-0">
                        <a-input v-model="header.value" placeholder="请输入请求头键值内容" />
                      </a-form-item>
                    </td>
                    <td class="p-2 pl-3">
                      <a-button
                        size="mini"
                        type="text"
                        class="!text-gray-700"
                        @click="form.headers.splice(idx, 1)"
                      >
                        <template #icon>
                          <icon-delete />
                        </template>
                      </a-button>
                    </td>
                  </tr>
                </tbody>
              </table>
              <a-button
                size="mini"
                class="rounded ml-3 mb-3 !text-gray-700"
                @click="form.headers.push({ key: '', value: '' })"
              >
                <template #icon>
                  <icon-plus />
                </template>
                增加参数
              </a-button>
            </div>
          </a-form-item>
          <a-form-item
            field="description"
            label="描述信息"
            asterisk-position="end"
            :rules="[{required: true, message: 'MCP服务描述信息不能为空' }]"
          >
            <a-textarea
              v-model="form.description"
              :auto-size="{ minRows: 4, maxRows: 4 }"
              placeholder="MCP服务器描述信息"
              show-word-limit
              :max-length="1024"
            />
          </a-form-item>
          <!-- 底部按钮 -->
          <div class="flex items-center justify-between">
            <div class="">
              <a-button
                v-if="showUpdateModal"
                class="rounded-lg !text-red-700"
                @click="handleDelete"
              >
                删除
              </a-button>
            </div>
            <a-space :size="16">
              <a-button class="rounded-lg" @click="handleCancel">取消</a-button>
              <a-button
                :loading="updateMcpToolLoading || createMcpToolLoading"
                type="primary"
                html-type="submit"
                class="rounded-lg"
              >
                保存
              </a-button>
            </a-space>
          </div>
        </a-form>
      </div>
    </a-modal>
  </a-spin>
</template>

<style scoped></style>
