<script setup lang="ts">
import { ref } from 'vue'
import {  useRoute } from 'vue-router'

const route = useRoute()
const tipMessage = ref<string>(`应用跳转中[${route.params.end_user_id}]......`)

</script>

<template>
  <div class="w-full min-h-screen flex items-center justify-center bg-white text-center">
    <a-spin>
      <template #tip>
        {{ tipMessage }}
      </template>
    </a-spin>
  </div>
</template>
