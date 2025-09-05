import {ref} from 'vue'
import { generateSuggestedQuesions, optimizePrompt, generateSuggestedQuesionsWithExLink } from '@/services/ai'

export const useGenerateSuggestedQuesions = () => {
  const loading = ref(false)
  const suggested_questions = ref<string[]>([])

  const handleGenerateSUggestedQuesions = async (message_id:string, end_user_id: string = '') => {
    try {
      loading.value = true
      const resp = await (end_user_id ? generateSuggestedQuesionsWithExLink(end_user_id, message_id) : generateSuggestedQuesions(message_id))
      suggested_questions.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return {loading, suggested_questions, handleGenerateSUggestedQuesions}
}

export const useOptimizePrompt = () => {
  const loading = ref(false)
  const optimize_prompt = ref('')

  const handleOptimizePrompt = async (prompt: string) => {
    try {
      loading.value = true
      optimize_prompt.value = ''
      await optimizePrompt(prompt, (event_response) => {
        const data = event_response.data
        optimize_prompt.value += data?.optimize_prompt
      })

    } finally {
      loading.value = false
    }
  }

  return {loading, optimize_prompt, handleOptimizePrompt}
}