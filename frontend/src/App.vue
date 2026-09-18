<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount, defineAsyncComponent } from 'vue'
import { Sparkles, Plus, MessageSquare, ArrowUp, LogOut, Package, ShieldCheck, ChartNoAxesCombined, ArrowUpRight, Menu, X, LoaderCircle, ChevronRight } from '@lucide/vue'
const Chart = defineAsyncComponent(() => import('./Chart.vue'))
import { json, stream } from './api'
const user = ref(null), mode = ref('demo'), sessions = ref([]), active = ref(null), messages = ref([])
const input = ref(''), busy = ref(false), error = ref(''), step = ref(''), panel = ref(null), mobileMenu = ref(false)
const username = ref('demo'), password = ref('Demo123!'), loginBusy = ref(false)
const prompts = [
  { icon: Package, title: '每一笔订单，都有答案', text: '查询订单与物流状态', query: '查询我的订单' },
  { icon: ShieldCheck, title: '售后问题，轻松解决', text: '了解退换货与退款政策', query: '七天无理由退货需要满足什么条件？' },
  { icon: ChartNoAxesCombined, title: '让数据，讲清楚故事', text: '用图表查看订单统计', query: '按分类统计销售额并画柱状图' }
]
const columns = rows => rows?.length ? Object.keys(rows[0]) : []
const labels = { order_no: '订单编号', product: '商品', category: '分类', amount: '金额', status: '状态', created_at: '下单时间', label: '类别 / 日期', value: '金额', count: '订单数', total_amount: '订单总额', order_count: '订单数' }
const greeting = computed(() => user.value?.role === 'admin' ? '让每一笔订单，都清晰可见。' : '你的订单，我们一起看。')
let controller
async function scroll() { await nextTick(); if (panel.value) panel.value.scrollTop = panel.value.scrollHeight }
async function refresh() { sessions.value = await json('/conversations') }
async function login() {
  error.value = ''; loginBusy.value = true
  try {
    const data = await json('/auth/login', { method: 'POST', body: JSON.stringify({ username: username.value, password: password.value }) })
    sessionStorage.setItem('orderly-token', data.access_token); user.value = data.user; await refresh()
  } catch (e) { error.value = e.message } finally { loginBusy.value = false }
}
function logout() { controller?.abort(); sessionStorage.removeItem('orderly-token'); user.value = null; active.value = null; messages.value = []; sessions.value = []; busy.value = false }
function fresh() { if (busy.value) return; active.value = null; messages.value = []; error.value = ''; mobileMenu.value = false }
async function selectSession(session) {
  if (busy.value) return
  error.value = ''
  try { const data = await json(`/conversations/${session.id}/messages`); active.value = session.id; messages.value = data; mobileMenu.value = false; scroll() } catch (e) { error.value = e.message }
}
async function send(value = input.value) {
  const text = value.trim(); if (!text || busy.value) return
  error.value = ''; busy.value = true; input.value = ''; controller = new AbortController()
  try {
    if (!active.value) { const session = await json('/conversations', { method: 'POST' }); active.value = session.id; await refresh() }
    messages.value.push({ role: 'user', content: text })
    const index = messages.value.push({ role: 'assistant', content: '', rows: [], sources: [], chart: null }) - 1
    step.value = '正在理解你的问题'; scroll()
    await stream(`/conversations/${active.value}/chat`, text, (event, data) => {
      const item = messages.value[index]
      if (event === 'token') item.content += data.text
      if (event === 'data') { item.rows = data.rows; item.sql = data.sql }
      if (event === 'sources') item.sources = data.sources
      if (event === 'chart') item.chart = data.chart
      if (event === 'status') step.value = { start: '正在理解你的问题', route: '已识别问题，正在处理', order: '订单查询完成', policy: '已检索售后政策', chart: '图表已生成', answer: '回答完成' }[data.node] || '正在处理'
      if (event === 'error') { item.failed = true; throw new Error(data.text) }
      scroll()
    }, controller.signal)
  } catch (e) { if (e.name !== 'AbortError') error.value = e.message } finally { busy.value = false; step.value = ''; if (user.value) await refresh().catch(() => {}) }
}
function expire() { logout(); error.value = '登录已失效，请重新登录' }
onMounted(async () => {
  window.addEventListener('auth-expired', expire)
  try { mode.value = (await json('/health')).mode; if (mode.value !== 'demo') { username.value = ''; password.value = '' } } catch { error.value = '无法连接服务，请确认后端已启动' }
  if (sessionStorage.getItem('orderly-token')) { try { user.value = await json('/auth/me'); await refresh() } catch { logout() } }
})
onBeforeUnmount(() => { controller?.abort(); window.removeEventListener('auth-expired', expire) })
</script>
<template>
  <div v-if="!user" class="login-page">
    <section class="login-brand"><a class="brand"><span class="brand-symbol"><Sparkles :size="20" /></span>orderly<span class="brand-dot">.</span></a><div class="brand-copy"><p class="eyebrow">A LITTLE CLARITY, EVERY DAY</p><h1>订单的每个问题，<br>都有温柔的解答。</h1><p>查询订单、了解售后、看懂数据。<br>让服务回归简单，让每一次沟通更有用。</p><div class="login-decoration"><Package :size="42" :stroke-width="1"/><div><span>订单 · 售后 · 数据</span><strong>一个对话，就够了。</strong></div><Sparkles :size="25"/></div></div><small>ORDERLY / 智能订单客服助手</small></section>
    <section class="login-form-wrap"><form class="login-form" @submit.prevent="login"><div class="mini-mark"><Sparkles :size="24"/></div><p class="eyebrow">WELCOME BACK</p><h2>欢迎回来</h2><p class="muted">登录，开始你的订单对话。</p><label>用户名<input v-model="username" autocomplete="username" required placeholder="请输入用户名" /></label><label>密码<input v-model="password" type="password" autocomplete="current-password" required placeholder="请输入密码" /></label><p v-if="error" role="alert" class="error">{{ error }}</p><button class="primary login-button" :disabled="loginBusy">{{ loginBusy ? '正在登录…' : '开始使用' }}<ArrowUpRight :size="18"/></button><div v-if="mode === 'demo'" class="demo-note"><span class="dot"></span><div><strong>当前为演示模式</strong><p>客户：demo / Demo123!<br>管理员：admin / Admin123!</p></div></div><small class="login-foot">你的订单数据，仅对有权限的用户可见。</small></form></section>
  </div>
  <div v-else class="app-shell">
    <button v-if="mobileMenu" class="overlay" aria-label="关闭菜单" @click="mobileMenu = false"></button>
    <aside :class="['sidebar', { open: mobileMenu }]"><a class="brand" @click="fresh"><span class="brand-symbol"><Sparkles :size="20" /></span>orderly<span class="brand-dot">.</span></a><p class="sidebar-caption">你的专属订单助手</p><button class="new-chat" :disabled="busy" @click="fresh"><Plus :size="18"/>开启新对话</button><div class="history-heading">最近的对话<span>{{ sessions.length }}</span></div><nav class="history-list"><button v-for="session in sessions" :key="session.id" :class="{ selected: active === session.id }" :disabled="busy" @click="selectSession(session)"><MessageSquare :size="15"/><span>{{ session.title }}</span></button><p v-if="!sessions.length" class="empty-history">你的对话会保存在这里</p></nav><div class="sidebar-tip"><div class="tip-icon"><ShieldCheck :size="19"/></div><strong>每次对话，都安心</strong><p>{{ user.role === 'admin' ? '管理员可查看所有订单统计。' : '订单查询仅限你的个人数据。' }}<br>售后回答提供政策来源。</p></div><div class="user-panel"><span class="avatar">{{ user.username.slice(0, 1).toUpperCase() }}</span><div><strong>{{ user.username }}</strong><small>{{ user.role === 'admin' ? '管理员' : '客户账户' }}</small></div><button title="退出登录" aria-label="退出登录" @click="logout"><LogOut :size="17"/></button></div></aside>
    <main class="workspace"><header class="topbar"><div><button class="mobile-toggle" aria-label="打开菜单" @click="mobileMenu = !mobileMenu"><Menu :size="20"/></button><span>工作空间</span><ChevronRight :size="14"/><strong>订单客服</strong></div><span class="mode-pill"><span class="dot"></span>{{ mode === 'demo' ? '演示模式' : '智能服务已连接' }}</span></header>
      <section ref="panel" class="conversation-scroll">
        <div v-if="!messages.length" class="welcome"><p class="welcome-overline"><span></span>为每一次购买，多一份安心</p><h1>{{ greeting }}</h1><p class="welcome-description">从一声你好，到每一个答案。<br>查询订单、解决售后，或发现数据里的新视角。</p><div class="prompt-grid"><button v-for="prompt in prompts" :key="prompt.title" class="prompt-card" @click="send(prompt.query)"><span class="prompt-icon"><component :is="prompt.icon" :size="23" :stroke-width="1.6"/></span><h3>{{ prompt.title }}</h3><p>{{ prompt.text }}</p><ArrowUpRight class="prompt-arrow" :size="18"/></button></div><div class="workflow-preview"><span>一个问题，协作完成</span><div><span>理解意图</span><i>→</i><span>匹配服务</span><i>→</i><span>查找答案</span><i>→</i><span>清晰呈现</span></div></div></div>
        <div v-else class="message-list"><article v-for="(message, i) in messages" :key="i" :class="['message', message.role]"><span v-if="message.role === 'assistant'" class="assistant-avatar"><Sparkles :size="18"/></span><div class="message-body"><p v-if="message.role === 'assistant'" class="message-name">Orderly <span>智能订单助手</span></p><p class="message-text">{{ message.content }}<span v-if="busy && i === messages.length - 1" class="typing-cursor"></span></p><div v-if="message.rows?.length" class="data-card"><div class="data-head"><Package :size="16"/><strong>查询结果</strong><span>{{ message.rows.length }} 条</span></div><div class="table-scroll"><table><thead><tr><th v-for="key in columns(message.rows)" :key="key">{{ labels[key] || key }}</th></tr></thead><tbody><tr v-for="(row, n) in message.rows" :key="n"><td v-for="key in columns(message.rows)" :key="key"><span :class="{ 'status-label': key === 'status' }">{{ row[key] }}</span></td></tr></tbody></table></div><details v-if="message.sql"><summary>查看查询语句</summary><pre>{{ message.sql }}</pre></details></div><Chart v-if="message.chart?.series?.length" :option="message.chart"/><div v-if="message.sources?.length" class="source-list"><ShieldCheck :size="14"/><span>政策来源</span><span v-for="source in [...new Set(message.sources.map(s => s.source))]" :key="source" class="source-tag">{{ source }}</span></div></div></article><p v-if="busy" class="progress-line"><LoaderCircle :size="14" class="spin"/>{{ step }}</p></div>
      </section>
      <footer class="composer-wrap"><div v-if="error" role="alert" class="error composer-error">{{ error }}<button aria-label="关闭错误提示" @click="error = ''"><X :size="14"/></button></div><form class="composer" @submit.prevent="send()"><textarea v-model="input" aria-label="输入你的问题" placeholder="聊聊你的订单，或试试“帮我画一张销售趋势图”…" rows="1" maxlength="2000" :disabled="busy" @keydown.enter.exact.prevent="send()"></textarea><button class="send-button" :disabled="busy || !input.trim()" aria-label="发送消息"><LoaderCircle v-if="busy" :size="20" class="spin"/><ArrowUp v-else :size="21"/></button></form><div class="composer-meta"><span><ShieldCheck :size="12"/>权限隔离 · 政策可追溯</span><span>Enter 发送 · Shift + Enter 换行</span></div><p class="disclaimer">{{ mode === 'demo' ? '当前数据和售后政策仅用于演示。' : '回答由 AI 生成，请结合订单详情核实。' }} 实际售后办理请联系人工客服。</p></footer>
    </main>
  </div>
</template>
