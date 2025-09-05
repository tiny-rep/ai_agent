import { type BasePaginatorResponse, type BaseResponse } from '@/models/base'

export type GetMcpToolsWithPageResponse = BasePaginatorResponse<{
  id: string
  name: string
  icon: string
  description: string
  provider_name: string
  params:any
  transport_type: string
  created_at: number,
  updated_at: number,
  mcp_params_obj: any
}>

export type CreateMcpToolRequest = {
  name: string
  icon: string
  description: string
  provider_name: string
  transport_type: string
  mcp_params: string
}

export type UpdateMcpToolRequest = {
  name: string
  icon: string
  description: string
  provider_name: string
  transport_type: string
  mcp_params: string
}

export type GetMcpToolResponse = BaseResponse<{
  id: string
  name: string
  icon: string
  description: string
  provider_name: string
  transport_type: string
  params: any
  created_at: number
  updated_at: number
}>