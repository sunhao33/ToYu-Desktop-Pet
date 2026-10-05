/* ─────────────────────────────────────────────────────────
   ToYu 宣传站 · 趣味交互
   包含三块：点宠物说话 / 功能卡实例弹窗 / AI 对话试玩

   设计原则：所有交互都在浏览器本地完成，不发任何请求。
   对话内容是**预设脚本**，页面里也明确标注了「这不是真的 AI」——
   不误导访客，同时把「为什么必须做成桌面软件」讲清楚。
   ───────────────────────────────────────────────────────── */

(function () {
  'use strict';

  /* ══════════════════════════════════════════════════════
     一、点宠物说话
     台词按时段（早/午/晚/深夜）与连点次数变化，
     与桌面版 pet_companion 的心情逻辑同源。
     ══════════════════════════════════════════════════════ */
  var petBtn = document.getElementById('petBtn');
  var petBubble = document.getElementById('petBubble');
  var petBubbleText = document.getElementById('petBubbleText');
  var petHint = document.getElementById('petHint');
  var petStage = document.querySelector('.pet-stage');

  var LINES = {
    morning: [
      '早呀！新的一天，先定今天的小目标？',
      '早上脑子最清楚，要不要来一轮 45 分钟？',
      '我刚看了眼你的待办，有三项还没动哦…',
      '（伸懒腰）今天也一起加油吧！'
    ],
    afternoon: [
      '下午容易犯困，来一轮番茄钟提提神？',
      '你已经连续坐了两小时啦，起来动动？',
      '刚才那段时间效率不错，我记下来了。',
      '要不要看看这周的学习报告？'
    ],
    evening: [
      '晚上好～今天学了多久要我报一下吗？',
      '傍晚适合复盘，点「学习/工作报告」看看？',
      '（打了个哈欠）今天也辛苦啦。',
      '明天要不要试试 60 分钟长专注？'
    ],
    night: [
      '都这个点了…再不睡明天效率会掉哦。',
      '（揉眼睛）我先困了，你也早点休息。',
      '深夜学习伤身，要不明天早起补？',
      '我把今天的数据都存好了，去睡吧～'
    ],
    clicked: [
      '诶，别戳我啦～',
      '（扭了扭）痒！',
      '再点我就要生气了哦。',
      '你是不是没事干了…',
      '好啦好啦，我陪你。'
    ]
  };

  var clickCount = 0;
  var bubbleTimer = null;

  function pickLines() {
    var h = new Date().getHours();
    if (h >= 5 && h < 12) return LINES.morning;
    if (h >= 12 && h < 18) return LINES.afternoon;
    if (h >= 18 && h < 23) return LINES.evening;
    return LINES.night;
  }

  function hearts(ev) {
    if (!petStage) return;
    var rect = petStage.getBoundingClientRect();
    var x = (ev && ev.clientX ? ev.clientX : rect.left + rect.width / 2) - rect.left;
    var y = (ev && ev.clientY ? ev.clientY : rect.top + rect.height / 2) - rect.top;
    var glyphs = ['♥', '★', '✦', '♪'];
    for (var i = 0; i < 5; i++) {
      var s = document.createElement('span');
      s.className = 'heart-pop';
      s.textContent = glyphs[Math.floor(Math.random() * glyphs.length)];
      s.style.left = (x + (Math.random() * 34 - 17)) + 'px';
      s.style.top = y + 'px';
      s.style.color = i % 2 ? 'var(--accent)' : '#E06C75';
      s.style.setProperty('--dx', (Math.random() * 40 - 20) + 'px');
      s.style.setProperty('--dx2', (Math.random() * 70 - 35) + 'px');
      s.style.animationDelay = (i * 55) + 'ms';
      petStage.appendChild(s);
      (function (node) {
        setTimeout(function () { node.remove(); }, 1400 + i * 60);
      })(s);
    }
  }

  if (petBtn && petBubble) {
    petBtn.addEventListener('click', function (ev) {
      clickCount++;
      if (petHint) petHint.classList.add('is-off');
      hearts(ev);

      var pool;
      if (clickCount > 4 && Math.random() < 0.65) {
        pool = LINES.clicked;
      } else {
        pool = pickLines();
      }
      var text = pool[Math.floor(Math.random() * pool.length)];

      // 连点 8 次彩蛋
      if (clickCount === 8) {
        text = '……你是不是特别喜欢我？（好感度 +1）';
      } else if (clickCount === 15) {
        text = '好吧，我承认：被你点也挺开心的。（好感度 68/100）';
      }

      petBubbleText.textContent = text;
      petBubble.classList.add('is-on');
      clearTimeout(bubbleTimer);
      bubbleTimer = setTimeout(function () {
        petBubble.classList.remove('is-on');
      }, 3200);
    });
  }


  /* ══════════════════════════════════════════════════════
     二、功能卡实例弹窗
     内容全部取材自软件的真实输出形状（报告格式、番茄参数、
     颜色量化结果等），不是编的。
     ══════════════════════════════════════════════════════ */
  var DEMOS = {
    report: {
      ic: '📈',
      title: '学习/工作报告',
      sub: '基础版纯本机统计 · 可导出 Markdown',
      body: '' +
        '<div class="ex">' +
        '  <div class="ex-mock"># 学习/工作报告 · 本周\n' +
        '> 2026-09-29 ~ 2026-10-05\n\n' +
        '## 概览\n' +
        '- 有效学习时长：**8 小时 32 分**（较上周 +1 小时 15 分）\n' +
        '- 桌面记录时长：21 小时 08 分\n' +
        '- 完成任务：**7 项**\n' +
        '- 目标达成：5 / 7 天\n\n' +
        '## 时段分布\n' +
        '```\n' +
        '09:00  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  86 分\n' +
        '10:00  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  124 分  ← 最专注\n' +
        '14:00  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓  78 分\n' +
        '15:00  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  96 分\n' +
        '21:00  ▓▓▓▓▓▓▓▓▓  42 分\n' +
        '```\n\n' +
        '## 应用分布\n' +
        '- 编辑器（VS Code / PyCharm）　4 小时 12 分　49%\n' +
        '- 浏览器　　　　　　　　　　　2 小时 05 分　24%\n' +
        '- 文档工具　　　　　　　　　　1 小时 10 分　14%\n\n' +
        '## 建议\n' +
        '- 周三、周五几乎空白，建议把难点任务排到这两天上午\n' +
        '- 最专注时段集中在 10:00 前后，可把重要任务固定在这个窗口\n' +
        '</div>' +
        '  <div class="ex-note"><b>数字从哪来：</b>全部读自本机已有记录' +
        '（专注日志 + 屏幕会话 + 任务历史）。报告代码<b>不自己算新数字</b>，' +
        '同一个数在不同页面必然一致。</div>' +
        '</div>',
      foot: 'AI 版会在此基础上做深度分析，但同样被约束「只能使用给定的数字」。'
    },

    flow: {
      ic: '🍅',
      title: '心流模式',
      sub: '番茄轮次 · 休息机制 · 计划项独立计时',
      body: '' +
        '<ul class="ex-list">' +
        '  <li><b>第 3 轮</b>　●●○○　今日 3 轮<br>' +
        '      当前：专注 25:00 → 到点自动进入 5 分钟休息</li>' +
        '  <li><b>计划栏独立计时</b><br>' +
        '      「写竞赛设计文档」累计 1 小时 24 分<br>' +
        '      「复习机器学习第 3 章」累计 48 分<br>' +
        '      切换任务不会把时间记到别人头上</li>' +
        '  <li><b>今日专注时间轴</b><br>' +
        '      一屏看完 24 小时：色块越深＝单段越长，红竖线是当前时刻</li>' +
        '  <li><b>暂停后继续不会重置</b><br>' +
        '      跑了 10 分钟暂停、继续 → 仍从 15:00 接着跑（不是跳回 25:00）</li>' +
        '</ul>' +
        '<div class="ex-note">预设有 25 / 45 / 60 / 90 分钟四档。' +
        '60 与 90 分钟不会被截成 59 分钟 —— 这个 bug 修过，也补了回归测试。</div>',
      foot: '休息时长可配置；到点会弹通知卡片，并同步更新轮次记录。'
    },

    goal: {
      ic: '🎯',
      title: '每日目标与进度环',
      sub: '进度环 + 近 7 天坚持曲线',
      body: '' +
        '<div class="ex">' +
        '  <div class="ex-bar"><span>今日</span><i style="--v:92%"></i><span>110 / 120 分</span></div>' +
        '  <div class="ex-bar"><span>昨天</span><i style="--v:100%"></i><span>135 / 120 分 ✓</span></div>' +
        '  <div class="ex-bar"><span>前天</span><i style="--v:35%"></i><span>42 / 120 分</span></div>' +
        '  <div class="ex-bar"><span>10-02</span><i style="--v:78%"></i><span>94 / 120 分</span></div>' +
        '  <div class="ex-bar"><span>10-01</span><i style="--v:88%"></i><span>106 / 120 分</span></div>' +
        '  <div class="ex-bar"><span>09-30</span><i style="--v:100%"></i><span>128 / 120 分 ✓</span></div>' +
        '  <div class="ex-bar"><span>09-29</span><i style="--v:60%"></i><span>72 / 120 分</span></div>' +
        '  <div class="ex-note">目标会<b>记住上一次的设置</b>，不用每天重设；' +
        '达成时进度环变绿并弹一句祝贺。</div>' +
        '</div>',
      foot: '「有效学习时长」的判定有明确规则：只统计学习类应用与含学习关键词的窗口，碎片会话（<3 分钟）不计。'
    },

    screen: {
      ic: '🖥',
      title: '屏幕时间统计',
      sub: '应用排行 · 时段分布 · 跨零点正确切分',
      body: '' +
        '<div class="ex">' +
        '  <div class="ex-row"><span class="ex-k">今日总使用</span>' +
        '    <span class="ex-v">6 小时 42 分　较昨日 −38 分</span></div>' +
        '  <div class="ex-bar"><span>编辑器</span><i style="--v:88%"></i><span>2h 51m　43%</span></div>' +
        '  <div class="ex-bar"><span>浏览器</span><i style="--v:52%"></i><span>1h 42m　25%</span></div>' +
        '  <div class="ex-bar"><span>文档</span><i style="--v:30%"></i><span>58m　　14%</span></div>' +
        '  <div class="ex-bar"><span>聊天</span><i style="--v:18%"></i><span>36m　　 9%</span></div>' +
        '  <div class="ex-bar"><span>其它</span><i style="--v:12%"></i><span>35m　　 9%</span></div>' +
        '  <div class="ex-note"><b>跨零点不会算错：</b>23:00 一直用到 00:30 的会话会' +
        '按午夜切成两段，分别记到两天 —— 不会把昨天的 90 分钟全算进今天。</div>' +
        '  <div class="ex-note"><b>隐私可控：</b>可以关闭「记录窗口标题」，' +
        '这样只统计应用与时长，不记录你在具体看什么。</div>' +
        '</div>',
      foot: '采样在独立子线程，60 秒落盘一次，界面完全不受影响。'
    },

    bead: {
      ic: '🧩',
      title: '像素创作与拼豆',
      sub: '导入图片 → 自动抠图 → 颜色量化',
      body: '' +
        '<div class="ex">' +
        '  <div class="ex-row"><span class="ex-k">处理流程</span>' +
        '    <span class="ex-v">导入 → 去白底 → 腐蚀 → 距离场羽化 → 量化到调色板</span></div>' +
        '  <div class="ex-row"><span class="ex-k">量化结果（示例）</span></div>' +
        '  <div class="swatches">' +
        '    <i style="background:#2B2B2B"></i><i style="background:#4A4A4A"></i>' +
        '    <i style="background:#7A7A7A"></i><i style="background:#A8A8A8"></i>' +
        '    <i style="background:#D8D8D8"></i><i style="background:#F2F2F2"></i>' +
        '    <i style="background:#3AA675"></i><i style="background:#6FCF97"></i>' +
        '    <i style="background:#C49A3C"></i><i style="background:#E0B65A"></i>' +
        '    <i style="background:#B5502F"></i><i style="background:#E06C75"></i>' +
        '  </div>' +
        '  <div class="ex-note">调色板固定 <b>51 色</b>，保证做出来的拼豆' +
        '用市面常见色号买得到；画布可导出 PNG。</div>' +
        '  <div class="ex-note">作品会收进<b>收藏夹（上限 20）</b>，' +
        '点一下就能切换成你的桌面伙伴 —— 首页那个 TV 头宠物就是这么来的。</div>' +
        '</div>',
      foot: '编辑器支持撤销、格子尺寸切换、从作品集继续编辑。'
    },

    memory: {
      ic: '🏠',
      title: '有性格的陪伴',
      sub: '好感度 · 心情 · 时间与天气感知',
      body: '' +
        '<ul class="ex-list">' +
        '  <li><b>好感度会衰减</b>　基础分 68/100<br>' +
        '      长时间不互动会缓慢下降，互动与完成任务会回升</li>' +
        '  <li><b>心情不是随机数</b>　按好感度 + 空闲时长 + 工作时间推导<br>' +
        '      开心 / 好奇 / 专注 / 疲惫 / 孤独 / 困倦 / 贪玩 / 兴奋</li>' +
        '  <li><b>时间感知</b>　夜晚整体调暗到 65% 并放慢走动<br>' +
        '      清晨活跃度 ×1.3，傍晚 ×0.8</li>' +
        '  <li><b>天气感知</b>　下雨自己撑伞，高温掏冰淇淋出来吃</li>' +
        '  <li><b>像素小房子</b>　拖到门口就回家；太久没互动也会自己回去休息</li>' +
        '</ul>' +
        '<div class="ex-note">这些「看起来没用」的细节，其实是桌宠能长期留在' +
        '桌面上不烦人的关键 —— 它得有变化，才不像一张贴纸。</div>',
      foot: '配件 7 种、粒子特效 5 种（爱心 / 星星 / 音符 / 雪花 / 雨滴）。'
    }
  };

  var modal = document.getElementById('demoModal');
  var mIcon = document.getElementById('modalIcon');
  var mTitle = document.getElementById('modalTitle');
  var mSub = document.getElementById('modalSub');
  var mBody = document.getElementById('modalBody');
  var mFoot = document.getElementById('modalFoot');
  var lastFocus = null;

  function openDemo(key) {
    var d = DEMOS[key];
    if (!d || !modal) return;
    lastFocus = document.activeElement;
    mIcon.textContent = d.ic;
    mTitle.textContent = d.title;
    mSub.textContent = d.sub;
    mBody.innerHTML = d.body;
    mFoot.textContent = d.foot || '';
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
    var closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) closeBtn.focus();
  }

  function closeDemo() {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    document.body.style.overflow = '';
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  var cardsWrap = document.getElementById('featureCards');
  if (cardsWrap) {
    cardsWrap.addEventListener('click', function (ev) {
      var card = ev.target.closest('.card-clickable');
      if (card) openDemo(card.getAttribute('data-demo'));
    });
    cardsWrap.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Enter' && ev.key !== ' ') return;
      var card = ev.target.closest('.card-clickable');
      if (!card) return;
      ev.preventDefault();
      openDemo(card.getAttribute('data-demo'));
    });
  }

  if (modal) {
    modal.addEventListener('click', function (ev) {
      if (ev.target.closest('[data-close]')) closeDemo();
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') closeDemo();
    });
  }


  /* ══════════════════════════════════════════════════════
     三、AI 对话试玩（本地预设脚本）
     ══════════════════════════════════════════════════════ */
  var chatLog = document.getElementById('chatLog');
  var chatInput = document.getElementById('chatInput');
  var chatSend = document.getElementById('chatSend');
  var chatChips = document.getElementById('chatChips');
  var chatStatus = document.getElementById('chatStatus');

  // 每条脚本：匹配词 -> 依次输出的气泡
  //   {t: 文本}            普通文本
  //   {tool: 名称}         工具调用标签
  //   {out: 文本}          工具执行结果（绿色左边线）
  var SCRIPTS = [
    {
      k: ['学了多久', '这周', '学习情况', '学了多长', '统计', '报告'],
      steps: [
        { tool: 'get_learning_stats', t: '我先查一下你这周的记录。' },
        { out: 'week=2026-09-29..2026-10-05  study_minutes=512  '
              + 'screen_minutes=1268  tasks_done=7  goal_hit_days=5' },
        { t: '这周有效学习 **8 小时 32 分**，比上周多了 1 小时 15 分。' },
        { t: '最专注的时段是上午 10 点前后（124 分钟），'
            + '但周三、周五几乎是空的 —— 这两天可以留意一下。' }
      ]
    },
    {
      k: ['安排', '计划', '复习', '下周', '规划'],
      steps: [
        { tool: 'get_learning_stats', t: '先看看你这周的情况，再决定怎么排。' },
        { out: 'gap_days=["2026-10-01","2026-10-03"]  weakest="周三/周五上午"' },
        { tool: 'list_todos', t: '再看看待办里有没有欠账。' },
        { out: '3 项未完成：复习机器学习第 3 章 / 写竞赛设计文档 / 整理实验数据' },
        { tool: 'add_todo', t: '好，我把复习计划拆成 4 项写进待办。' },
        { out: 'added=4  priority[high]=2  ("复习第3章","做习题","整理笔记","自测")' },
        { tool: 'set_daily_goal', t: '再给周三、周五各设 1 小时目标。' },
        { out: 'goal_minutes=60  days=["2026-10-01","2026-10-03"]' },
        { t: '安排好了。我把最难的两项放在了周三和周五上午 —— '
            + '那是你一周里最专注的时段。' }
      ]
    },
    {
      k: ['分心', '什么时候', '效率', '注意力', '规律'],
      steps: [
        { tool: 'get_screen_time_detail', t: '我拉一下你这周的时段分布。' },
        { out: 'peak="10:00-11:00"  trough="15:00-16:00"  '
              + 'chat_apps_share="9%"  context_switches=214' },
        { t: '你的高效窗口很稳定：**上午 10 点前后**，'
            + '这一小时产出基本是下午的两倍。' },
        { t: '分心主要出现在 **15:00–16:00**，聊天类应用占了 9%，'
            + '而且这个时段的任务切换次数明显偏高。' },
        { t: '建议：把需要深度思考的任务固定在上午，'
            + '下午安排整理、回复这类低强度工作。' }
      ]
    },
    {
      k: ['记住', '我叫', '我喜欢', '每天晚上', '习惯'],
      steps: [
        { tool: 'remember', t: '好的，我记下来。' },
        { out: 'slot="study.focus_time_of_day"  value="20:00"  '
              + 'kind="preference"  confidence=0.92  '
              + 'evidence="「记住我每天晚上 8 点学习」"' },
        { t: '已写入记忆槽位 `study.focus_time_of_day = 20:00`。' },
        { t: '以后我推荐专注时间时会优先考虑晚上 8 点，'
            + '不会再给你推上午的时段。' },
        { t: '（这条置信度 0.92 —— 因为你说的是「记住…」，属于显性信号。'
            + '如果你只是随口说「晚上可能学一会儿」，我只会给 0.6 并再问你一次。）' }
      ]
    },
    {
      k: ['你好', '在吗', 'hi', 'hello', '你是谁', '介绍一下'],
      steps: [
        { t: '我在。我是 ToYu，住在你桌面上的那只。' },
        { t: '我能查你的学习记录、帮你加待办、设目标、生成报告 —— '
            + '最多自己跑 5 轮工具调用把事情办完。' },
        { t: '要不要试试问我「我这周学了多久」？' }
      ]
    }
  ];

  var FALLBACK = [
    { t: '这个我暂时答不上来 —— 网页版是**预设脚本演示**，'
         + '只有上面那几句是配好的。' },
    { t: '真实的多轮工具调用要运行桌面版（需要你自己的 API Key）。' },
    { t: '你可以点上面的快捷按钮，看看它拿到工具结果后会怎么组织语言。' }
  ];

  var busy = false;

  function addMsg(role, html) {
    var row = document.createElement('div');
    row.className = 'chat-msg ' + role;
    if (role === 'ai') {
      var av = document.createElement('span');
      av.className = 'avatar';
      av.textContent = '🥔';
      row.appendChild(av);
    }
    var b = document.createElement('div');
    b.className = 'bubble';
    b.innerHTML = html;
    row.appendChild(b);
    chatLog.appendChild(row);
    chatLog.scrollTop = chatLog.scrollHeight;
    return b;
  }

  function mdLite(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
            .replace(/`(.+?)`/g,
                     '<code style="background:var(--accent-sf);padding:1px 5px;'
                     + 'border-radius:4px;font-size:12.5px">$1</code>');
  }

  function typingBubble() {
    var row = document.createElement('div');
    row.className = 'chat-msg ai';
    row.innerHTML = '<span class="avatar">🥔</span>'
      + '<div class="bubble"><span class="chat-typing">'
      + '<i></i><i></i><i></i></span></div>';
    chatLog.appendChild(row);
    chatLog.scrollTop = chatLog.scrollHeight;
    return row;
  }

  function runSteps(steps, done) {
    var i = 0;
    (function next() {
      if (i >= steps.length) { done(); return; }
      var st = steps[i++];
      var wait = 520 + Math.random() * 480;

      if (st.tool) {
        var row = typingBubble();
        setTimeout(function () {
          row.remove();
          addMsg('ai', mdLite(st.t || '') +
                 ' <span class="tool-tag">🔧 ' + st.tool + '</span>');
          next();
        }, wait);
      } else if (st.out) {
        setTimeout(function () {
          addMsg('ai', '<span class="tool-out">→ ' + mdLite(st.out)
                 + '</span>');
          next();
        }, 380);
      } else {
        var t2 = typingBubble();
        setTimeout(function () {
          t2.remove();
          addMsg('ai', mdLite(st.t));
          next();
        }, wait);
      }
    })();
  }

  function respond(text) {
    if (busy) return;
    busy = true;
    if (chatSend) chatSend.disabled = true;
    if (chatStatus) chatStatus.textContent = '正在处理…';

    addMsg('user', mdLite(text));

    var low = text.toLowerCase();
    var hit = null;
    for (var n = 0; n < SCRIPTS.length; n++) {
      for (var m = 0; m < SCRIPTS[n].k.length; m++) {
        if (low.indexOf(SCRIPTS[n].k[m].toLowerCase()) !== -1) {
          hit = SCRIPTS[n];
          break;
        }
      }
      if (hit) break;
    }

    setTimeout(function () {
      runSteps(hit ? hit.steps : FALLBACK, function () {
        busy = false;
        if (chatSend) chatSend.disabled = false;
        if (chatStatus) chatStatus.textContent = '在线 · 本机运行';
      });
    }, 320);
  }

  if (chatLog && chatInput && chatSend) {
    // 欢迎语
    setTimeout(function () {
      addMsg('ai', '嗨，我是 ToYu 👋<br>'
        + '点下面的快捷问题，或直接打字试试 —— '
        + '我会演示拿到工具结果后是怎么组织语言的。');
    }, 700);

    chatSend.addEventListener('click', function () {
      var v = chatInput.value.trim();
      if (!v) return;
      chatInput.value = '';
      respond(v);
    });
    chatInput.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') {
        ev.preventDefault();
        chatSend.click();
      }
    });
  }

  if (chatChips) {
    chatChips.addEventListener('click', function (ev) {
      var chip = ev.target.closest('.chat-chip');
      if (!chip || chip.disabled) return;
      chip.disabled = true;
      respond(chip.getAttribute('data-say') || chip.textContent.trim());
    });
  }
})();
