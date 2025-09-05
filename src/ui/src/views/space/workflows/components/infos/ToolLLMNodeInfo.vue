<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import { apiPrefix, typeMap } from '@/config'
import { cloneDeep } from 'lodash'
import { getReferencedVariables } from '@/utils/helper'
import { Message, type ValidatedError } from '@arco-design/web-vue'
import ModelConfig from './components/ModelConfig.vue'
import { useGetApiTool, useGetApiToolProvidersWithPage } from '@/hooks/use-tool'
import { useGetBuiltinTool, useGetBuiltinTools, useGetCategories } from '@/hooks/use-builtin-tool'
import { useGetMcpToolsWithPage } from '@/hooks/use-mcp-tool'

// 1.定义自定义组件所需数据
const props = defineProps({
  visible: { type: Boolean, required: true, default: false },
  node: { type: Object as any, required: true, default: {} },
  loading: { type: Boolean, required: true, default: false },
})
const emits = defineEmits(['update:visible', 'updateNode'])
const { nodes, edges } = useVueFlow()
const {
  loading: getApiToolProvidersLoading,
  paginator,
  api_tool_providers,
  loadApiToolProviders,
} = useGetApiToolProvidersWithPage()
const { builtin_tool, loadBuiltinTool } = useGetBuiltinTool()
const { api_tool, loadApiTool } = useGetApiTool()
const { builtin_tools, loadBuiltinTools } = useGetBuiltinTools()
const { categories, loadCategories } = useGetCategories()
const { loading: getMcpLoading, mcp_tools, loadMcpTools, paginator: mcpPaginator } = useGetMcpToolsWithPage()
const form = ref<Record<string, any>>({})

const toolInfoModalVisible = ref(false)
const toolInfoNavType = ref('info')
const toolInfo = ref<Record<string, any>>({})
const toolInfoIdx = ref(-1)
const toolInfoSettingForm = ref<Record<string, any>>({})

const toolsModalVisible = ref(false)
const toolsActivateType = ref('mcp_tool')
const toolsActivateCategory = ref('all')
const computedBuiltinTools = computed(() => {
  if (toolsActivateCategory.value === 'all') return builtin_tools.value
  return builtin_tools.value.filter((item: any) => item.category === toolsActivateCategory.value)
})

const defaultToolMeta = {
  type: 'mcp_tool',
  provider: { id: '', name: '', label: '', icon: '', description: '' },
  tool: { id: '', name: '', label: '', description: '', params: {} },
}

// 2.定义节点可引用的变量选项
const inputRefOptions = computed(() => {
  return getReferencedVariables(cloneDeep(nodes.value), cloneDeep(edges.value), props.node.id)
})

// 3.定义添加表单输入字段函数
const addFormInputField = () => {
  form.value?.inputs.push({ name: '', type: 'string', content: null, ref: '' })
  Message.success('新增输入字段成功')
}

// 3.定义移除表单输入字段函数
const removeFormInputField = (idx: number) => {
  form.value?.inputs?.splice(idx, 1)
}

// 4.定义表单提交函数
// todo: 与model-config选择模型交互时有Bug，模型选择后如果直接单击 submit，modelname获取不到
const onSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 4.1 检查表单是否出现错误，如果出现错误则直接结束
  if (errors) return

  // 4.2 深度拷贝表单数据内容
  const cloneInputs = cloneDeep(form.value.inputs) 

  // 4.3 处理tools，工具列表
  const tools: any[] = []
  // @ts-ignore
  form.value.tools.forEach(t => {
    tools.push({
      type: t.type,
      provider_id: t.provider.name,
      tool_id: t.tool.name,
      params: t.tool.params
    })
  })

  // 4.3 数据校验通过，通过事件触发数据更新
  emits('updateNode', {
    id: props.node.id,
    title: form.value.title,
    description: form.value.description,
    prompt: form.value.prompt,
    model_config: form.value.model_config,
    tools: tools,
    inputs: cloneInputs.map((input:any) => {
      return {
        name: input.name,
        description: '',
        required: true,
        type: input.type === 'ref' ? 'string' : input.type,
        value: {
          type: input.type === 'ref' ? 'ref' : 'literal',
          content:
            input.type === 'ref'
              ? {
                  ref_node_id: input.ref.split('/')[0] || '',
                  ref_var_name: input.ref.split('/')[1] || '',
                }
              : input.content,
        },
        meta: {},
      }
    }),
    outputs: cloneDeep(form.value.outputs),
  })
}

// 5.监听数据，将数据映射到表单模型上
watch(
  () => props.node,
  (newNode) => {
    const cloneInputs = cloneDeep(newNode.data.inputs)
    form.value = {
      id: newNode.id,
      type: newNode.type,
      title: newNode.data.title,
      description: newNode.data.description,
      model_config: newNode.data.language_model_config,
      prompt: newNode.data.prompt,
      tools: newNode.data.metas, // 工具列表
      inputs: cloneInputs.map((input:any) => {
        // 5.1 计算引用的变量值信息
        const ref =
          input.value.type === 'ref'
            ? `${input.value.content.ref_node_id}/${input.value.content.ref_var_name}`
            : ''

        // 5.2 判断引用的变量值信息是否存在，如果不存在则设置为空
        let refExists = false
        if (input.value.type === 'ref') {
          for (const inputRefOption of inputRefOptions.value) {
            for (const option of inputRefOption.options) {
              if (option.value === ref) {
                refExists = true
                break
              }
            }
          }
        }
        return {
          name: input.name, // 变量名
          type: input.value.type === 'literal' ? input.type : 'ref', // 数据类型(涵盖ref/string/int/float/boolean
          content: input.value.type === 'literal' ? input.value.content : null, // 变量值内容
          ref: input.value.type === 'ref' && refExists ? ref : '', // 变量引用信息，存储引用节点id+引用变量名
        }
      }),
      outputs: [{ name: 'output', type: 'string', value: { type: 'generated', content: '' } }],
    }
  },
  { immediate: true },
)
onMounted(() => {
  loadCategories()
})

// ----------------------工具绑定相关---------------------------
// 3.定义显示工具列表模态窗
const handleShowToolsModal = async () => {
  // 3.1 显示模态窗
  toolsModalVisible.value = true

  // 3.2 调用API接口获取响应
  await loadApiToolProviders(true)
  await loadBuiltinTools()
  await loadMcpTools(true)
}
// 4.定义移除绑定工具的函数
const removeBindTool = (idx: number) => {
  form.value.tools.splice(idx, 1)
  if (form.value.tools.length == 0) {
    form.value.tools = cloneDeep(defaultToolMeta)
  }
}

// 5.定义是否关联工具判断函数
const isToolSelected = (provider: Record<string, any>, tool: Record<string, any>) => {
  // @ts-ignore
  return form.value.tools.some(t => t.provider?.name === provider.name && t.tool.name === tool.name )
}
//5.1 定义是否关联Mcp工具的判断函数
const isToolSelectedWithMcpTool = (tool: Record<string, any>) => {
  // @ts-ignore
  return form.value.tools.some(t => t.tool.name === tool.name )
}

// 工具选择器
const  handleSelectTool = async (provider_idx: number, tool_idx: number) => {
  // 6.1 根据不同的工具类型执行不同的操作
  let selectTool: any
  if (toolsActivateType.value === 'api_tool') {
    // 6.2 获取api工具提供者+工具本身，并更新selectTool
    const apiToolProvider = api_tool_providers.value[provider_idx]
    const apiTool = apiToolProvider['tools'][tool_idx]
    selectTool = {
      type: 'api_tool',
      provider: {
        id: apiToolProvider.id,
        name: apiToolProvider.name,
        label: apiToolProvider.name,
        icon: apiToolProvider.icon,
        description: apiToolProvider.description,
      },
      tool: {
        id: apiTool.name,
        name: apiTool.name,
        label: apiTool.name,
        description: apiTool.description,
        params: {}
      },
    }
  }
  else if (toolsActivateType.value=== 'mcp_tool') {
    // 6.4 Mcp服务
    const mcp_info = mcp_tools.value[provider_idx]
    selectTool = {
      type: 'mcp_tool',
      provider: {
        id: mcp_info.id,
        name: mcp_info.provider_name,
        label: mcp_info.provider_name,
        icon: mcp_info.icon,
        description: '',
      },
      tool: {
        id: mcp_info.name,
        name: mcp_info.name,
        label: mcp_info.name,
        description: mcp_info.description,
        params: {}
      },
    }

  } else {
    // 6.3 获取内置工具提供者+内置工具，并提取选择工具
    const builtinToolProvider = computedBuiltinTools.value[provider_idx]
    const builtinTool = builtinToolProvider['tools'][tool_idx]
    const params = builtinTool['params']
    selectTool = {
      type: 'builtin_tool',
      provider: {
        id: builtinToolProvider.name,
        name: builtinToolProvider.name,
        label: builtinToolProvider.label,
        icon: `${apiPrefix}/builtin-tools/${builtinToolProvider.name}/icon`,
        description: builtinToolProvider.description,
      },
      tool: {
        id: builtinTool.name,
        name: builtinTool.name,
        label: builtinTool.label,
        description: builtinTool.description,
        params: params.reduce((newObj: any, item: any) => {
          newObj[item.name] = item.default
          return newObj
        }, {})
      },
    }
  }

  // 6.4 检查是新增，还是删除
  // @ts-ignore
  const findToolIdx = form.value.tools.findIndex(t => t.type == selectTool.type && t.provider.id == selectTool.provider.id && t.tool.id == selectTool.tool.id )
  if (findToolIdx >= 0) {
    // 删除
    removeBindTool(findToolIdx)
  } else {
    // 新增数据，调用不同的接口获取相关的参数
    form.value.tools.push(selectTool)
  }
}

// 7.滚动加载api工具列表
const handleScroll = async (event: UIEvent) => {
  // 7.1 获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 7.2 判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (getApiToolProvidersLoading.value) {
      return
    }
    await loadApiToolProviders()
  }
}

// 8.滚动加载Mcp服务列表
const handleScrollWithMcp = async (event: UIEvent) => {
  // 8.1 获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 8.2 判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (getMcpLoading.value) {
      return
    }
    await loadMcpTools()
  }
}

//------------------------工具设置显示模态--------------------

// 2.定义显示工具设置模态窗
const handleShowToolInfoModal = async (idx: number) => {
  // 2.1 获取当前选中的工具
  if (idx === -1) return
  toolInfoIdx.value = idx
  const tool = form.value.tools[idx]

  // 2.2 检测不同的工具类型调用不同API接口
  if (tool.type === 'builtin_tool') {
    await loadBuiltinTool(tool.provider.name, tool.tool.name)
    toolInfo.value = {
      type: 'builtin_tool',
      provider: {
        id: builtin_tool.value.provider.name,
        icon: `${apiPrefix}/builtin-tools/${builtin_tool.value.provider.name}/icon`,
        name: builtin_tool.value.provider.name,
        label: builtin_tool.value.provider.label,
        description: builtin_tool.value.provider.description,
      },
      tool: {
        id: builtin_tool.value.name,
        name: builtin_tool.value.name,
        label: builtin_tool.value.label,
        description: builtin_tool.value.description,
        inputs: builtin_tool.value.inputs,
        params: builtin_tool.value.params,
      },
    }
  } else if (tool.type === 'mcp_tool') {
    // mcp服务
    toolInfo.value = cloneDeep(tool)
    toolInfo.value.tool.inputs = []
    toolInfo.value.tool.params = []
  } else {
    await loadApiTool(tool.provider.id, tool.tool.name)
    toolInfo.value = {
      type: 'api_tool',
      provider: {
        id: api_tool.value.provider.id,
        icon: api_tool.value.provider.icon,
        name: api_tool.value.provider.name,
        label: api_tool.value.provider.name,
        description: api_tool.value.provider.description,
      },
      tool: {
        id: api_tool.value.name,
        name: api_tool.value.name,
        label: api_tool.value.name,
        description: api_tool.value.description,
        inputs: api_tool.value.inputs,
        params: [],
      },
    }
  }

  // 2.3 更新工具设置表单，从草稿中获取配置，如果没有则设置默认值
  const params = tool.tool.params
  toolInfo.value.tool.params.forEach((param: any) => {
    toolInfoSettingForm.value[param.name] = params[param.name] ?? param.default
  })

  // 2.3 显示模态窗
  toolInfoModalVisible.value = true
}

// 3.定义关闭工具设置模态窗
const handleCancelToolInfoModal = () => {
  toolInfoIdx.value = -1
  toolInfoModalVisible.value = false
  toolInfoNavType.value = 'info'
}

// 4.定义提交工具设置模态窗
const handleSubmitToolInfo = async () => {
  // 4.1 获取当前工具信息
  const tool = form.value.tools[toolInfoIdx.value]
  if (tool.type === 'api_tool' || tool.type === 'mcp_tool' ) {
    // 4.2 自定义工具则直接关闭模态窗
    handleCancelToolInfoModal()
    return
  }

  // 4.3 更新草稿配置
  form.value.tools[toolInfoIdx.value].tool.params = toolInfoSettingForm.value

  // 4.5 关闭模态窗
  handleCancelToolInfoModal()
}

</script>

<template>
  <div
    v-if="props.visible"
    id="llm-node-info"
    class="absolute top-0 right-0 bottom-0 w-[400px] border-l z-50 bg-white overflow-scroll scrollbar-w-none p-3"
  >
    <!-- 顶部标题信息 -->
    <div class="flex items-center justify-between gap-3 mb-2">
      <!-- 左侧标题 -->
      <div class="flex items-center gap-1 flex-1">
        <a-avatar :size="30" shape="square" class="bg-sky-500 rounded-lg flex-shrink-0">
          <icon-language />
        </a-avatar>
        <a-input
          v-model:model-value="form.title"
          placeholder="请输入标题"
          class="!bg-white text-gray-700 font-semibold px-2"
        />
      </div>
      <!-- 右侧关闭按钮 -->
      <a-button
        type="text"
        size="mini"
        class="!text-gray700 flex-shrink-0"
        @click="() => emits('update:visible', false)"
      >
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>
    <!-- 描述信息 -->
    <a-textarea
      :auto-size="{ minRows: 3, maxRows: 5 }"
      v-model="form.description"
      class="rounded-lg text-gray-700 !text-xs"
      placeholder="输入描述..."
    />
    <!-- 分隔符 -->
    <a-divider class="my-2" />
    <!-- 表单信息 -->
    <a-form size="mini" :model="form" layout="vertical" @submit="onSubmit">
      <!--模型选择-->
      <div class="flex flex-col gap-2">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div>语言模型配置</div>
            <a-tooltip content="选择不同的大语言模型作为节点的底座模型">
              <icon-question-circle />
            </a-tooltip>
          </div>
          <!--右侧-->
          <model-config v-model:model_config="form.model_config" />
        </div>
      </div>
      <a-divider class="my-4" />
      <!-- 输入参数 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">输入数据</div>
            <a-tooltip
              content="输入给大模型的参数，可在下方提示词中引用。所有输入参数会被转为string输入。"
            >
              <icon-question-circle />
            </a-tooltip>
          </div>
          <!-- 右侧新增字段按钮 -->
          <a-button
            type="text"
            size="mini"
            class="!text-gray-700"
            @click="() => addFormInputField()"
          >
            <template #icon>
              <icon-plus />
            </template>
          </a-button>
        </div>
        <!-- 字段名 -->
        <div class="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <div class="w-[20%]">参数名</div>
          <div class="w-[25%]">类型</div>
          <div class="w-[47%]">值</div>
          <div class="w-[8%]"></div>
        </div>
        <!-- 循环遍历字段列表 -->
        <div v-for="(input, idx) in form?.inputs" :key="idx" class="flex items-center gap-1">
          <div class="w-[20%] flex-shrink-0">
            <a-input v-model="input.name" size="mini" placeholder="请输入参数名" class="!px-2" />
          </div>
          <div class="w-[25%] flex-shrink-0">
            <a-select
              size="mini"
              v-model="input.type"
              class="px-2"
              :options="[
                { label: '引用', value: 'ref' },
                { label: 'STRING', value: 'string' },
                { label: 'INT', value: 'int' },
                { label: 'FLOAT', value: 'float' },
                { label: 'BOOLEAN', value: 'boolean' },
                { label: 'LIST[STRING]', value: 'list[string]' },
                { label: 'LIST[INT]', value: 'list[int]' },
                { label: 'LIST[FLOAT]', value: 'list[float]' },
                { label: 'LIST[BOOLEAN]', value: 'list[boolean]' },
              ]"
            />
          </div>
          <div class="w-[47%] flex-shrink-0 flex items-center gap-1">
            <a-input-tag
              v-if="input.type.startsWith('list')"
              size="mini"
              v-model="input.content"
              :default-value="[]"
              placeholder="请输入参数值，按回车结束"
             />
            <a-input
              v-else-if="input.type !== 'ref'"
              size="mini"
              v-model="input.content"
              placeholder="请输入参数值"
            />
            <a-select
              v-else
              placeholder="请选择引用变量"
              size="mini"
              tag-nowrap
              v-model="input.ref"
              :options="inputRefOptions"
            />
          </div>
          <div class="w-[8%] text-right">
            <icon-minus-circle
              class="text-gray-500 hover:text-gray-700 cursor-pointer flex-shrink-0"
              @click="() => removeFormInputField(idx)"
            />
          </div>
        </div>
        <!-- 空数据状态 -->
        <a-empty v-if="form?.inputs.length <= 0" class="my-4">该节点暂无输入数据</a-empty>
      </div>
      <a-divider class="my-4" />
      <!-- 提示词 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">提示词</div>
            <a-tooltip
              content="作为人类消息传递给大语言模型，可以使用{{参数名}}插入引用/创建的变量。"
            >
              <icon-question-circle />
            </a-tooltip>
          </div>
        </div>
        <!-- 提示词输入框 -->
        <a-form-item field="prompt" hide-label hide-asterisk required>
          <a-textarea
            :auto-size="{ minRows: 5, maxRows: 10 }"
            v-model="form.prompt"
            placeholder="编写大模型的提示词，使大模型实现对应的功能。通过插入{{参数名}}可以引用对应的参数值。"
            class="rounded-lg"
          />
        </a-form-item>
      </div>
      <a-divider class=" my-4" />
      <!--绑定的工具列表-->
      <div class=" flex flex-col gap-2" >
        <div class=" flex items-center justify-between " >
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">绑定工具</div>
            <a-tooltip content="为工具执行节点绑定指定的扩展插件、API插件和MCP插件。">
              <icon-question-circle />
            </a-tooltip>
          </div>
          <!-- 右侧绑定工具按钮 -->
          <a-button type="text" size="mini" class="!text-gray-700" @click="handleShowToolsModal">
            <template #icon>
              <icon-plus />
            </template>
          </a-button>
        </div>
      </div>
      <div class=" flex flex-col gap-1" >
        <div
          class="flex items-center justify-between bg-white p-3 rounded-lg cursor-pointer hover:shadow-sm group border"
          v-for="(tool, idx) in form?.tools"
          :key="idx"
        >
          <!-- 左侧工具信息 -->
          <div class="flex items-center gap-2">
            <!-- 图标 -->
            <a-avatar
              :size="36"
              shape="square"
              class="rounded flex-shrink-0"
              :image-url="tool?.provider?.icon"
            />
            <!-- 名称与描述信息 -->
            <div class="flex flex-col flex-1 gap-1 h-9">
              <div class="text-gray-700 font-bold leading-[18px] line-clamp-1 break-all">
                {{ tool?.provider?.label }}/{{ tool?.tool?.name }}
              </div>
              <div class="text-gray-500 text-xs line-clamp-1 break-all">
                {{ tool?.tool?.description }}
              </div>
            </div>
          </div>
          <div 
            class="hidden group-hover:block flex-shrink-0 ml-2 !text-red-700 rounded">
            <!-- 右侧设置按钮 -->
            <a-button
              @click="handleShowToolInfoModal(idx)"
              size="mini"
              type="text"
            >
              <template #icon>
                <icon-settings />
              </template>
            </a-button>
            <!-- 右侧删除按钮 -->
            <a-button
              size="mini"
              type="text"
              @click="removeBindTool(idx)"
            >
              <template #icon>
                <icon-delete />
              </template>
            </a-button>
          </div>
        </div>
      </div>

      <a-divider class="my-4" />
      <!-- 输出参数 -->
      <div class="flex flex-col gap-2">
        <!-- 输出标题 -->
        <div class="font-semibold text-gray-700">输出数据</div>
        <!-- 字段标题 -->
        <div class="text-gray-500 text-xs">参数名</div>
        <!-- 输出参数列表 -->
        <div v-for="(output, idx) in form?.outputs" :key="idx" class="flex flex-col gap-2">
          <div class="flex items-center gap-2">
            <div class="text-gray-700">{{ output.name }}</div>
            <div class="text-gray-500 bg-gray-200 px-1 py-0.5 rounded">{{ output.type }}</div>
          </div>
        </div>
      </div>
      <a-divider class="my-4" />
      <!-- 保存按钮 -->
      <a-button
        :loading="props.loading"
        type="primary"
        size="small"
        html-type="submit"
        long
        class="rounded-lg"
      >
        保存
      </a-button>
    </a-form>
    <!-- 选择工具模态窗 -->
    <a-modal
      v-model:visible="toolsModalVisible"
      hide-title
      :footer="false"
      class="tool-llms-modal"
      modal-class="right-4 h-[calc(100vh-32px)]"
    >
      <div class="flex w-full h-full">
        <!-- 左侧导航菜单 -->
        <div
          class="flex flex-col flex-shrink-0 bg-gray-50 w-[200px] h-full px-3 py-4 overflow-scroll scrollbar-w-none"
        >
          <!-- 标题 -->
          <div class="text-gray-900 font-bold text-lg mb-4">关联工具</div>
          <!-- 工具类别导航 -->
          <div class="flex flex-col gap-1 mb-4">
            <div
              :class="`rounded-lg h-8 leading-8 px-3 flex items-center gap-2 cursor-pointer hover:bg-white hover:text-blue-700 ${toolsActivateType === 'api_tool' ? 'text-blue-700 bg-white' : 'text-gray-700'}`"
              @click="toolsActivateType = 'api_tool'"
            >
              <icon-code />
              自定义插件
            </div>
            <div
              :class="`rounded-lg h-8 leading-8 px-3 flex items-center gap-2 cursor-pointer hover:bg-white hover:text-blue-700 ${toolsActivateType === 'builtin_tool' ? 'text-blue-700 bg-white' : 'text-gray-700'}`"
              @click="toolsActivateType = 'builtin_tool'"
            >
              <icon-translate />
              内置插件
            </div>
            <div
              :class="`rounded-lg h-8 leading-8 px-3 flex items-center gap-2 cursor-pointer hover:bg-white hover:text-blue-700 ${toolsActivateType === 'mcp_tool' ? 'text-blue-700 bg-white' : 'text-gray-700'}`"
              @click="toolsActivateType = 'mcp_tool'"
            >
              <icon-translate />
              MCP服务
            </div>
          </div>
          <!-- 内置工具分类 -->
          <div v-if="toolsActivateType === 'builtin_tool'" class="">
            <!-- 分类标题 -->
            <div class="text-xs text-gray-500 mb-3">类别</div>
            <!-- 分类列表 -->
            <div class="flex flex-col gap-1">
              <!-- 所有类别 -->
              <div
                :class="`rounded-lg h-8 leading-8 px-3 flex items-center gap-2 cursor-pointer hover:bg-white hover:text-blue-700 ${toolsActivateCategory === 'all' ? 'text-blue-700 bg-white' : 'text-gray-700'}`"
                @click="toolsActivateCategory = 'all'"
              >
                <icon-apps />
                全部
              </div>
              <div
                v-for="category in categories"
                :key="category.name"
                :class="`rounded-lg h-8 leading-8 px-3 flex items-center gap-2 cursor-pointer hover:bg-white hover:text-blue-700 ${toolsActivateCategory === category.category ? 'text-blue-700 bg-white' : ' text-gray-700'}`"
                @click="toolsActivateCategory = category.category"
              >
                <span v-html="category.icon"></span>
                {{ category.name }}
              </div>
            </div>
          </div>
        </div>
        <!-- 右侧工具列表 -->
        <div class="flex-1 p-4">
          <!-- 标题与关闭按钮 -->
          <div class="w-full flex items-center justify-between gap-2 mb-7">
            <div class="text-lg font-bold text-gray-700">
              {{ toolsActivateType === 'api_tool' ? '自定义插件' : ( toolsActivateType === 'mcp_tool' ? 'MCP服务' : '内置插件') }}
            </div>
            <a-button
              size="mini"
              type="text"
              class="!text-gray-700 ml-6"
              @click="() => (toolsModalVisible = false)"
            >
              <template #icon>
                <icon-close />
              </template>
            </a-button>
          </div>
          <!-- 内置工具列表 -->
          <div
            v-if="toolsActivateType === 'builtin_tool'"
            class="h-[calc(100vh-130px)] overflow-scroll scrollbar-w-none"
          >
            <div
              v-for="(builtin_tool, builtin_tool_idx) in computedBuiltinTools"
              :key="builtin_tool.name"
              class="flex flex-col gap-3 mb-3"
            >
              <!-- 提供者信息 -->
              <div class="text-gray-900">{{ builtin_tool.label }}</div>
              <!-- 工具列表 -->
              <div class="flex flex-col gap-1">
                <div
                  v-for="(tool, tool_idx) in builtin_tool.tools"
                  :key="tool.name"
                  :class="`flex items-center justify-between px-2 h-8 rounded-lg cursor-pointer hover:bg-gray-50 group ${isToolSelected(builtin_tool, tool) ? 'bg-blue-50 border border-blue-700' : ''}`"
                >
                  <!-- 工具信息 -->
                  <div class="flex items-center gap-2">
                    <a-avatar
                      :size="20"
                      shape="circle"
                      :image-url="`${apiPrefix}/builtin-tools/${builtin_tool.name}/icon`"
                    />
                    <div class="text-gray-900">{{ tool.label }}</div>
                  </div>
                  <!-- 添加按钮 -->
                  <a-button
                    size="mini"
                    class="hidden group-hover:block rounded px-1.5 flex-shrink-0"
                    @click="() => handleSelectTool(builtin_tool_idx, tool_idx)"
                  >
                    <template #icon>
                      <icon-plus />
                    </template>
                    {{ isToolSelected(builtin_tool, tool) ? '删除' : '添加' }}
                  </a-button>
                </div>
              </div>
            </div>
            <div v-if="computedBuiltinTools.length === 0" class="">
              <a-empty
                description="没有可用的内置插件"
                class="h-[400px] flex flex-col items-center justify-center"
              />
            </div>
          </div>
          <!-- 自定义插件列表 -->
          <div v-if="toolsActivateType === 'api_tool'">
            <a-spin
              :loading="getApiToolProvidersLoading"
              class="block h-[calc(100vh-130px)] overflow-scroll scrollbar-w-none"
              @scroll="handleScroll"
            >
              <div
                v-for="(api_tool_provider, api_tool_provider_idx) in api_tool_providers"
                :key="api_tool_provider.id"
                class="flex flex-col gap-3 mb-3"
              >
                <!-- 提供者信息 -->
                <div class="text-gray-900">{{ api_tool_provider.name }}</div>
                <!-- 工具列表 -->
                <div class="flex flex-col gap-1">
                  <div
                    v-for="(tool, tool_idx) in api_tool_provider.tools"
                    :key="tool.name"
                    :class="`flex items-center justify-between px-2 h-8 rounded-lg cursor-pointer hover:bg-gray-50 group ${isToolSelected(api_tool_provider, tool) ? 'bg-blue-50 border border-blue-700' : ''}`"
                  >
                    <!-- 工具信息 -->
                    <div class="flex items-center gap-2">
                      <a-avatar :size="20" shape="circle" :image-url="api_tool_provider.icon" />
                      <div class="text-gray-900">{{ tool.name }}</div>
                    </div>
                    <!-- 添加按钮 -->
                    <a-button
                      size="mini"
                      class="hidden group-hover:block rounded px-1.5 flex-shrink-0"
                      @click="() => handleSelectTool(Number(api_tool_provider_idx), tool_idx)"
                    >
                      <template #icon>
                        <icon-plus />
                      </template>
                      {{ isToolSelected(api_tool_provider, tool) ? '删除' : '添加' }}
                    </a-button>
                  </div>
                </div>
              </div>
              <div v-if="api_tool_providers.length === 0" class="">
                <a-empty
                  description="没有可用的API插件"
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
          <!-- Mcp服务列表 -->
          <div v-if="toolsActivateType === 'mcp_tool'" >
            <a-spin
              :loading="getMcpLoading"
              class="block h-[calc(100vh-130px)] overflow-scroll scrollbar-w-none"
              @scroll="handleScrollWithMcp"
            >
              <div
                v-for="(mcp_tool, mcp_tool_idx) in mcp_tools"
                :key="mcp_tool.id"
                class="flex flex-col gap-3 mb-3"
              >
                <!-- 提供者信息 -->
                <div class="text-gray-900">{{ mcp_tool.provider_name }}</div>
                <!-- 工具列表 -->
                <div class="flex flex-col gap-1">
                  <div
                    :class="`flex items-center justify-between px-2 h-8 rounded-lg cursor-pointer hover:bg-gray-50 group ${isToolSelectedWithMcpTool(mcp_tool) ? 'bg-blue-50 border border-blue-700' : ''}`"
                  >
                    <!-- 工具信息 -->
                    <div class="flex items-center gap-2">
                      <a-avatar :size="20" shape="circle" :image-url="mcp_tool.icon" />
                      <div class="text-gray-900">{{ mcp_tool.name }}</div>
                    </div>
                    <!-- 添加按钮 -->
                    <a-button
                      size="mini"
                      class="hidden group-hover:block rounded px-1.5 flex-shrink-0"
                      @click="() => handleSelectTool(Number(mcp_tool_idx), Number(mcp_tool_idx))"
                    >
                      <template #icon>
                        <icon-plus />
                      </template>
                      {{ isToolSelectedWithMcpTool(mcp_tool) ? '删除' : '添加' }}
                    </a-button>
                  </div>
                </div>
              </div>
              <div v-if="mcp_tools.length === 0" class="">
                <a-empty
                  description="没有可用的MCP服务"
                  class="h-[400px] flex flex-col items-center justify-center"
                />
              </div>
              <!-- 加载器 -->
              <a-row v-if="mcpPaginator.total_page >= 2">
                <!-- 加载数据中 -->
                <a-col
                  v-if="mcpPaginator.current_page <= mcpPaginator.total_page"
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
        </div>
      </div>
    </a-modal>
    <!-- 工具设置模态窗 -->
    <a-modal
      :visible="toolInfoModalVisible"
      hide-title
      :footer="false"
      class="tool-setting-modal"
      modal-class="h-[calc(100vh-32px)] right-4"
      @cancel="handleCancelToolInfoModal"
    >
      <!-- 顶部标题&关闭按钮 -->
      <div class="flex items-center justify-between mb-6">
        <!-- 左侧标题&导航 -->
        <div class="flex items-center">
          <!-- 工具信息 -->
          <div class="flex items-center gap-2">
            <a-avatar :size="24" shape="circle" :image-url="toolInfo?.provider?.icon" />
            <div class="text-gray-700 font-bold max-w-[200px] line-clamp-1 break-all">
              {{ toolInfo?.tool?.label }}
            </div>
          </div>
          <!-- 分隔符 -->
          <div class="mx-4 text-gray-400">
            <icon-oblique-line :size="12" />
          </div>
          <!-- 导航菜单 -->
          <div class="flex items-center gap-6">
            <div
              :class="`text-gray-700 pt-1 cursor-pointer border-blue-700 hover:border-b-4 hover:font-bold transition-all ${toolInfoNavType === 'info' ? 'font-bold border-b-4' : ''}`"
              @click="toolInfoNavType = 'info'"
            >
              信息
            </div>
            <div
              v-if="toolInfo.type === 'builtin_tool' && toolInfo?.tool?.params?.length > 0"
              :class="`text-gray-700 pt-1 cursor-pointer border-blue-700 hover:border-b-4 hover:font-bold transition-all ${toolInfoNavType === 'setting' ? 'font-bold border-b-4' : ''}`"
              @click="toolInfoNavType = 'setting'"
            >
              设置
            </div>
          </div>
        </div>
        <!-- 右侧关闭按钮 -->
        <a-button size="mini" type="text" class="!text-gray-700" @click="handleCancelToolInfoModal">
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 信息容器 -->
      <div
        v-if="toolInfoNavType === 'info'"
        class="h-[calc(100vh-170px)] pb-4 overflow-scroll scrollbar-w-none"
      >
        <!-- 工具描述 -->
        <div class="text-gray-70 font-bold mb-1">工具描述</div>
        <div class="text-gray-500 text-xs">{{ toolInfo?.tool?.description }}</div>
        <!-- 工具参数 -->
        <div v-if="toolInfo?.tool?.inputs?.length > 0" class="">
          <!-- 分隔符 -->
          <div class="flex items-center gap-2 my-4">
            <div class="text-xs font-bold text-gray-500">参数</div>
            <hr class="flex-1" />
          </div>
          <!-- 参数列表 -->
          <div class="flex flex-col gap-4">
            <div
              v-for="input in toolInfo?.tool?.inputs"
              :key="input.name"
              class="flex flex-col gap-2"
            >
              <!-- 上半部分 -->
              <div class="flex items-center gap-2 text-xs">
                <div class="text-gray-900 font-bold">{{ input.name }}</div>
                <div class="text-gray-500">{{ typeMap[input.type] }}</div>
                <div v-if="input.required" class="text-red-700">必填</div>
              </div>
              <!-- 参数描述信息 -->
              <div class="text-xs text-gray-500">{{ input.description }}</div>
            </div>
          </div>
        </div>
      </div>
      <!-- 设置容器 -->
      <div
        v-if="toolInfoNavType === 'setting'"
        class="h-[calc(100vh-170px)] pb-4 overflow-scroll scrollbar-w-none"
      >
        <a-form v-model:model="toolInfoSettingForm" layout="vertical" class="">
          <a-form-item
            v-for="param in toolInfo?.tool?.params"
            :key="param.name"
            :field="param.name"
          >
            <template #label>
              <div class="flex items-center gap-1">
                <div class="text-gray-700">{{ param.label }}</div>
                <div v-if="param.required" class="text-red-700">*</div>
                <a-tooltip :content="param.label">
                  <icon-info-circle />
                </a-tooltip>
              </div>
            </template>
            <a-select
              v-if="param.type === 'select'"
              :default-value="param.default"
              v-model:model-value="toolInfoSettingForm[param.name]"
              placeholder="请输入参数值"
              :options="param.options"
            />
            <a-input
              v-if="param.type === 'string'"
              placeholder="请输入参数值"
              v-model:model-value="toolInfoSettingForm[param.name]"
              :default-value="param.default"
            />
            <a-input-number
              v-if="param.type === 'number'"
              placeholder="请输入参数值"
              v-model:model-value="toolInfoSettingForm[param.name]"
              :default-value="param.default"
              :min="param.min"
              :max="param.max"
            />
            <a-radio-group
              v-if="param.type === 'boolean'"
              v-model:model-value="toolInfoSettingForm[param.name]"
              :default-value="param.default"
            >
              <a-radio :value="true">开启</a-radio>
              <a-radio :value="false">关闭</a-radio>
            </a-radio-group>
          </a-form-item>
        </a-form>
      </div>
      <!-- 底部按钮 -->
      <div class="flex items-center justify-between">
        <div class=""></div>
        <a-space :size="12">
          <a-button class="rounded-lg" @click="handleCancelToolInfoModal">取消</a-button>
          <a-button
            type="primary"
            class="rounded-lg"
            @click="handleSubmitToolInfo"
          >
            保存
          </a-button>
        </a-space>
      </div>
    </a-modal>
  </div>
</template>

<style>
.tool-setting-modal {
  .arco-modal-wrapper {
    text-align: right;
  }
}

.tool-llms-modal {
  .arco-modal-wrapper {
    text-align: right;
  }

  .arco-modal-body {
    padding: 0;
    height: 100%;
    width: 100%;
    border-radius: 8px;
  }
}
</style>
