<script setup lang="ts">
import {ref} from 'vue'
import {get, post} from '@/utils/request'

let cont = ref('我正在请求一个AI接口')

post('/api/app/completion', {
  body: {
    'query': '您好，你是？'
  }
}).then((r:any) => {
  cont.value = r.data.content
})

</script>

<template>
  <div class="about">
    <h1>This is an about page</h1>
    <div>{{ cont }}</div>
  </div>
</template>

<style>
@media (min-width: 1024px) {
  .about {
    min-height: 100vh;
    display: flex;
    align-items: center;
  }
}
</style>
