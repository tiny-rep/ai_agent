<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useExlinkSwitchInfoStore } from '@/stores/exlink_switch_info'


const router = useRouter()
const route = useRoute()
const { update:updateExlinkSwitchInfo } = useExlinkSwitchInfoStore()

const onRecvMessage = (event:MessageEvent<any>) => {
  const data = JSON.parse(event.data)
  if (data.app_token) {
    router.replace({
      name: 'ex-link-inner-web-app-index',
      params: {
        end_user_id: route.params.end_user_id,
        ex_link_token: data.app_token
      }
    })
    updateExlinkSwitchInfo({question: data.question, conversationId: data.conversationId})
  }
}

onMounted(() => {
  window.addEventListener("message", onRecvMessage, false)
  window.parent.postMessage({loaded: true}, "*")
})

onBeforeUnmount(() => {
  console.log('unmount')
  window.removeEventListener('message', onRecvMessage)
})

</script>

<template>
  <router-view />
</template>
