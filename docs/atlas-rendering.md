# 天眼能力图尺寸更新

观察图表容器的 border-box，扣除边框后向下取整，避免 clientWidth / clientHeight 随滚动条显示而变化、以及小数像素上取整引起反馈。只在实际布局尺寸发生变化时更新状态，使用 requestAnimationFrame 合并事件，卸载时取消观察和待执行更新。旧浏览器退回 offsetWidth / offsetHeight，仍不依赖滚动视口尺寸。文字测量画布复用。

tests/atlas_resize.mjs 使用真实 Chrome 隔离页面模拟滚动条视口抖动：尺寸抖动不应修改 SVG，而真正的容器缩放、图表缩放和模型选点仍应生效。可通过 CHROME_PATH 指定浏览器。浏览器验收另覆盖桌面、平板、手机及全屏；数据更新节奏仍为每分钟尝试更新。
