import { get, post } from '@/utils/request'
import { type BaseResponse } from '@/models/base'
import { type GetMcpToolResponse, type CreateMcpToolRequest, type GetMcpToolsWithPageResponse, type UpdateMcpToolRequest } from '@/models/mcp-tool'

// 获取自定义API列表分页数据
export const GetMcpToolsWithPage = (
  current_page: number = 1,
  page_size: number = 20,
  search_word: string = '',
) => {
  return get<GetMcpToolsWithPageResponse>('/mcp-tools', {
    params: { current_page, page_size, search_word },
  })
}

export const CreateMcpTool = (req: CreateMcpToolRequest) => {
  return post<BaseResponse<any>>('/mcp-tools', {
    body: req
  })
}

export const UpdateMcpTool = (mcp_tool_id: string, req: UpdateMcpToolRequest) => {
  return post<BaseResponse<any>>(`/mcp-tools/${mcp_tool_id}`, {
    body: req
  })
}

export const DeleteMcpTool = (mcp_tool_id: string) => {
  return post<BaseResponse<any>>(`/mcp-tools/${mcp_tool_id}/delete`)
}

export const GetMcpTool = (mcp_tool_id: string) => {
  return get<GetMcpToolResponse>(`/mcp-tools/${mcp_tool_id}`)
}