<script setup lang="ts">
/**
 * HomePage.vue - 主页内容（标签页切换）
 *
 * 接收 App.vue 传入的 currentTab，渲染对应组件。
 */
import { ref } from 'vue'
import ChatLearning from '../components/ChatLearning.vue'
import PersonalizedLearning from '../components/PersonalizedLearning.vue'
import ResourceGenerator from '../components/ResourceGenerator.vue'
import EvaluationCenter from '../components/EvaluationCenter.vue'
import VoiceLearning from '../components/VoiceLearning.vue'

const props = defineProps<{
  currentTab: string
}>()

const ragQuery = ref('Python for循环')
const ragResults = ref('')
const loading = ref(false)
const error = ref('')

async function ingestRag() {
  error.value = ''
  loading.value = true
  try {
    const res = await fetch('/api/rag/ingest?sync=true', { method: 'POST' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    ragResults.value = JSON.stringify(await res.json(), null, 2)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '入库失败'
  } finally {
    loading.value = false
  }
}

async function queryRag() {
  error.value = ''
  loading.value = true
  try {
    const res = await fetch('/api/rag/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: ragQuery.value, top_k: 4 }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    ragResults.value = JSON.stringify(await res.json(), null, 2)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '检索失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <transition name="page" mode="out-in">
    <div :key="props.currentTab" class="max-w-5xl mx-auto">
      <ChatLearning v-if="props.currentTab === 'chat'" />
      <PersonalizedLearning v-else-if="props.currentTab === 'profile'" />
      <ResourceGenerator v-else-if="props.currentTab === 'resource'" />
      <EvaluationCenter v-else-if="props.currentTab === 'evaluation'" />
      <VoiceLearning v-else-if="props.currentTab === 'voice'" />

      <div v-else-if="props.currentTab === 'rag'" class="space-y-5">
        <div class="flex items-center gap-3 mb-2">
          <span class="text-2xl">📚</span>
          <div>
            <h2 class="text-xl font-bold text-surface-800">RAG 知识库</h2>
            <p class="text-sm text-surface-400">知识检索增强生成，提升AI回答准确度</p>
          </div>
        </div>

        <div class="rounded-2xl border border-surface-200 bg-white p-5 space-y-4">
          <div class="space-y-2">
            <label class="text-xs font-semibold uppercase tracking-wider text-surface-400">检索问题</label>
            <input
              v-model="ragQuery"
              class="w-full rounded-xl border border-surface-200 bg-surface-50 px-4 py-2.5 text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-400/20 focus:outline-none transition-all"
              placeholder="输入检索问题..."
            />
          </div>

          <div class="flex gap-2.5">
            <button
              type="button"
              class="rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50 transition-all shadow-sm shadow-emerald-500/20"
              :disabled="loading"
              @click="ingestRag"
            >
              入库 knowledge/
            </button>
            <button
              type="button"
              class="rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 transition-all shadow-sm shadow-brand-500/20"
              :disabled="loading"
              @click="queryRag"
            >
              检索
            </button>
          </div>

          <pre
            v-if="ragResults"
            class="overflow-x-auto rounded-xl border border-surface-200 bg-surface-50 p-4 text-xs text-brand-700"
          >{{ ragResults }}</pre>
        </div>
      </div>

      <p v-if="error" class="text-sm text-rose-500 bg-rose-50 rounded-xl px-4 py-3 border border-rose-200">{{ error }}</p>
    </div>
  </transition>
</template>

<style scoped>
.page-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.page-leave-active {
  transition: all 0.2s ease-in;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
