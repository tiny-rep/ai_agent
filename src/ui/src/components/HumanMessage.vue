<script setup lang="ts">
const props = defineProps({
  account: {type:Object, default: {}, required: true},
  query: {type: String, default: '', required: true},
  image_urls: {type: Array, default: () => []}
})
</script>

<template>
  <div class="flex gap-2">
    <a-avatar :size="30" shape="circle" class=" flex-shrink-0" :image-url="props.account.avatat" />
    <div class="flex flex-col items-start gap-2">
      <div class="text-gray-700 font-bold">{{ props.account?.name }}</div>
      <div class="bg-blue-100 border border-blue-200 text-gray-700 px-4 py-3 rounded-2xl break-all">
        <a-image v-for="(image_url, idx) in props.image_urls" :key="idx" :src="String(image_url)" />
        {{ props.query }}
      </div>
    </div>
  </div>
</template>