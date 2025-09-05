import {get} from '@/utils/request'

import { type GetCategoriesResp, type GetBuiltinToolsResp, type GetBuiltinToolResponse } from '@/models/builtin-tool'

//获取内置工具分类
export const getCategories = () => {
  return get<GetCategoriesResp>("/builtin-tools/categories")
}

//获取内置工具所有提供者列表
export const GetBuiltinTools = () => {
  return get<GetBuiltinToolsResp>("/builtin-tools")
}

// 获取内置工具详情
export const getBuiltinTool = (provider_name: string, tool_name: string) => {
  return get<GetBuiltinToolResponse>(`/builtin-tools/${provider_name}/tools/${tool_name}`)
}
