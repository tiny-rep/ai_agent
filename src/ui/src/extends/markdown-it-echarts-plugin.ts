import MarkdownIt from 'markdown-it'
/**
 * markdown-it 增加echarts能力
 * @param md 
 */
export const echartsPlugin = (md: MarkdownIt) => {
  const defaultRender = md.renderer.rules.fence!

  md.renderer.rules.fence = (tokens, idx, options, env, self) => {
    const token = tokens[idx]
    const lang = token.info.trim()

    if (lang === 'echarts') {
      const rawContent = token.content
        .replace(/'/g, '"')
        .replace(/(\w+):/g, '"$1":')
        .replace(/,\s*([}\]])/g, '$1')

      const chartId = `echart-${Math.random().toString(36).slice(2, 11)}`
      const safeContent = encodeURIComponent(rawContent)

      return `
        <div id="${chartId}" 
             class="echarts-container" 
             data-option="${safeContent}"
             data-render="${Date.now()}"
             style="width:auto;height:600px;margin:20px 0">
          <div class="flex justify-center items-center h-full chart-loading">图表加载中...</div>
        </div>
      `
    }
    return defaultRender(tokens, idx, options, env, self)
  }
}