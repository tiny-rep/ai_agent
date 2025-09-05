import { ref } from "vue"
import { CreateMcpTool, DeleteMcpTool, GetMcpTool, GetMcpToolsWithPage, UpdateMcpTool } from "@/services/mcp-tool"
import type { CreateMcpToolRequest, GetMcpToolsWithPageResponse, UpdateMcpToolRequest } from "@/models/mcp-tool"
import { Message, Modal } from "@arco-design/web-vue"

// 获取Mcp Tool列表（分页）
export const useGetMcpToolsWithPage = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const mcp_tools = ref<GetMcpToolsWithPageResponse['data']['list']>([])
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref(defaultPaginator)

  // 2.定义加载数据函数
  const loadMcpTools = async (init: boolean = false, search_word: string = '') => {
    if (init) {
      paginator.value = defaultPaginator
      Object.assign(paginator, {...defaultPaginator})
    } else if (paginator.value.current_page > paginator.value.total_page) {
      return
    }

    try {
      loading.value = true
      const resp = await GetMcpToolsWithPage(
        paginator.value.current_page,
        paginator.value.page_size,
        search_word
      )
      const data = resp.data

      paginator.value =data.paginator

      if (paginator.value.current_page <= paginator.value.total_page) {
        paginator.value.current_page += 1
      }
      const list = data.list
      if (init) {
        mcp_tools.value = list
      } else {
        mcp_tools.value.push(...list)
      }

    } finally {
      loading.value = false
    }
  }

  return {loading, mcp_tools, paginator, loadMcpTools}
}

// 获取Mcp工具详细信息
export const useGetMcpTool = () => {
  const loading = ref(false)
  const mcp_tool = ref<Record<string, any>>({})

  const loadMcpTool = async (mcp_tool_id: string) => {
    try {
      loading.value = true
      const resp = await GetMcpTool(mcp_tool_id)
      mcp_tool.value = resp.data
    } finally {
      loading.value = false
    }
  }
  return {loading, mcp_tool, loadMcpTool}
}

// 添加Mcp工具
export const useCreateMcpTool = () => {
  const loading = ref(false)

  const handleCreateMcpTool = async (req: CreateMcpToolRequest) => {
    try {
      loading.value = true
      const resp = await CreateMcpTool(req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }
  return {loading, handleCreateMcpTool}
}

//修改Mcp工具
export const useUpdateMcpTool = () => {
  const loading = ref(false)

  const handleUpdateMcpTool = async (mcp_tool_id: string, req: UpdateMcpToolRequest) => {
    try {
      loading.value = true
      const resp = await UpdateMcpTool(mcp_tool_id, req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }
  return {loading, handleUpdateMcpTool}
}

// 删除Mcp工具
export const useDeleteMcpTool = () => {

  const handleDeleteMcpTool = (mcp_tool_id: string, success_cb: () => void) => {
    Modal.warning({
      title: "删除这个MCP服务？",
      content: "删除MCP服务是不可逆的。AI应用将无法再访问您的MCP服务",
      hideCancel: false,
      onOk: async () => {
        try {
          const resp = await DeleteMcpTool(mcp_tool_id)
          Message.success(resp.data)
        } finally {
          success_cb && success_cb()
        }
      }
    })
  }
  return {handleDeleteMcpTool}
}