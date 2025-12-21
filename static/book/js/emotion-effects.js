/**
 * emotion-english-final.js
 * 2025년 12월 기준 — 영어 태그 버전
 */

function emotionFunc() {
  const container = document.getElementById("emotionViewContainer");

  const categories = [
    {
      title: "Joy / Laugh",
      color: "#4ade80",
      items: ["happy","very_happy","excited","laughing","giggling","bursting_laughter","bright_smile","chuckling","loving_it","cheering"]
    },
    {
      title: "Sadness / Cry",
      color: "#60a5fa",
      items: ["sad","heartbroken","teary","sobbing","sniffling","crying","sorrowful","whimpering","anguished","choked_voice"]
    },
    {
      title: "Anger / Irritation",
      color: "#f87171",
      items: ["angry","shouting","yelling","snapping","irate","growling","furious","gritting_teeth","angered","frustrated"]
    },
    {
      title: "Shout / Exclaim",
      color: "#f43f5e",
      items: ["shout","yell","exclaim","scream","loud_voice","moan"]
    },
    {
      title: "Fear / Tension",
      color: "#a78bfa",
      items: ["scared","trembling","whisper_fear","shaking","panicked","terrified","nervous_voice","cold_sweat","fearful"]
    },
    {
      title: "Calm / Serious",
      color: "#38bdf8",
      items: ["calm","serious","quiet","steady","composed","firm","cold","expressionless"]
    },
    {
      title: "Whisper / Secret",
      color: "#e879f9",
      items: ["whispering","chuckles","soft_whisper", "exhales sharply" , "short pause","murmur","hushed","secretive","quietly","under_breath","sneaky_voice"]
    },
    {
      title: "Drunk / Drowsy",
      color: "#f97316",
      items: ["drunk","slurred","staggering","sleepy","yawning","drowsy","tipsy","wine_breath"]
    },
    {
      title: "ETC",
      color: "#c084fc",
      items: ["warried","clears throat", "embarrassed", "confused",  "awkward", "ashamed", "discouraged", "puzzled", "shocked", "startled", "uneasy", "bothered",  ]
    },
    {
      title: "Speech Style",
      color: "#fb923c",
      items: ["slow","fast","sarcastic","sly","cute","cool","arrogant","charming","formal","gentle","warm"]
    },
    {
      title: "Intensity / Volume",
      color: "#94a3b8",
      items: ["soft","slightly","normal","loud","very_loud","maximum","quiet","quietly","very_soft","very_slow"]
    }
  ];

  function createButtons(items) {
    return items.map(tag =>
      `<button class="emotion-chip" onclick="insertEmotionToPage('[${tag}]')">[${tag}]</button>`
    ).join("");
  }

  function makeSection(cat) {
    return `
      <div style="margin-bottom:22px; padding:18px; background:rgba(255,255,255,0.05);
                  border-left:4px solid ${cat.color}; border-radius:12px;">
        <div style="color:${cat.color}; margin-bottom:12px; font-weight:700; font-size:15px;">
          ${cat.title}
        </div>
        <div style="display:flex; flex-wrap:wrap; gap:8px;">
          ${createButtons(cat.items)}
        </div>
      </div>
    `;
  }

  container.innerHTML = `
    <div style="margin-top:20px; background:rgba(18,28,48,0.98); backdrop-filter:blur(16px);
                padding:30px; border-radius:20px; border:1px solid rgba(96,165,250,0.4);
                width:360px; max-height:85vh; overflow-y:auto; position:relative; font-family:'Pretendard',sans-serif;">

      <button onclick="document.getElementById('emotionViewContainer').innerHTML='';"
        style="position:absolute; top:14px; right:14px; background:rgba(255,80,80,0.25);
               border:1px solid rgba(255,80,80,0.5); color:#ff6b6b; font-size:26px;
               width:38px; height:38px; border-radius:12px; cursor:pointer;">×</button>

      <h3 style="color:#7dd3fc; text-align:center; margin-bottom:30px; font-size:22px; font-weight:800;">
        감정 리스트
      </h3>

      ${categories.map(makeSection).join("")}
    </div>
  `;
}

function insertEmotionToPage(text) {
  const textarea = document.getElementById("pageContent");
  if (!textarea) return;
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  textarea.value = textarea.value.substring(0, start) + text + " " + textarea.value.substring(end);
  textarea.selectionStart = textarea.selectionEnd = start + text.length + 1;
  textarea.focus();
}



