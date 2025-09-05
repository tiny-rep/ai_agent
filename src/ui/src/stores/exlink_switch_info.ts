import { ref } from "vue"
import { defineStore } from 'pinia'


const initExlinkSwitchInfo = {
  question: '',
  conversationId: ''
}

export const useExlinkSwitchInfoStore = defineStore('exlinkswitch', () => {
  const exlinkSwitchInfo = ref(initExlinkSwitchInfo)

  const update = (params: any) => {
    exlinkSwitchInfo.value = params
  }

  const clear = () => {
    exlinkSwitchInfo.value = initExlinkSwitchInfo
  }

  return {exlinkSwitchInfo, update, clear}
})