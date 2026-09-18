<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])
const props = defineProps({ option: Object })
const host = ref(null)
const kind = ref('original')
let chart, observer
function render() {
  if (!chart || !props.option?.series?.length) return
  const option = JSON.parse(JSON.stringify(props.option))
  if (kind.value === 'pie' && option.xAxis) {
    const first = option.series[0]
    const labels = option.xAxis.data
    delete option.xAxis; delete option.yAxis; delete option.grid
    option.tooltip = { trigger: 'item' }
    option.series = [{ name: first.name, type: 'pie', radius: ['40%', '70%'], data: labels.map((name, i) => ({ name, value: first.data[i] })) }]
  } else if (['bar', 'line'].includes(kind.value)) {
    if (!option.xAxis) {
      const data = option.series[0].data
      option.xAxis = { type: 'category', data: data.map(d => d.name) }; option.yAxis = { type: 'value' }
      option.series = [{ name: option.series[0].name, data: data.map(d => d.value) }]
    }
    option.series.forEach(s => { s.type = kind.value; s.smooth = kind.value === 'line' })
    option.tooltip = { trigger: 'axis' }
  }
  option.color = ['#23876a', '#d3a461', '#7899a8', '#b88180']
  chart.setOption(option, true)
}
onMounted(() => { chart = echarts.init(host.value); observer = new ResizeObserver(() => chart.resize()); observer.observe(host.value); render() })
watch(() => props.option, render, { deep: true }); watch(kind, render)
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>
<template><section class="chart-card"><div class="chart-head"><strong>订单数据视图</strong><select v-model="kind" aria-label="图表类型"><option value="original">原始图表</option><option value="bar">柱状图</option><option value="line">折线图</option><option value="pie">饼图</option></select></div><div ref="host" class="chart-host"></div></section></template>
