const pptxgen = require("pptxgenjs");
const path = require("path");

let pres = new pptxgen();
pres.author = "智岗罗盘团队";
pres.title = "智岗罗盘 — 智能岗位技能图谱与就业演化分析系统";

// ============================================================
// SLIDE DIMENSIONS
// ============================================================
pres.layout = 'LAYOUT_16x9';
const SLIDE_W = 10;
const SLIDE_H = 5.625;

const MARGIN = 0.5;
const CONTENT_X = MARGIN;
const CONTENT_Y = MARGIN;
const CONTENT_W = SLIDE_W - (2 * MARGIN);
const CONTENT_H = SLIDE_H - (2 * MARGIN);

const CENTER_X = SLIDE_W / 2;
const CENTER_Y = SLIDE_H / 2;

// ============================================================
// COLOR PALETTE — Ocean Gradient
// ============================================================
const COLORS = {
  deepBlue: '065A82',
  teal: '1C7293',
  midnight: '21295C',
  darkNavy: '0A1628',
  darkBg: '0F172A',
  cardBg: '1E293B',
  cyan: '06B6D4',
  cyanLight: '22D3EE',
  white: 'FFFFFF',
  offWhite: 'E2E8F0',
  muted: '94A3B8',
  accent: '38BDF8',
};

const IMG_DIR = path.join(__dirname, 'images');

// Shape type constants (pptxgenjs v3 uses string names)
const SHAPES = {
  RECTANGLE: 'rect',
  OVAL: 'ellipse',
  ROUNDED_RECTANGLE: 'roundRect',
  LINE: 'line',
};

const CHARTS = {
  BAR: 'bar',
  COLUMN: 'column',
  LINE: 'line',
  PIE: 'pie',
  DOUGHNUT: 'doughnut',
};

// ============================================================
// CONTAINER SYSTEM
// ============================================================
function calculateScaledImageOpts(opts) {
  const { path: imgPath, w: targetW, h: targetH, x = 0, y = 0, mode = 'cover', ...rest } = opts;
  if (!imgPath || !targetW || !targetH) return opts;
  return {
    path: imgPath,
    x,
    y,
    w: targetW,
    h: targetH,
    sizing: { type: mode, w: targetW, h: targetH },
    ...rest
  };
}

function createVirtualNode(type, data, parentX = 0, parentY = 0) {
  const opts = data.opts || {};
  const node = {
    type, data,
    absX: parentX + (opts.x || 0),
    absY: parentY + (opts.y || 0),
    w: opts.w || 0, h: opts.h || 0,
    children: []
  };
  node.addShape = function(shapeType, opts = {}) {
    const child = createVirtualNode('shape', { shapeType, opts }, node.absX, node.absY);
    node.children.push(child);
    return child;
  };
  node.addText = function(text, opts = {}) {
    const safeOpts = { fit: "shrink", ...opts };
    const bulletRe = /^(?:[\u2022\u2023\u25E6\u2043\u2219\u00B7\u25CF\u25CB\u2013\u2014]\s*|\-\s+)/;
    if (Array.isArray(text)) {
      text = text.map(item => {
        if (item && item.options && item.options.bullet && typeof item.text === 'string') {
          return { ...item, text: item.text.replace(bulletRe, '') };
        }
        return item;
      });
    }
    const child = createVirtualNode('text', { text, opts: safeOpts }, node.absX, node.absY);
    node.children.push(child);
    return child;
  };
  node.addImage = function(opts = {}) {
    const scaledOpts = calculateScaledImageOpts(opts);
    const child = createVirtualNode('image', { opts: scaledOpts }, node.absX, node.absY);
    node.children.push(child);
    return child;
  };
  node.addTable = function(tableData, opts = {}) {
    const child = createVirtualNode('table', { tableData, opts }, node.absX, node.absY);
    node.children.push(child);
    return child;
  };
  return node;
}

function flattenNode(node, realSlide, pres) {
  const absOpts = { ...node.data.opts, x: node.absX, y: node.absY };
  if (node.type === 'shape') realSlide.addShape(node.data.shapeType, absOpts);
  else if (node.type === 'text') realSlide.addText(node.data.text, absOpts);
  else if (node.type === 'image') realSlide.addImage(absOpts);
  else if (node.type === 'table') realSlide.addTable(node.data.tableData, absOpts);
  node.children.forEach(child => flattenNode(child, realSlide, pres));
}

const originalAddSlide = pres.addSlide.bind(pres);
pres.addSlide = function(options) {
  const realSlide = originalAddSlide(options);
  const virtualSlide = {
    children: [],
    _realSlide: realSlide,
    set background(val) { realSlide.background = val; },
    get background() { return realSlide.background; },
    addShape: function(shapeType, opts = {}) {
      const node = createVirtualNode('shape', { shapeType, opts }, 0, 0);
      this.children.push(node);
      return node;
    },
    addText: function(text, opts = {}) {
      const safeOpts = { fit: "shrink", ...opts };
      const node = createVirtualNode('text', { text, opts: safeOpts }, 0, 0);
      this.children.push(node);
      return node;
    },
    addImage: function(opts = {}) {
      const scaledOpts = calculateScaledImageOpts(opts);
      const node = createVirtualNode('image', { opts: scaledOpts }, 0, 0);
      this.children.push(node);
      return node;
    },
    addTable: function(tableData, opts = {}) {
      const node = createVirtualNode('table', { tableData, opts }, 0, 0);
      this.children.push(node);
      return node;
    },
    addChart: function(chartType, data, opts = {}) {
      realSlide.addChart(chartType, data, opts);
    },
    render: function() {
      this.children.forEach(child => flattenNode(child, realSlide, pres));
    }
  };
  return virtualSlide;
};

// ============================================================
// HELPER FUNCTIONS
// ============================================================

function addDarkBg(slide) {
  slide.addShape(SHAPES.RECTANGLE, {
    x: 0, y: 0, w: SLIDE_W, h: SLIDE_H,
    fill: { color: COLORS.darkBg }
  });
}

function addSlideTitle(slide, title, subtitle) {
  // Accent dot before title
  slide.addShape(SHAPES.OVAL, {
    x: CONTENT_X, y: CONTENT_Y + 0.08, w: 0.15, h: 0.15,
    fill: { color: COLORS.cyan }
  });
  slide.addText(title, {
    x: CONTENT_X + 0.3, y: CONTENT_Y,
    w: CONTENT_W - 0.3, h: 0.5,
    fontSize: 28, bold: true, color: COLORS.white,
    fontFace: 'Georgia', charSpacing: 1.5,
    valign: 'middle'
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x: CONTENT_X + 0.3, y: CONTENT_Y + 0.5,
      w: CONTENT_W - 0.3, h: 0.3,
      fontSize: 13, color: COLORS.muted,
      fontFace: 'Calibri'
    });
  }
}

function addGlowCircle(slide, x, y, size, color) {
  slide.addShape(SHAPES.OVAL, {
    x: x - size/2, y: y - size/2, w: size, h: size,
    fill: { color: color, transparency: 85 },
    line: { color: color, transparency: 60, width: 1 }
  });
}

// ============================================================
// SLIDE 1: COVER
// ============================================================
{
  let slide = pres.addSlide();
  slide.background = { color: COLORS.darkBg };

  // Background image
  slide.addImage({
    path: path.join(IMG_DIR, 'bg-cover.jpg'),
    x: 0, y: 0, w: SLIDE_W, h: SLIDE_H,
    mode: 'cover'
  });

  // Dark overlay gradient
  slide.addShape(SHAPES.RECTANGLE, {
    x: 0, y: 0, w: SLIDE_W, h: SLIDE_H,
    fill: { color: '0A1628', transparency: 40 }
  });

  // Glowing accent circle
  addGlowCircle(slide, CENTER_X, CENTER_Y - 0.5, 3, COLORS.cyan);

  // Title
  slide.addText("智岗罗盘", {
    x: 0, y: CENTER_Y - 1.0, w: SLIDE_W, h: 1.0,
    fontSize: 48, bold: true, color: COLORS.white,
    fontFace: 'Georgia', charSpacing: 4,
    align: 'center', valign: 'middle'
  });

  // Subtitle
  slide.addText("智能岗位技能图谱与就业演化分析系统", {
    x: 0, y: CENTER_Y + 0.1, w: SLIDE_W, h: 0.6,
    fontSize: 22, color: COLORS.cyanLight,
    fontFace: 'Georgia', charSpacing: 2,
    align: 'center', valign: 'middle'
  });

  // Divider line
  slide.addShape(SHAPES.RECTANGLE, {
    x: CENTER_X - 1, y: CENTER_Y + 0.75, w: 2, h: 0.04,
    fill: { color: COLORS.cyan, transparency: 30 }
  });

  // Bottom info
  slide.addText("终期答辩 · 2026", {
    x: 0, y: SLIDE_H - 0.9, w: SLIDE_W, h: 0.4,
    fontSize: 14, color: COLORS.muted,
    align: 'center'
  });

  slide.render();
}

// ============================================================
// SLIDE 2: TABLE OF CONTENTS
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);

  slide.addText("目录", {
    x: 0, y: CONTENT_Y + 0.3, w: SLIDE_W, h: 0.6,
    fontSize: 32, bold: true, color: COLORS.white,
    fontFace: 'Georgia', charSpacing: 2,
    align: 'center'
  });

  const sections = [
    { num: '01', title: '项目背景与痛点', desc: '就业市场的信息不对称挑战' },
    { num: '02', title: '解决方案概览', desc: '知识图谱驱动的智能分析平台' },
    { num: '03', title: '核心技术架构', desc: '多源采集 · LLM 抽取 · 图谱构建' },
    { num: '04', title: '智能匹配引擎', desc: '语义增强 + Bradley-Terry 调优' },
    { num: '05', title: '准确率验证', desc: '三项核心指标全面达标' },
    { num: '06', title: '产品与性能', desc: '全栈功能与性能优化成果' },
    { num: '07', title: '总结与展望', desc: '项目成果与未来规划' },
  ];

  const cols = 4;
  const cardW = (CONTENT_W - 0.6) / cols;
  const cardH = 1.6;
  const startY = CONTENT_Y + 1.2;
  const gapX = 0.2;
  const gapY = 0.2;

  sections.forEach((sec, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = CONTENT_X + col * (cardW + gapX);
    const y = startY + row * (cardH + gapY);

    // Card background
    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x, y, w: cardW, h: cardH,
      fill: { color: COLORS.cardBg },
      line: { color: COLORS.teal, transparency: 50, width: 1 },
      rectRadius: 0.08
    });

    // Number
    slide.addText(sec.num, {
      x: x + 0.2, y: y + 0.15, w: cardW - 0.4, h: 0.4,
      fontSize: 22, bold: true, color: COLORS.cyan,
      fontFace: 'Georgia'
    });

    // Title
    slide.addText(sec.title, {
      x: x + 0.2, y: y + 0.55, w: cardW - 0.4, h: 0.4,
      fontSize: 15, bold: true, color: COLORS.white,
      fontFace: 'Calibri'
    });

    // Description
    slide.addText(sec.desc, {
      x: x + 0.2, y: y + 0.95, w: cardW - 0.4, h: 0.5,
      fontSize: 11, color: COLORS.muted,
      fontFace: 'Calibri'
    });
  });

  slide.render();
}

// ============================================================
// SLIDE 3: 项目背景与痛点
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "项目背景与痛点", "就业市场的信息不对称与技能错配挑战");

  // Left: pain points
  const leftX = CONTENT_X;
  const leftW = 4.5;
  const topY = CONTENT_Y + 1.0;

  const painPoints = [
    { icon: '①', title: '信息不对称', desc: '求职者难以全面了解岗位真实技能需求，企业招聘效率低下' },
    { icon: '②', title: '技能错配', desc: '高校培养与市场需求脱节，毕业生技能与岗位要求存在差距' },
    { icon: '③', title: '演化难追踪', desc: '技术迭代加速，技能需求快速变化，缺乏实时演化洞察工具' },
    { icon: '④', title: '决策缺依据', desc: '职业规划、课程设置、人才培养缺乏数据驱动的决策支持' },
  ];

  painPoints.forEach((p, i) => {
    const y = topY + i * 0.85;
    // Accent bar
    slide.addShape(SHAPES.RECTANGLE, {
      x: leftX, y: y + 0.05, w: 0.06, h: 0.55,
      fill: { color: COLORS.cyan }
    });
    // Icon number
    slide.addText(p.icon, {
      x: leftX + 0.2, y, w: 0.5, h: 0.65,
      fontSize: 20, bold: true, color: COLORS.cyan,
      fontFace: 'Georgia', valign: 'middle'
    });
    // Title
    slide.addText(p.title, {
      x: leftX + 0.75, y, w: leftW - 0.75, h: 0.3,
      fontSize: 15, bold: true, color: COLORS.white,
      fontFace: 'Calibri'
    });
    // Description
    slide.addText(p.desc, {
      x: leftX + 0.75, y: y + 0.3, w: leftW - 0.75, h: 0.4,
      fontSize: 12, color: COLORS.muted,
      fontFace: 'Calibri'
    });
  });

  // Right: hero image
  const imgX = CONTENT_X + 5.2;
  const imgY = CONTENT_Y + 0.9;
  const imgW = 3.8;
  const imgH = 3.5;

  slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
    x: imgX, y: imgY, w: imgW, h: imgH,
    fill: { color: COLORS.cardBg },
    line: { color: COLORS.teal, transparency: 50, width: 1 },
    rectRadius: 0.1
  });

  slide.addImage({
    path: path.join(IMG_DIR, 'hero-data-visualization.jpg'),
    x: imgX + 0.15, y: imgY + 0.15, w: imgW - 0.3, h: imgH - 0.3,
    mode: 'cover'
  });

  // Caption below image
  slide.addText("数据驱动的就业市场洞察", {
    x: imgX, y: imgY + imgH + 0.1, w: imgW, h: 0.3,
    fontSize: 11, color: COLORS.muted,
    align: 'center', italic: true
  });

  slide.render();
}

// ============================================================
// SLIDE 4: 解决方案概览（3 卡片）
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "解决方案概览", "知识图谱 + LLM + 智能匹配的三位一体架构");

  const cards = [
    {
      img: 'card-data-collection.jpg',
      title: '多源数据采集',
      desc: '覆盖主流招聘平台与在线课程平台，实时采集岗位与课程数据，构建全面的技能生态数据源'
    },
    {
      img: 'card-skill-extraction.jpg',
      title: 'LLM 智能抽取',
      desc: '基于大语言模型的技能抽取与归一化引擎，精准识别岗位与简历中的技能实体与层级关系'
    },
    {
      img: 'card-resume-match.jpg',
      title: '智能匹配推荐',
      desc: '语义增强匹配引擎结合 Bradley-Terry 权重调优，实现高精度的人岗匹配与学习路径推荐'
    }
  ];

  const cardW = (CONTENT_W - 0.4) / 3;
  const cardH = 3.8;
  const startY = CONTENT_Y + 1.0;

  cards.forEach((card, i) => {
    const x = CONTENT_X + i * (cardW + 0.2);

    // Card bg
    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x, y: startY, w: cardW, h: cardH,
      fill: { color: COLORS.cardBg },
      line: { color: COLORS.teal, transparency: 60, width: 1 },
      rectRadius: 0.1
    });

    // Card image (top ~50%)
    const imgH = cardH * 0.48;
    slide.addImage({
      path: path.join(IMG_DIR, card.img),
      x: x + 0.1, y: startY + 0.1, w: cardW - 0.2, h: imgH - 0.1,
      mode: 'cover'
    });

    // Title
    slide.addText(card.title, {
      x: x + 0.25, y: startY + imgH + 0.1, w: cardW - 0.5, h: 0.4,
      fontSize: 17, bold: true, color: COLORS.white,
      fontFace: 'Calibri'
    });

    // Accent line under title
    slide.addShape(SHAPES.RECTANGLE, {
      x: x + 0.25, y: startY + imgH + 0.5, w: 0.5, h: 0.04,
      fill: { color: COLORS.cyan }
    });

    // Description
    slide.addText(card.desc, {
      x: x + 0.25, y: startY + imgH + 0.65, w: cardW - 0.5, h: cardH - imgH - 0.85,
      fontSize: 12, color: COLORS.muted,
      fontFace: 'Calibri', valign: 'top'
    });
  });

  slide.render();
}

// ============================================================
// SLIDE 5: 系统整体架构
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "系统整体架构", "六层架构设计，端到端智能化处理链路");

  const layers = [
    { name: '展示层', items: 'React · ECharts · Force Graph · 响应式 UI', color: COLORS.cyan },
    { name: '网关层', items: 'FastAPI · JWT 认证 · 限流 · CORS · API 路由', color: COLORS.teal },
    { name: '服务层', items: '图谱服务 · 匹配引擎 · 演化分析 · 简历管理', color: COLORS.deepBlue },
    { name: '算法层', items: 'LLM 抽取 · 技能归一化 · 语义匹配 · BT 调优', color: COLORS.midnight },
    { name: '数据层', items: 'Neo4j 图谱 · PostgreSQL · Redis 缓存 · RAG 向量', color: '1E3A5F' },
    { name: '采集层', items: 'Scrapy 爬虫 · 多平台适配 · 代理池 · 调度系统', color: '0F2A44' },
  ];

  const archX = CONTENT_X + 0.5;
  const archW = CONTENT_W - 1.0;
  const archTop = CONTENT_Y + 0.95;
  const layerH = 0.5;
  const layerGap = 0.05;

  layers.forEach((layer, i) => {
    const y = archTop + i * (layerH + layerGap);

    // Layer bar
    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x: archX, y, w: archW, h: layerH,
      fill: { color: layer.color },
      line: { color: COLORS.cyan, transparency: 60, width: 0.5 },
      rectRadius: 0.06
    });

    // Layer name (left)
    slide.addText(layer.name, {
      x: archX + 0.3, y, w: 1.2, h: layerH,
      fontSize: 13, bold: true, color: COLORS.white,
      fontFace: 'Calibri', valign: 'middle'
    });

    // Layer items (right)
    slide.addText(layer.items, {
      x: archX + 1.8, y, w: archW - 2.1, h: layerH,
      fontSize: 11, color: COLORS.offWhite,
      fontFace: 'Calibri', valign: 'middle'
    });
  });

  // Insight box
  const insightY = archTop + layers.length * (layerH + layerGap) + 0.15;
  slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
    x: CONTENT_X, y: insightY, w: CONTENT_W, h: 0.5,
    fill: { color: '1E293B', transparency: 20 },
    line: { color: COLORS.cyan, transparency: 50, width: 0.5 },
    rectRadius: 0.06
  });

  slide.addText("💡 架构亮点：", {
    x: CONTENT_X + 0.3, y: insightY, w: 1.5, h: 0.5,
    fontSize: 12, bold: true, color: COLORS.cyan,
    fontFace: 'Calibri', valign: 'middle'
  });

  slide.addText("采集-存储-计算-服务全链路解耦，算法层独立迭代，支撑图谱 5000+ 节点、10 万+ 关系的实时查询", {
    x: CONTENT_X + 1.8, y: insightY, w: CONTENT_W - 2.1, h: 0.5,
    fontSize: 11, color: COLORS.offWhite,
    fontFace: 'Calibri', valign: 'middle'
  });

  slide.render();
}

// ============================================================
// SLIDE 6: 多源数据采集
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "多源数据采集", "覆盖招聘与课程两大维度，构建完整技能生态");

  // Left side: data sources
  const leftX = CONTENT_X;
  const leftW = 5.0;
  const topY = CONTENT_Y + 0.9;

  const sources = [
    { cat: '招聘平台', items: ['BOSS 直聘', '前程无忧', '智联招聘', '拉勾网'], color: COLORS.cyan },
    { cat: '课程平台', items: ['中国大学 MOOC', 'Coursera', '网易云课堂'], color: COLORS.teal },
  ];

  let curY = topY;
  sources.forEach((src, si) => {
    // Category label
    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x: leftX, y: curY, w: 1.2, h: 0.32,
      fill: { color: src.color },
      rectRadius: 0.04
    });
    slide.addText(src.cat, {
      x: leftX, y: curY, w: 1.2, h: 0.32,
      fontSize: 11, bold: true, color: COLORS.white,
      align: 'center', valign: 'middle'
    });

    // Items as pills
    src.items.forEach((item, ii) => {
      const pillX = leftX + 1.35 + ii * 0.88;
      slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
        x: pillX, y: curY + 0.02, w: 0.82, h: 0.28,
        fill: { color: COLORS.cardBg },
        line: { color: src.color, transparency: 40, width: 0.5 },
        rectRadius: 0.14
      });
      slide.addText(item, {
        x: pillX, y: curY + 0.02, w: 0.82, h: 0.28,
        fontSize: 9, color: COLORS.offWhite,
        align: 'center', valign: 'middle'
      });
    });

    curY += 0.55;
  });

  // Pipeline flow
  const flowY = curY + 0.25;
  const flowSteps = [
    { label: '调度触发', icon: '⏰' },
    { label: '代理池', icon: '🔄' },
    { label: '数据抓取', icon: '🕷️' },
    { label: '清洗去重', icon: '🧹' },
    { label: '入图入库', icon: '📦' },
  ];

  slide.addText("采集流水线", {
    x: leftX, y: flowY - 0.05, w: 2, h: 0.28,
    fontSize: 12, bold: true, color: COLORS.white,
    fontFace: 'Calibri'
  });

  const stepW = 0.82;
  const stepGap = 0.1;
  const flowStartX = leftX;
  const flowStepY = flowY + 0.3;

  flowSteps.forEach((step, i) => {
    const sx = flowStartX + i * (stepW + stepGap);
    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x: sx, y: flowStepY, w: stepW, h: 0.72,
      fill: { color: COLORS.cardBg },
      line: { color: COLORS.cyan, transparency: 50, width: 0.5 },
      rectRadius: 0.06
    });
    slide.addText(step.icon, {
      x: sx, y: flowStepY + 0.05, w: stepW, h: 0.32,
      fontSize: 15, align: 'center'
    });
    slide.addText(step.label, {
      x: sx, y: flowStepY + 0.38, w: stepW, h: 0.3,
      fontSize: 9, color: COLORS.offWhite,
      align: 'center', valign: 'middle'
    });

    // Arrow between steps
    if (i < flowSteps.length - 1) {
      slide.addShape(SHAPES.LINE, {
        x: sx + stepW + 0.01, y: flowStepY + 0.36, w: stepGap, h: 0,
        line: { color: COLORS.cyan, width: 1.5, endArrowType: 'triangle' }
      });
    }
  });

  // Right: stats
  const rightX = CONTENT_X + 5.8;
  const rightW = 3.2;

  slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
    x: rightX, y: CONTENT_Y + 0.9, w: rightW, h: 3.8,
    fill: { color: COLORS.cardBg },
    line: { color: COLORS.teal, transparency: 50, width: 1 },
    rectRadius: 0.1
  });

  slide.addText("数据规模", {
    x: rightX, y: CONTENT_Y + 1.1, w: rightW, h: 0.38,
    fontSize: 15, bold: true, color: COLORS.white,
    fontFace: 'Calibri', align: 'center'
  });

  const stats = [
    { num: '5,000+', label: '岗位节点' },
    { num: '800+', label: '技能实体' },
    { num: '10万+', label: '图谱关系' },
    { num: '3,000+', label: '课程数据' },
  ];

  stats.forEach((stat, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const sx = rightX + 0.15 + col * ((rightW - 0.3) / 2 + 0.1);
    const sy = CONTENT_Y + 1.65 + row * 1.25;
    const sw = (rightW - 0.5) / 2;

    slide.addText(stat.num, {
      x: sx, y: sy, w: sw, h: 0.5,
      fontSize: 24, bold: true, color: COLORS.cyan,
      fontFace: 'Georgia', align: 'center', valign: 'middle'
    });
    slide.addText(stat.label, {
      x: sx, y: sy + 0.5, w: sw, h: 0.28,
      fontSize: 10, color: COLORS.muted,
      align: 'center'
    });
  });

  slide.render();
}

// ============================================================
// SLIDE 7: 知识图谱构建
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "知识图谱构建", "多层级技能本体，语义关联的知识网络");

  // Right: image
  const imgX = CONTENT_X + 5.2;
  const imgY = CONTENT_Y + 0.9;
  const imgW = 3.8;
  const imgH = 3.5;

  slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
    x: imgX, y: imgY, w: imgW, h: imgH,
    fill: { color: COLORS.cardBg },
    line: { color: COLORS.teal, transparency: 50, width: 1 },
    rectRadius: 0.1
  });

  slide.addImage({
    path: path.join(IMG_DIR, 'hero-knowledge-graph.jpg'),
    x: imgX + 0.15, y: imgY + 0.15, w: imgW - 0.3, h: imgH - 0.3,
    mode: 'cover'
  });

  // Left: graph schema
  const leftX = CONTENT_X;
  const leftW = 4.8;
  const topY = CONTENT_Y + 1.0;

  // Node types
  slide.addText("图谱 Schema", {
    x: leftX, y: topY, w: leftW, h: 0.35,
    fontSize: 15, bold: true, color: COLORS.white,
    fontFace: 'Calibri'
  });

  const nodeTypes = [
    { type: '岗位 (Position)', desc: '5000+ 节点，含薪资、城市、经验要求等属性', color: COLORS.cyan },
    { type: '技能 (Skill)', desc: '800+ 节点，技术栈/工具/软技能分类体系', color: COLORS.teal },
    { type: '技能组 (SkillGroup)', desc: '领域分类，如前端/后端/数据/设计等', color: COLORS.deepBlue },
    { type: '课程 (Course)', desc: '3000+ 节点，MOOC 平台课程与技能关联', color: '0E7490' },
  ];

  nodeTypes.forEach((nt, i) => {
    const y = topY + 0.4 + i * 0.6;
    // Dot
    slide.addShape(SHAPES.OVAL, {
      x: leftX, y: y + 0.08, w: 0.18, h: 0.18,
      fill: { color: nt.color }
    });
    slide.addText(nt.type, {
      x: leftX + 0.32, y, w: leftW - 0.32, h: 0.26,
      fontSize: 12, bold: true, color: COLORS.white,
      fontFace: 'Calibri'
    });
    slide.addText(nt.desc, {
      x: leftX + 0.32, y: y + 0.26, w: leftW - 0.32, h: 0.3,
      fontSize: 10, color: COLORS.muted,
      fontFace: 'Calibri'
    });
  });

  // Relationships
  const relY = topY + 0.4 + nodeTypes.length * 0.6 + 0.12;
  slide.addText("核心关系", {
    x: leftX, y: relY, w: leftW, h: 0.28,
    fontSize: 12, bold: true, color: COLORS.white,
    fontFace: 'Calibri'
  });

  const rels = ["REQUIRES（岗位-技能）", "BELONGS_TO（技能-技能组）", "TEACHES（课程-技能）", "IS_SIMILAR（技能-技能）"];
  rels.forEach((rel, i) => {
    const col = i % 2;
    const rx = leftX + col * 2.4;
    const ry = relY + 0.32 + Math.floor(i / 2) * 0.28;
    slide.addText("→ " + rel, {
      x: rx, y: ry, w: 2.3, h: 0.26,
      fontSize: 9, color: COLORS.cyanLight,
      fontFace: 'Calibri'
    });
  });

  slide.render();
}

// ============================================================
// SLIDE 8: LLM 智能抽取（2x2 卡片）
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "LLM 智能抽取", "大模型驱动的多维度信息抽取能力");

  const features = [
    { title: 'JD 技能抽取', desc: '从岗位描述中精准识别技术栈、工具、软技能，支持层级化技能分类', icon: '🔧' },
    { title: '简历信息抽取', desc: '结构化提取教育背景、工作经历、项目经验、技能清单等核心字段', icon: '📄' },
    { title: '职位归一化', desc: '同义词归并、别名映射，统一岗位命名标准，消除数据歧义', icon: '🔄' },
    { title: '软技能推断', desc: '从职责描述中推断隐含软技能要求，如沟通协作、领导力、问题解决', icon: '🧠' },
  ];

  const cardW = (CONTENT_W - 0.3) / 2;
  const cardH = 1.75;
  const startY = CONTENT_Y + 1.0;

  features.forEach((f, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = CONTENT_X + col * (cardW + 0.3);
    const y = startY + row * (cardH + 0.2);

    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x, y, w: cardW, h: cardH,
      fill: { color: COLORS.cardBg },
      line: { color: COLORS.teal, transparency: 60, width: 1 },
      rectRadius: 0.08
    });

    // Icon circle
    slide.addShape(SHAPES.OVAL, {
      x: x + 0.25, y: y + 0.25, w: 0.55, h: 0.55,
      fill: { color: COLORS.deepBlue },
      line: { color: COLORS.cyan, width: 1 }
    });
    slide.addText(f.icon, {
      x: x + 0.25, y: y + 0.25, w: 0.55, h: 0.55,
      fontSize: 20, align: 'center', valign: 'middle'
    });

    // Title
    slide.addText(f.title, {
      x: x + 1.0, y: y + 0.25, w: cardW - 1.2, h: 0.55,
      fontSize: 15, bold: true, color: COLORS.white,
      fontFace: 'Calibri', valign: 'middle'
    });

    // Description
    slide.addText(f.desc, {
      x: x + 0.3, y: y + 0.95, w: cardW - 0.6, h: 0.7,
      fontSize: 12, color: COLORS.muted,
      fontFace: 'Calibri', valign: 'top'
    });
  });

  slide.render();
}

// ============================================================
// SLIDE 9: 技能归一化引擎
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "技能归一化引擎", "从异构表述到统一技能体系的映射");

  // Before / After comparison
  const colW = (CONTENT_W - 0.6) / 2;
  const topY = CONTENT_Y + 1.0;
  const colH = 3.5;

  // Before column
  const beforeX = CONTENT_X;
  slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
    x: beforeX, y: topY, w: colW, h: colH,
    fill: { color: '1A2332' },
    line: { color: '475569', width: 1 },
    rectRadius: 0.1
  });

  slide.addText("归一化前", {
    x: beforeX, y: topY + 0.2, w: colW, h: 0.4,
    fontSize: 16, bold: true, color: COLORS.muted,
    fontFace: 'Calibri', align: 'center'
  });

  const beforeItems = [
    'React.js / ReactJS / react',
    'Node.js / NodeJS / Node',
    'Python / PYTHON / python3',
    '机器学习 / ML / Machine Learning',
    '前端开发 / 前端工程师 / FE',
    'Vue.js / Vue / vue3',
  ];

  beforeItems.forEach((item, i) => {
    const y = topY + 0.75 + i * 0.42;
    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x: beforeX + 0.3, y, w: colW - 0.6, h: 0.32,
      fill: { color: COLORS.cardBg },
      line: { color: '475569', transparency: 50, width: 0.5 },
      rectRadius: 0.04
    });
    slide.addText(item, {
      x: beforeX + 0.3, y, w: colW - 0.6, h: 0.32,
      fontSize: 11, color: COLORS.muted,
      align: 'center', valign: 'middle'
    });
  });

  // Arrow in middle
  const arrowX = CONTENT_X + colW + 0.1;
  slide.addText("→", {
    x: arrowX, y: topY + colH / 2 - 0.3, w: 0.4, h: 0.6,
    fontSize: 32, color: COLORS.cyan,
    align: 'center', valign: 'middle', bold: true
  });

  // After column
  const afterX = CONTENT_X + colW + 0.6;
  slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
    x: afterX, y: topY, w: colW, h: colH,
    fill: { color: '0C2D48' },
    line: { color: COLORS.cyan, transparency: 40, width: 1 },
    rectRadius: 0.1
  });

  slide.addText("归一化后", {
    x: afterX, y: topY + 0.2, w: colW, h: 0.4,
    fontSize: 16, bold: true, color: COLORS.cyan,
    fontFace: 'Calibri', align: 'center'
  });

  const afterItems = [
    { name: 'React', cat: '前端框架' },
    { name: 'Node.js', cat: '后端运行时' },
    { name: 'Python', cat: '编程语言' },
    { name: '机器学习', cat: 'AI/数据科学' },
    { name: '前端开发', cat: '岗位方向' },
    { name: 'Vue.js', cat: '前端框架' },
  ];

  afterItems.forEach((item, i) => {
    const y = topY + 0.75 + i * 0.42;
    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x: afterX + 0.3, y, w: colW - 0.6, h: 0.32,
      fill: { color: COLORS.deepBlue },
      line: { color: COLORS.cyan, transparency: 50, width: 0.5 },
      rectRadius: 0.04
    });
    slide.addText(item.name, {
      x: afterX + 0.4, y, w: 1.5, h: 0.32,
      fontSize: 11, bold: true, color: COLORS.white,
      valign: 'middle'
    });
    slide.addText(item.cat, {
      x: afterX + 1.9, y, w: colW - 2.2, h: 0.32,
      fontSize: 10, color: COLORS.cyanLight,
      align: 'right', valign: 'middle'
    });
  });

  // Bottom insight
  const insightY = topY + colH + 0.15;
  slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
    x: CONTENT_X, y: insightY, w: CONTENT_W, h: 0.4,
    fill: { color: '1E293B', transparency: 30 },
    line: { color: COLORS.teal, transparency: 50, width: 0.5 },
    rectRadius: 0.05
  });
  slide.addText("💡  多策略融合：规则匹配 + 语义相似度 + LLM 校验，归一化准确率达 95%+", {
    x: CONTENT_X + 0.3, y: insightY, w: CONTENT_W - 0.6, h: 0.4,
    fontSize: 12, color: COLORS.offWhite,
    fontFace: 'Calibri', valign: 'middle'
  });

  slide.render();
}

// ============================================================
// SLIDE 10: 智能匹配引擎
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "智能匹配引擎", "语义增强 + Bradley-Terry 权重调优");

  // Left: matching architecture text
  const leftX = CONTENT_X;
  const leftW = 4.8;
  const topY = CONTENT_Y + 1.0;

  const components = [
    { title: '多维度特征', desc: '技能匹配度 / 经验匹配 / 学历匹配 / 城市适配 / 薪资预期' },
    { title: '语义增强', desc: '基于向量嵌入的技能语义相似度计算，捕捉隐性技能关联' },
    { title: 'BT 权重调优', desc: 'Bradley-Terry 模型 + Optuna 优化，自动学习各维度最优权重' },
    { title: '多样性推荐', desc: 'MMR 重排序策略，平衡匹配精度与结果多样性' },
  ];

  components.forEach((c, i) => {
    const y = topY + i * 0.8;
    slide.addShape(SHAPES.OVAL, {
      x: leftX, y: y + 0.1, w: 0.3, h: 0.3,
      fill: { color: COLORS.cyan }
    });
    slide.addText(String(i + 1), {
      x: leftX, y: y + 0.1, w: 0.3, h: 0.3,
      fontSize: 12, bold: true, color: COLORS.darkBg,
      align: 'center', valign: 'middle'
    });
    slide.addText(c.title, {
      x: leftX + 0.5, y, w: leftW - 0.5, h: 0.3,
      fontSize: 14, bold: true, color: COLORS.white,
      fontFace: 'Calibri'
    });
    slide.addText(c.desc, {
      x: leftX + 0.5, y: y + 0.3, w: leftW - 0.5, h: 0.4,
      fontSize: 11, color: COLORS.muted,
      fontFace: 'Calibri'
    });
  });

  // Right: image
  const imgX = CONTENT_X + 5.3;
  const imgY = CONTENT_Y + 0.9;
  const imgW = 3.7;
  const imgH = 3.5;

  slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
    x: imgX, y: imgY, w: imgW, h: imgH,
    fill: { color: COLORS.cardBg },
    line: { color: COLORS.teal, transparency: 50, width: 1 },
    rectRadius: 0.1
  });

  slide.addImage({
    path: path.join(IMG_DIR, 'hero-matching-engine.jpg'),
    x: imgX + 0.15, y: imgY + 0.15, w: imgW - 0.3, h: imgH - 0.3,
    mode: 'cover'
  });

  slide.render();
}

// ============================================================
// SLIDE 11: 三项准确率验证
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "三项准确率验证", "核心指标全部超过 90% 目标线");

  // Big metric cards
  const metrics = [
    { label: 'JD 抽取 F1', value: '90.38%', target: '≥ 90%' },
    { label: '简历抽取 F1', value: '93.38%', target: '≥ 90%' },
    { label: '匹配准确率', value: '96.00%', target: '≥ 90%' },
  ];

  const cardW = (CONTENT_W - 0.4) / 3;
  const cardH = 2.0;
  const startY = CONTENT_Y + 1.0;

  metrics.forEach((m, i) => {
    const x = CONTENT_X + i * (cardW + 0.2);

    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x, y: startY, w: cardW, h: cardH,
      fill: { color: COLORS.cardBg },
      line: { color: COLORS.cyan, transparency: 40, width: 1 },
      rectRadius: 0.1
    });

    // Label
    slide.addText(m.label, {
      x, y: startY + 0.25, w: cardW, h: 0.35,
      fontSize: 14, color: COLORS.muted,
      align: 'center', fontFace: 'Calibri'
    });

    // Big value
    slide.addText(m.value, {
      x, y: startY + 0.6, w: cardW, h: 0.8,
      fontSize: 40, bold: true, color: COLORS.cyan,
      fontFace: 'Georgia', align: 'center', valign: 'middle',
      charSpacing: 1
    });

    // Target indicator
    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x: x + cardW / 2 - 0.7, y: startY + 1.5, w: 1.4, h: 0.32,
      fill: { color: '0E7490' },
      rectRadius: 0.16
    });
    slide.addText("✓ 目标 " + m.target, {
      x: x + cardW / 2 - 0.7, y: startY + 1.5, w: 1.4, h: 0.32,
      fontSize: 11, bold: true, color: COLORS.white,
      align: 'center', valign: 'middle'
    });
  });

  // Chart: bar comparison
  const chartY = startY + cardH + 0.3;
  const chartH = CONTENT_Y + CONTENT_H - chartY - 0.1;

  slide.addChart(
    CHARTS.BAR,
    [
      { name: '准确率', labels: ['JD 抽取', '简历抽取', '匹配推荐'], values: [90.38, 93.38, 96.00] },
      { name: '目标线', labels: ['JD 抽取', '简历抽取', '匹配推荐'], values: [90, 90, 90] },
    ],
    {
      x: CONTENT_X + 0.5,
      y: chartY,
      w: CONTENT_W - 1.0,
      h: chartH,
      barDir: 'col',
      barGrouping: 'clustered',
      catAxisLabelFontSize: 11,
      catAxisLabelColor: COLORS.muted,
      valAxisLabelColor: COLORS.muted,
      valAxisMinVal: 80,
      valAxisMaxVal: 100,
      valGridLine: { color: '334155', size: 0.5 },
      dataColors: [COLORS.cyan, COLORS.teal],
      showLegend: true,
      legendFontSize: 10,
      legendColor: COLORS.muted,
      showValue: true,
      dataLabelColor: COLORS.white,
      dataLabelFontSize: 10,
      dataLabelPosition: 'outEnd',
      chartColors: {
        text: COLORS.white,
      }
    }
  );

  slide.render();
}

// ============================================================
// SLIDE 12: 前端 — 图谱全景
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "产品功能：图谱全景", "交互式技能知识图谱，可视化探索技能生态");

  // Left: product screenshot
  const imgX = CONTENT_X;
  const imgY = CONTENT_Y + 0.9;
  const imgW = 5.2;
  const imgH = 3.8;

  slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
    x: imgX, y: imgY, w: imgW, h: imgH,
    fill: { color: COLORS.cardBg },
    line: { color: COLORS.teal, transparency: 50, width: 1 },
    rectRadius: 0.1
  });

  slide.addImage({
    path: path.join(IMG_DIR, 'hero-graph-dashboard.jpg'),
    x: imgX + 0.15, y: imgY + 0.15, w: imgW - 0.3, h: imgH - 0.3,
    mode: 'cover'
  });

  // Right: feature list
  const rightX = CONTENT_X + 5.7;
  const rightW = 3.3;
  const topY = CONTENT_Y + 1.0;

  const features = [
    { title: '力导向图谱', desc: '5000+ 节点实时渲染，缩放拖拽流畅交互' },
    { title: '多维度筛选', desc: '按城市/经验/薪资/技能组多条件过滤' },
    { title: '技能搜索', desc: '模糊搜索 + 联想推荐，秒级定位技能节点' },
    { title: '详情面板', desc: '点击查看岗位/技能详情与关联关系' },
    { title: '响应式布局', desc: '桌面/平板/手机三端自适应体验' },
  ];

  features.forEach((f, i) => {
    const y = topY + i * 0.68;
    slide.addShape(SHAPES.OVAL, {
      x: rightX, y: y + 0.08, w: 0.18, h: 0.18,
      fill: { color: COLORS.cyan }
    });
    slide.addText(f.title, {
      x: rightX + 0.35, y, w: rightW - 0.35, h: 0.3,
      fontSize: 13, bold: true, color: COLORS.white,
      fontFace: 'Calibri'
    });
    slide.addText(f.desc, {
      x: rightX + 0.35, y: y + 0.28, w: rightW - 0.35, h: 0.35,
      fontSize: 11, color: COLORS.muted,
      fontFace: 'Calibri'
    });
  });

  slide.render();
}

// ============================================================
// SLIDE 13: 简历匹配与演化看板（2 卡片）
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "产品功能：简历匹配 & 演化看板", "人岗智能匹配 + 技能演化趋势洞察");

  const cards = [
    {
      img: 'card-resume-match.jpg',
      title: '简历智能匹配',
      points: [
        '上传简历自动解析技能',
        '多维度匹配评分与排名',
        '差距分析与提升建议',
        '学习路径智能推荐'
      ]
    },
    {
      img: 'card-evolution.jpg',
      title: '技能演化看板',
      points: [
        '技能需求趋势追踪',
        '新旧技能更替可视化',
        '岗位结构变化分析',
        '未来技能预测洞察'
      ]
    }
  ];

  const cardW = (CONTENT_W - 0.3) / 2;
  const cardH = 3.8;
  const startY = CONTENT_Y + 0.95;

  cards.forEach((card, i) => {
    const x = CONTENT_X + i * (cardW + 0.3);

    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x, y: startY, w: cardW, h: cardH,
      fill: { color: COLORS.cardBg },
      line: { color: COLORS.teal, transparency: 60, width: 1 },
      rectRadius: 0.1
    });

    // Card image top
    const imgH = cardH * 0.38;
    slide.addImage({
      path: path.join(IMG_DIR, card.img),
      x: x + 0.15, y: startY + 0.15, w: cardW - 0.3, h: imgH - 0.15,
      mode: 'cover'
    });

    // Title
    slide.addText(card.title, {
      x: x + 0.3, y: startY + imgH + 0.1, w: cardW - 0.6, h: 0.4,
      fontSize: 17, bold: true, color: COLORS.white,
      fontFace: 'Calibri'
    });

    // Accent bar
    slide.addShape(SHAPES.RECTANGLE, {
      x: x + 0.3, y: startY + imgH + 0.5, w: 0.5, h: 0.04,
      fill: { color: COLORS.cyan }
    });

    // Points
    card.points.forEach((p, pi) => {
      const py = startY + imgH + 0.65 + pi * 0.45;
      slide.addText("✓", {
        x: x + 0.3, y: py, w: 0.3, h: 0.32,
        fontSize: 13, color: COLORS.cyan,
        valign: 'middle'
      });
      slide.addText(p, {
        x: x + 0.6, y: py, w: cardW - 0.9, h: 0.32,
        fontSize: 12, color: COLORS.offWhite,
        fontFace: 'Calibri', valign: 'middle'
      });
    });
  });

  slide.render();
}

// ============================================================
// SLIDE 14: 性能优化成果
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "性能优化成果", "全栈性能调优，用户体验显著提升");

  // Top: 4 key metrics
  const metrics = [
    { num: '~181KB', label: '首屏 JS gzip', sub: 'Vite 分包 + 路由懒加载' },
    { num: '< 2s', label: 'P95 响应时间', sub: '100 并发下压测达标' },
    { num: '3.2x', label: '批量抽取加速', sub: '并发 + 缓存优化' },
    { num: '5 min', label: '缓存有效期', sub: 'TanStack Query 优化' },
  ];

  const metricW = (CONTENT_W - 0.45) / 4;
  const metricH = 1.5;
  const metricY = CONTENT_Y + 0.95;

  metrics.forEach((m, i) => {
    const x = CONTENT_X + i * (metricW + 0.15);

    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x, y: metricY, w: metricW, h: metricH,
      fill: { color: COLORS.cardBg },
      line: { color: COLORS.teal, transparency: 60, width: 1 },
      rectRadius: 0.08
    });

    slide.addText(m.num, {
      x, y: metricY + 0.2, w: metricW, h: 0.55,
      fontSize: 26, bold: true, color: COLORS.cyan,
      fontFace: 'Georgia', align: 'center', valign: 'middle',
      charSpacing: 1
    });

    slide.addText(m.label, {
      x, y: metricY + 0.75, w: metricW, h: 0.3,
      fontSize: 13, bold: true, color: COLORS.white,
      align: 'center', fontFace: 'Calibri'
    });

    slide.addText(m.sub, {
      x, y: metricY + 1.05, w: metricW, h: 0.35,
      fontSize: 10, color: COLORS.muted,
      align: 'center', fontFace: 'Calibri'
    });
  });

  // Bottom: optimization areas
  const areasY = metricY + metricH + 0.3;

  const areas = [
    { title: '前端优化', items: 'manualChunks 分包 · 骨架屏 · 搜索防抖 · 路由预取 · 图片懒加载' },
    { title: '后端优化', items: '连接池调优 · Redis 多级缓存 · Gunicorn 多 worker · SQL 索引优化' },
    { title: '算法优化', items: '批量抽取并行化 · 向量缓存复用 · BT 模型增量更新' },
  ];

  areas.forEach((a, i) => {
    const ay = areasY + i * 0.55;
    slide.addShape(SHAPES.RECTANGLE, {
      x: CONTENT_X, y: ay + 0.08, w: 0.05, h: 0.35,
      fill: { color: COLORS.cyan }
    });
    slide.addText(a.title, {
      x: CONTENT_X + 0.2, y: ay, w: 1.5, h: 0.5,
      fontSize: 13, bold: true, color: COLORS.white,
      fontFace: 'Calibri', valign: 'middle'
    });
    slide.addText(a.items, {
      x: CONTENT_X + 1.8, y: ay, w: CONTENT_W - 2.0, h: 0.5,
      fontSize: 12, color: COLORS.muted,
      fontFace: 'Calibri', valign: 'middle'
    });
  });

  slide.render();
}

// ============================================================
// SLIDE 15: 技术亮点与创新（4 卡片）
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "技术亮点与创新", "四大核心创新点，构建差异化竞争优势");

  const innovations = [
    {
      num: '01',
      title: '多源异构数据融合',
      desc: '招聘 + 课程双维度数据交叉验证，构建完整技能生态图谱，数据质量三重校验'
    },
    {
      num: '02',
      title: 'LLM + 规则双路抽取',
      desc: '大模型语义理解结合规则引擎精确匹配，RAG 接地校验保障抽取准确率'
    },
    {
      num: '03',
      title: 'BT 模型权重自学习',
      desc: 'Bradley-Terry 配对比较 + Optuna 超参优化，匹配权重自动迭代进化'
    },
    {
      num: '04',
      title: '技能演化时间轴',
      desc: '版本化图谱 + 差异检测算法，追踪技能兴衰趋势，预测未来需求方向'
    }
  ];

  const cardW = (CONTENT_W - 0.45) / 2;
  const cardH = 1.8;
  const startY = CONTENT_Y + 1.0;

  innovations.forEach((inn, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = CONTENT_X + col * (cardW + 0.45);
    const y = startY + row * (cardH + 0.2);

    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x, y, w: cardW, h: cardH,
      fill: { color: COLORS.cardBg },
      line: { color: COLORS.cyan, transparency: 50, width: 1 },
      rectRadius: 0.1
    });

    // Big number watermark
    slide.addText(inn.num, {
      x: x + cardW - 1.0, y: y + 0.1, w: 0.9, h: 0.8,
      fontSize: 48, bold: true, color: COLORS.cyan,
      fontFace: 'Georgia', align: 'right', charSpacing: 1,
      transparency: 15
    });

    // Title
    slide.addText(inn.title, {
      x: x + 0.3, y: y + 0.25, w: cardW - 0.6, h: 0.4,
      fontSize: 15, bold: true, color: COLORS.white,
      fontFace: 'Calibri'
    });

    // Accent line
    slide.addShape(SHAPES.RECTANGLE, {
      x: x + 0.3, y: y + 0.7, w: 0.5, h: 0.04,
      fill: { color: COLORS.cyan }
    });

    // Description
    slide.addText(inn.desc, {
      x: x + 0.3, y: y + 0.85, w: cardW - 0.6, h: 0.85,
      fontSize: 12, color: COLORS.muted,
      fontFace: 'Calibri', valign: 'top'
    });
  });

  slide.render();
}

// ============================================================
// SLIDE 16: 项目成果总览
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "项目成果总览", "核心指标全面达成，质量与性能双优");

  const bigStats = [
    { num: '123', unit: '个', label: '单元测试', color: COLORS.cyan },
    { num: '57', unit: '个', label: '集成测试', color: COLORS.teal },
    { num: '58', unit: '个', label: 'E2E 测试', color: COLORS.cyanLight },
    { num: '90%+', unit: '', label: '三项准确率', color: COLORS.accent },
  ];

  const statW = (CONTENT_W - 0.9) / 4;
  const statH = 2.2;
  const statY = CONTENT_Y + 1.1;

  bigStats.forEach((s, i) => {
    const x = CONTENT_X + i * (statW + 0.3);

    // Glow circle background
    slide.addShape(SHAPES.OVAL, {
      x: x + statW / 2 - 0.9, y: statY + 0.1, w: 1.8, h: 1.8,
      fill: { color: s.color, transparency: 88 }
    });

    // Big number
    slide.addText(s.num, {
      x, y: statY + 0.3, w: statW, h: 1.0,
      fontSize: 52, bold: true, color: s.color,
      fontFace: 'Georgia', align: 'center', valign: 'middle',
      charSpacing: 2
    });

    // Unit
    if (s.unit) {
      slide.addText(s.unit, {
        x: x + statW / 2 + 0.9, y: statY + 0.7, w: 0.5, h: 0.5,
        fontSize: 16, color: s.color,
        fontFace: 'Calibri', valign: 'middle'
      });
    }

    // Label
    slide.addText(s.label, {
      x, y: statY + 1.4, w: statW, h: 0.4,
      fontSize: 14, color: COLORS.offWhite,
      fontFace: 'Calibri', align: 'center'
    });
  });

  // Bottom summary
  const summaryY = statY + statH + 0.1;
  slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
    x: CONTENT_X, y: summaryY, w: CONTENT_W, h: 0.55,
    fill: { color: '0E2D48' },
    line: { color: COLORS.cyan, transparency: 40, width: 0.5 },
    rectRadius: 0.08
  });
  slide.addText(
    "全栈 6 大模块 · 18 项功能 · 238 个测试用例 · 三项准确率全部达标 · 端到端性能优化完成",
    {
      x: CONTENT_X + 0.3, y: summaryY, w: CONTENT_W - 0.6, h: 0.55,
      fontSize: 13, color: COLORS.cyanLight,
      fontFace: 'Calibri', align: 'center', valign: 'middle',
      bold: true
    }
  );

  slide.render();
}

// ============================================================
// SLIDE 17: 未来规划
// ============================================================
{
  let slide = pres.addSlide();
  addDarkBg(slide);
  addSlideTitle(slide, "未来规划", "持续迭代，打造更智能的职业发展助手");

  const phases = [
    {
      phase: '短期 · Q4 2026',
      items: ['更多招聘平台接入', '简历解析格式扩展', '移动端原生体验优化', '用户反馈快速迭代'],
      color: COLORS.cyan
    },
    {
      phase: '中期 · 2027 H1',
      items: ['企业端招聘 SaaS 化', 'AI 面试模拟功能', '学习路径个性化推荐', '多语言国际化支持'],
      color: COLORS.teal
    },
    {
      phase: '长期 · 2027 H2+',
      items: ['职业发展全周期陪伴', '行业趋势预测报告', '高校就业数据合作', '技能认证生态构建'],
      color: COLORS.deepBlue
    }
  ];

  const phaseW = (CONTENT_W - 0.4) / 3;
  const phaseH = 3.6;
  const startY = CONTENT_Y + 1.0;

  phases.forEach((p, i) => {
    const x = CONTENT_X + i * (phaseW + 0.2);

    // Card
    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x, y: startY, w: phaseW, h: phaseH,
      fill: { color: COLORS.cardBg },
      line: { color: p.color, transparency: 40, width: 1 },
      rectRadius: 0.1
    });

    // Phase header
    slide.addShape(SHAPES.ROUNDED_RECTANGLE, {
      x, y: startY, w: phaseW, h: 0.55,
      fill: { color: p.color },
      rectRadius: 0.1
    });
    slide.addText(p.phase, {
      x, y: startY, w: phaseW, h: 0.55,
      fontSize: 14, bold: true, color: COLORS.white,
      fontFace: 'Calibri', align: 'center', valign: 'middle'
    });

    // Items
    p.items.forEach((item, ii) => {
      const iy = startY + 0.8 + ii * 0.65;
      slide.addShape(SHAPES.OVAL, {
        x: x + 0.25, y: iy + 0.08, w: 0.14, h: 0.14,
        fill: { color: p.color }
      });
      slide.addText(item, {
        x: x + 0.5, y: iy, w: phaseW - 0.7, h: 0.4,
        fontSize: 12, color: COLORS.offWhite,
        fontFace: 'Calibri', valign: 'middle'
      });
    });
  });

  slide.render();
}

// ============================================================
// SLIDE 18: CLOSING
// ============================================================
{
  let slide = pres.addSlide();
  slide.background = { color: COLORS.darkBg };

  // Background image
  slide.addImage({
    path: path.join(IMG_DIR, 'bg-closing.jpg'),
    x: 0, y: 0, w: SLIDE_W, h: SLIDE_H,
    mode: 'cover'
  });

  // Overlay
  slide.addShape(SHAPES.RECTANGLE, {
    x: 0, y: 0, w: SLIDE_W, h: SLIDE_H,
    fill: { color: '0A1628', transparency: 35 }
  });

  // Center glow
  addGlowCircle(slide, CENTER_X, CENTER_Y - 0.3, 3.5, COLORS.cyan);

  // Thank you
  slide.addText("感谢聆听", {
    x: 0, y: CENTER_Y - 0.8, w: SLIDE_W, h: 0.9,
    fontSize: 48, bold: true, color: COLORS.white,
    fontFace: 'Georgia', charSpacing: 6,
    align: 'center', valign: 'middle'
  });

  // Subtitle
  slide.addText("智岗罗盘 — 让每个职业选择都有数据可循", {
    x: 0, y: CENTER_Y + 0.2, w: SLIDE_W, h: 0.5,
    fontSize: 20, color: COLORS.cyanLight,
    fontFace: 'Georgia', charSpacing: 2,
    align: 'center', valign: 'middle'
  });

  // Divider
  slide.addShape(SHAPES.RECTANGLE, {
    x: CENTER_X - 1.2, y: CENTER_Y + 0.85, w: 2.4, h: 0.04,
    fill: { color: COLORS.cyan, transparency: 40 }
  });

  // Q&A
  slide.addText("Q & A", {
    x: 0, y: CENTER_Y + 1.0, w: SLIDE_W, h: 0.5,
    fontSize: 18, color: COLORS.muted,
    fontFace: 'Georgia', charSpacing: 3,
    align: 'center', valign: 'middle'
  });

  slide.render();
}

// ============================================================
// GENERATE
// ============================================================
const outputPath = path.join(__dirname, '智岗罗盘-终期答辩.pptx');
pres.writeFile({ fileName: outputPath })
  .then(() => {
    console.log('PPT generated successfully:', outputPath);
    console.log('Total slides:', 18);
  })
  .catch(err => {
    console.error('Error generating PPT:', err);
    process.exit(1);
  });
