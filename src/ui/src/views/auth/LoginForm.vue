<script setup lang="ts">
  import Banner from './components/LoginBanner.vue'
  import LoginForm from './components/LoginForm.vue'
</script>
<template>
  <div class="flex h-screen bg-white" >
    <div class="fixed top-6 left-[22px] inline-flex items-center">
      <div class="bg-gray-100 h-8 leading-8 px-2 z-50">
        LLMOps App Builder
      </div>
    </div>
    <!--左侧Banner-->
    <banner />
    <div class="relative flex flex-1 items-center justify-center pb-10">
      <!--登录表单-->
      <login-form />
      <!--底部banner-->
      <div class="right-0 absolute bottom-0 w-full">
        <footer class="flex items-center justify-center h-10 text-gray-600 text-center">
          LLMOps App Builder
        </footer>
      </div>
    </div>
  </div>
</template>