<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useCredentialStore } from '@/stores/credential'
import { useAuthorize } from '@/hooks/use-oauth'

//定义数据
const route = useRoute()
const router = useRouter()
const {update: updateCredential} = useCredentialStore()
const { authorization, handleAuthorize } = useAuthorize()

onMounted( async () => {
  try {
    await handleAuthorize(String(route.params?.provider_name), String(route.query?.code ?? ''))
    Message.success('登录成功，正在跳转')

    updateCredential(authorization.value)
    await router.replace({path: '/home'})
  } catch {
    await router.replace({path: '/auth/login'})
  }
})

</script>

<template>
  <div class="w-full min-h-screen flex items-center justify-center bg-white">
    <a-spin tip="第三方授权登录中..."></a-spin>
  </div>
</template>

