import { getBuiltinTool, GetBuiltinTools, getCategories } from '@/services/builtin-tool'
import { ref } from 'vue'


//获取分类
export const useGetCategories = () => {
  const loading = ref(false)
  const categories = ref<Record<string,any>[]>([])

  const loadCategories = async () => {
    try {
      loading.value = true
      const resp = await getCategories()
      const data = resp.data

      categories.value = data

    } finally {
      loading.value = false
    }
  }

  return {loading, categories, loadCategories}
}

// 获取内置工具
export const useGetBuiltinTool = () => {
  const loading = ref(false)
  const builtin_tool = ref<Record<string,any>>({})

  const loadBuiltinTool = async (provider_name: string, tool_name: string) => {
    try {
      loading.value = true
      const resp = await getBuiltinTool(provider_name, tool_name)
      const data = resp.data

      builtin_tool.value = data
    } finally {
      loading.value = false
    }
  }

  return {loading, builtin_tool, loadBuiltinTool}
}

// 获取内置工具列表
export const useGetBuiltinTools = () => {
  const loading = ref(false)
  const builtin_tools = ref<Record<string,any>[]>([])

  const loadBuiltinTools = async () => {
    try {
      loading.value = true
      const resp = await GetBuiltinTools()
      const data = resp.data

      builtin_tools.value = data
    } finally {
      loading.value = false
    }
  }

  return {loading, builtin_tools, loadBuiltinTools}
}