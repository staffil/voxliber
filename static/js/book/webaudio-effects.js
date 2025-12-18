// ========= WebAudio Effects Module =========
// 현재 적용된 효과 (전역 변수)
let currentEffect = "normal";

// ========= Web Audio API 연결 =========
function initAudioFilters() {
    const audioEl = document.getElementById("pageAudioPlayer");
    if (!audioEl) return;

    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaElementSource(audioEl);

    // 기본 필터
    const filter = audioCtx.createBiquadFilter();

    // ==== 동굴 효과용 Delay + Feedback ====
    const delayNode = audioCtx.createDelay();
    delayNode.delayTime.value = 0.25;

    const feedback = audioCtx.createGain();
    feedback.gain.value = 0.4;

    delayNode.connect(feedback);
    feedback.connect(delayNode);

    // ==== 로봇 효과용 Tremolo ====
    const tremoloGain = audioCtx.createGain();
    tremoloGain.gain.value = 1;

    const tremoloOsc = audioCtx.createOscillator();
    tremoloOsc.type = "sine";
    tremoloOsc.frequency.value = 10;
    tremoloOsc.connect(tremoloGain.gain);
    tremoloOsc.start();

    // ==== Master Gain (전체 볼륨) ====
    const masterGain = audioCtx.createGain();
    masterGain.gain.value = 1;

    // 기본 연결: source -> filter -> masterGain -> destination
    source.connect(filter);
    filter.connect(masterGain);
    masterGain.connect(audioCtx.destination);

    // UI 요소
    const filterType = document.getElementById("filterType");
    const filterFreq = document.getElementById("filterFrequency");
    const filterQ = document.getElementById("filterQ");
    const filterGain = document.getElementById("filterGain");
    const masterVolumeSlider = document.getElementById("masterVolume");
    const voiceBtns = document.querySelectorAll(".voice-btn");

    // 필터 업데이트
    function updateFilter() {
        filter.type = filterType.value;
        filter.frequency.value = parseFloat(filterFreq.value);
        filter.Q.value = parseFloat(filterQ.value);
        filter.gain.value = parseFloat(filterGain.value);
    }

    filterType.onchange = updateFilter;
    filterFreq.oninput = updateFilter;
    filterQ.oninput = updateFilter;
    filterGain.oninput = updateFilter;

    // Master Gain 슬라이더
    masterVolumeSlider.oninput = () => {
        masterGain.gain.value = parseFloat(masterVolumeSlider.value);
    };

    updateFilter();

// 효과 적용 라우팅
function applyRouting(effect) {
    try {
        source.disconnect();
        filter.disconnect();
        delayNode.disconnect();
        tremoloGain.disconnect();
    } catch (e) {}

    source.connect(filter);

    if (effect === "cave") {
        // 기존 동굴 메아리
        filter.connect(delayNode);
        delayNode.connect(masterGain);
        filter.connect(masterGain); // 원본 + 메아리
    }
    else if (effect === "robot") {
        // 기존 로봇
        filter.connect(tremoloGain);
        tremoloGain.connect(masterGain);
    }
    else if (effect === "whisper" || effect === "radio" || effect === "telephone" || effect === "megaphone" || effect === "protoss") {
        // 이 효과들도 딜레이/트레몰로 필요하면 cave/protoss랑 같은 라우팅 타면 됨
        filter.connect(delayNode);
        delayNode.connect(feedback);
        feedback.connect(delayNode);
        delayNode.connect(masterGain);
        filter.connect(masterGain);
        if (effect === "radio" || effect === "whisper") {
            filter.connect(tremoloGain);
            tremoloGain.connect(masterGain);
        }
    }
    else if (effect === "echo") {
        // 새로 추가된 echo 효과
        filter.connect(delayNode);
        delayNode.delayTime.value = 0.6;   // 긴 메아리
        feedback.gain.value = 0.75;        // 피드백 강하게
        delayNode.connect(masterGain);
        filter.connect(masterGain);         // 원본 + 메아리
    }
    else if (["demon","angel","vader","giant","tiny","angel","possessed"].includes(effect)) {
    filter.connect(delayNode);
    delayNode.connect(feedback);
    feedback.connect(delayNode);
    delayNode.connect(masterGain);
    filter.connect(masterGain);
    if (effect === "demon" || effect === "vader" || effect === "possessed") {
        filter.connect(tremoloGain);
        tremoloGain.connect(masterGain);
    }
}
else if (["horror","helium"].includes(effect)) {
    filter.connect(delayNode);
    delayNode.connect(feedback);
    feedback.connect(delayNode);
    delayNode.connect(masterGain);
    filter.connect(masterGain);
    if (effect === "horror") {
        filter.connect(tremoloGain);
        tremoloGain.connect(masterGain);
    }
}
else if (["timewarp","glitch","choir"].includes(effect)) {
    filter.connect(delayNode);
    delayNode.connect(feedback);
    feedback.connect(delayNode);
    delayNode.connect(masterGain);
    filter.connect(masterGain);
    filter.connect(tremoloGain);        // 모두 트레몰로 필요
    tremoloGain.connect(masterGain);
}
else if (["hyperpop","vaporwave","darksynth","lofi-girl","bitcrush-voice","portal","neoncity","ghost-in-machine"].includes(effect)) {
    filter.connect(delayNode);
    delayNode.connect(feedback);
    feedback.connect(delayNode);
    delayNode.connect(masterGain);
    filter.connect(masterGain);
    filter.connect(tremoloGain);
    tremoloGain.connect(masterGain);
}
    else {
        // 기본 효과
        filter.connect(masterGain);
    }
}


    // 프리셋 버튼 동작
    voiceBtns.forEach(btn => {
        btn.onclick = () => {
            let v = btn.dataset.voice;

        switch (v) {
            case "normal":
                filterType.value = "allpass";
                filterFreq.value = 1000;
                filterQ.value = 1;
                tremoloGain.gain.value = 0;
                delayNode.delayTime.value = 0;
                feedback.gain.value = 0;
                currentEffect = "normal";
                break;

            case "phone":
                filterType.value = "highpass";
                filterFreq.value = 2000;
                filterQ.value = 8;
                tremoloGain.gain.value = 0;
                delayNode.delayTime.value = 0;
                feedback.gain.value = 0;
                currentEffect = "phone";
                break;

            case "cave":
                filterType.value = "lowpass";
                filterFreq.value = 600;
                filterQ.value = 6;
                delayNode.delayTime.value = 0.45; // 메아리 길게
                feedback.gain.value = 0.7;        // 피드백 강하게
                tremoloGain.gain.value = 0;
                currentEffect = "cave";
                break;

            case "underwater":
                filterType.value = "lowpass";
                filterFreq.value = 400;
                filterQ.value = 2;
                delayNode.delayTime.value = 0.15;
                feedback.gain.value = 0.3;
                tremoloGain.gain.value = 0.2;
                tremoloOsc.frequency.value = 5; // 느린 진동
                currentEffect = "underwater";
                break;

            case "robot":
                filterType.value = "highpass";
                filterFreq.value = 1200;
                filterQ.value = 1;
                tremoloGain.gain.value = 1;
                tremoloOsc.frequency.value = 30; // 빠른 떨림
                delayNode.delayTime.value = 0;
                feedback.gain.value = 0;
                currentEffect = "robot";
                break;

            case "ghost": // 공포/유령 느낌
                filterType.value = "bandpass";
                filterFreq.value = 500;
                filterQ.value = 9;
                delayNode.delayTime.value = 0.5;
                feedback.gain.value = 0.8;
                tremoloGain.gain.value = 0.4;
                tremoloOsc.frequency.value = 3; // 느린 떨림
                currentEffect = "ghost";
                break;

            case "child":
                filterType.value = "allpass";
                filterFreq.value = 1500;
                filterQ.value = 2;
                tremoloGain.gain.value = 0.3;
                tremoloOsc.frequency.value = 15; // 빠른 떨림
                delayNode.delayTime.value = 0;
                feedback.gain.value = 0;
                currentEffect = "child";
                break;

            case "old":
                filterType.value = "lowpass";
                filterFreq.value = 700;
                filterQ.value = 3;
                tremoloGain.gain.value = 0.2;
                tremoloOsc.frequency.value = 2; // 느린 떨림
                delayNode.delayTime.value = 0.2;
                feedback.gain.value = 0.5;
                currentEffect = "old";
                break;

            case "echo":
                filterType.value = "allpass";
                filterFreq.value = 1000;
                filterQ.value = 1;
                delayNode.delayTime.value = 0.6; // 긴 메아리
                feedback.gain.value = 0.7;
                tremoloGain.gain.value = 0;
                currentEffect = "echo";
                break;
            case "protoss":
            filterType.value = "allpass";
            filterFreq.value = 1100;
            filterQ.value = 6;
            delayNode.delayTime.value = 0.09;
            feedback.gain.value = 0.42;
                tremoloGain.gain.value = 0;
                currentEffect = "protoss";
                break;


case "whisper":
    filterType.value = "bandpass";
    filterFreq.value = 1800;
    filterQ.value = 4;
    filter.gain.value = 6;
    delayNode.delayTime.value = 0.03;   // 아주 짧은 울림만
    feedback.gain.value = 0.2;
    tremoloGain.gain.value = 0.15;
    tremoloOsc.frequency.value = 4;
    currentEffect = "whisper";
    break;

case "radio":
    filterType.value = "bandpass";
    filterFreq.value = 1800;      // 중음역만 남김
    filterQ.value = 2;
    filter.gain.value = 8;
    delayNode.delayTime.value = 0;
    tremoloGain.gain.value = 0.4;
    // 라디오 특유 떨림
    tremoloOsc.frequency.value = 6.5;
    currentEffect = "radio";
    break;


case "megaphone":
    filterType.value = "highpass";
    filterFreq.value = 900;
    filterQ.value = 5;
    filter.gain.value = 15;           // 확성기라서 진짜 크게
    delayNode.delayTime.value = 0.05;
    feedback.gain.value = 0.35;
    tremoloGain.gain.value = 0;
    currentEffect = "megaphone";
    break;
case "demon":
    filterType.value = "lowpass";
    filterFreq.value = 800;
    filterQ.value = 3;
    filter.gain.value = 12;
    delayNode.delayTime.value = 0.07;   // 역리버브 느낌
    feedback.gain.value = 0.6;
    tremoloGain.gain.value = 0.5;
    tremoloOsc.frequency.value = 120;   // 메탈릭 링모드
    currentEffect = "demon";
    break;

case "angel":
    filterType.value = "highpass";
    filterFreq.value = 800;
    filterQ.value = 5;
    filter.gain.value = 10;
    delayNode.delayTime.value = 0.35;   // 길고 성스러운 꼬리
    feedback.gain.value = 0.65;
    tremoloGain.gain.value = 0.2;
    tremoloOsc.frequency.value = 1.5;   // 천상의 떨림
    currentEffect = "angel";
    break;

case "vader":
    filterType.value = "bandpass";
    filterFreq.value = 400;
    filterQ.value = 8;
    filter.gain.value = 15;
    delayNode.delayTime.value = 0.04;
    feedback.gain.value = 0.4;
    tremoloGain.gain.value = 0.3;
    tremoloOsc.frequency.value = 80;     // 숨소리 같은 링잉
    currentEffect = "vader";
    break;

case "giant":
    filterType.value = "lowpass";
    filterFreq.value = 300;
    filterQ.value = 4;
    filter.gain.value = 18;             // 진짜 산만하게 크게
    delayNode.delayTime.value = 0.6;
    feedback.gain.value = 0.7;
    currentEffect = "giant";
    break;

case "tiny":
    filterType.value = "highpass";
    filterFreq.value = 2200;
    filterQ.value = 6;
    filter.gain.value = 8;
    delayNode.delayTime.value = 0.02;
    feedback.gain.value = 0.3;
    tremoloGain.gain.value = 0.4;
    tremoloOsc.frequency.value = 8;
    currentEffect = "tiny";
    break;

case "possessed":
    filterType.value = "bandpass";
    filterFreq.value = 600;
    filterQ.value = 5;
    filter.gain.value = 12;
    delayNode.delayTime.value = 0.07;   // 이중 목소리 느낌
    feedback.gain.value = 0.7;
    tremoloGain.gain.value = 0.6;
    tremoloOsc.frequency.value = 100;
    currentEffect = "possessed";
    break;
    case "horror": // 진짜 소름 돋는 공포 목소리
    filterType.value = "bandpass";
    filterFreq.value = 620;
    filterQ.value = 14;                // 극단적 공명
    filter.gain.value = 15;
    delayNode.delayTime.value = 0.38;  // 불길한 메아리
    feedback.gain.value = 0.78;
    tremoloGain.gain.value = 0.6;
    tremoloOsc.frequency.value = 2.8;   // 불안한 떨림
    currentEffect = "horror";
    break;


case "helium": // 헬륨 빨고 말하는 꼬마/웃긴 목소리
    filterType.value = "highpass";
    filterFreq.value = 2900;            // 고음 극대화
    filterQ.value = 7;
    filter.gain.value = 10;
    delayNode.delayTime.value = 0.015;  // 아주 짧은 울림만
    feedback.gain.value = 0.18;
    tremoloGain.gain.value = 0.2;
    tremoloOsc.frequency.value = 12;    // 미세한 떨림으로 더 웃김
    currentEffect = "helium";
    break;
    case "timewarp": // 시간이 느려지는 듯한 몽환·환상 효과
    filterType.value = "lowpass";
    filterFreq.value = 580;
    filterQ.value = 9;
    filter.gain.value = 13;
    delayNode.delayTime.value = 0.42;   // 길게 늘어지는 메아리
    feedback.gain.value = 0.89;         // 거의 무한에 가까운 반복
    tremoloOsc.frequency.value = 0.25;  // 초저속 떨림 → 시간 멈춘 듯
    tremoloGain.gain.value = 0.5;
    currentEffect = "timewarp";
    break;

case "glitch": // 디지털 깨져버린 AI·사이버펑크 목소리
    filterType.value = "bandpass";
    filterFreq.value = 1300;
    filterQ.value = 22;                 // 극단적 공명
    filter.gain.value = 11;
    delayNode.delayTime.value = 0.008;  // 아주 짧고 날카로운 반복
    feedback.gain.value = 0.35;
    tremoloOsc.frequency.value = 280;   // 미친듯이 빠른 떨림
    tremoloGain.gain.value = 0.92;      // 거의 깨진 느낌
    currentEffect = "glitch";
    break;

case "choir": // 천상의 성가대·신성한 합창 효과
    filterType.value = "allpass";
    filterFreq.value = 1600;
    filterQ.value = 5;
    filter.gain.value = 15;
    delayNode.delayTime.value = 0.28;   // 은은하게 퍼지는 울림
    feedback.gain.value = 0.72;
    tremoloOsc.frequency.value = 1.1;   // 천사들의 미세 떨림
    tremoloGain.gain.value = 0.28;
    currentEffect = "choir";
    break;
    case "hyperpop":      // TikTok·Hyperpop 보컬
    filterType.value = "highpass";
    filterFreq.value = 3200;
    filterQ.value = 14;
    filter.gain.value = 19;
    delayNode.delayTime.value = 0.018;
    feedback.gain.value = 0.42;
    tremoloOsc.frequency.value = 220;
    tremoloGain.gain.value = 0.7;
    currentEffect = "hyperpop";
    break;

case "vaporwave":     // 80년대 쇼핑몰 + 슬로우 리버브
    filterType.value = "lowpass";
    filterFreq.value = 3400;
    filterQ.value = 2;
    filter.gain.value = 11;
    delayNode.delayTime.value = 0.38;
    feedback.gain.value = 0.78;
    tremoloOsc.frequency.value = 0.35;
    tremoloGain.gain.value = 0.65;
    currentEffect = "vaporwave";
    break;

case "darksynth":     // Cyberpunk 2077 나이트시티 DJ
    filterType.value = "bandpass";
    filterFreq.value = 950;
    filterQ.value = 11;
    filter.gain.value = 17;
    delayNode.delayTime.value = 0.24;
    feedback.gain.value = 0.70;
    tremoloOsc.frequency.value = 130;
    tremoloGain.gain.value = 0.55;
    currentEffect = "darksynth";
    break;

case "lofi-girl":     // Lo-Fi HipHop 라디오 걸 ASMR 보이스
    filterType.value = "lowpass";
    filterFreq.value = 4200;
    filterQ.value = 1.8;
    filter.gain.value = 9;
    delayNode.delayTime.value = 0.45;
    feedback.gain.value = 0.62;
    tremoloOsc.frequency.value = 0.12;
    tremoloGain.gain.value = 0.35;
    currentEffect = "lofi-girl";
    break;

case "bitcrush-voice": // 8bit 게임 깨져버린 보이스 (2025 트렌드)
    filterType.value = "bandpass";
    filterFreq.value = 2200;
    filterQ.value = 28;
    filter.gain.value = 15;
    delayNode.delayTime.value = 0.004;
    feedback.gain.value = 0.25;
    tremoloOsc.frequency.value = 420;
    tremoloGain.gain.value = 0.96;
    currentEffect = "bitcrush-voice";
    break;

case "portal":        // 차원문 열리는 듯한 공간 왜곡
    filterType.value = "allpass";
    filterFreq.value = 750;
    filterQ.value = 18;
    filter.gain.value = 22;
    delayNode.delayTime.value = 0.65;
    feedback.gain.value = 0.94;
    tremoloOsc.frequency.value = 0.7;
    tremoloGain.gain.value = 0.8;
    currentEffect = "portal";
    break;

case "neoncity":      // Blade Runner 2049 네온 도시 아나운서
    filterType.value = "bandpass";
    filterFreq.value = 1150;
    filterQ.value = 9;
    filter.gain.value = 19;
    delayNode.delayTime.value = 0.52;
    feedback.gain.value = 0.80;
    tremoloOsc.frequency.value = 2.8;
    tremoloGain.gain.value = 0.45;
    currentEffect = "neoncity";
    break;

case "ghost-in-machine": // AI가 귀신 들린 듯한 최신 호러
    filterType.value = "bandpass";
    filterFreq.value = 780;
    filterQ.value = 20;
    filter.gain.value = 16;
    delayNode.delayTime.value = 0.09;
    feedback.gain.value = 0.58;
    tremoloOsc.frequency.value = 190;
    tremoloGain.gain.value = 0.88;
    currentEffect = "ghost-in-machine";
    break;
        }


            updateFilter();
            applyRouting(currentEffect);
        };
    });
}
async function saveFilteredAudio() {
    const page = pages[currentPageIndex];

    if (!page.audioUrl && !page.audioFile) {
        alert("현재 페이지에 오디오가 없습니다.");
        return;
    }

    // 1) 원본 오디오 로드
    let arrayBuffer;
    if (page.audioFile) {
        arrayBuffer = await page.audioFile.arrayBuffer();
    } else {
        const res = await fetch(page.audioUrl);
        arrayBuffer = await res.arrayBuffer();
    }

    const tempCtx = new AudioContext();
    const originalBuffer = await tempCtx.decodeAudioData(arrayBuffer);
    tempCtx.close();

    // 2) OfflineAudioContext 생성
    const offlineCtx = new OfflineAudioContext(
        originalBuffer.numberOfChannels,
        originalBuffer.length,
        originalBuffer.sampleRate
    );

    // 3) 실시간과 똑같은 노드 생성
    const source = offlineCtx.createBufferSource();
    source.buffer = originalBuffer;

    const filter = offlineCtx.createBiquadFilter();
    const delayNode = offlineCtx.createDelay(2);
    const feedback = offlineCtx.createGain();
    const tremoloGain = offlineCtx.createGain();
    const tremoloOsc = offlineCtx.createOscillator();
    tremoloOsc.type = "sine";
    const masterGain = offlineCtx.createGain();

    // 4) 실시간에서 현재 적용된 모든 파라미터를 그대로 복사
    const filterTypeEl = document.getElementById("filterType");
    const filterFreqEl = document.getElementById("filterFrequency");
    const filterQEl = document.getElementById("filterQ");
    const filterGainEl = document.getElementById("filterGain");
    const masterVolEl = document.getElementById("masterVolume");

    filter.type = filterTypeEl.value;
    filter.frequency.value = parseFloat(filterFreqEl.value);
    filter.Q.value = parseFloat(filterQEl.value);
    filter.gain.value = parseFloat(filterGainEl.value);
    masterGain.gain.value = parseFloat(masterVolEl.value || 1);

    // 프리셋에서 설정된 delay/tremolo 값도 그대로 복사 (DOM에 반영되어 있음)
    // initAudioFilters()에서 프리셋 클릭 시 delayNode.delayTime, feedback.gain, tremoloOsc.frequency 등을 직접 설정했음
    // 하지만 Offline에서는 새로 만들었으므로, currentEffect 기반으로 다시 설정
    // → 하지만 더 정확하게 하려면 실시간 노드의 현재 값을 읽는 게 제일 좋지만 불가능
    // 그래서 가장 현실적인 방법: 프리셋 switch에서 설정한 값과 동일하게 재현

    let delayTime = 0;
    let feedbackGain = 0;
    let tremoloRate = 10;
    let tremoloDepth = 0;

    // currentEffect별 정확한 값 재현 (실시간 프리셋과 1:1 매칭)
    switch (currentEffect) {
        case "normal": case "phone": case "megaphone":
            delayTime = 0; feedbackGain = 0; tremoloDepth = 0;
            break;
        case "cave":
            delayTime = 0.45; feedbackGain = 0.7; tremoloDepth = 0;
            break;
        case "echo":
            delayTime = 0.6; feedbackGain = 0.7; tremoloDepth = 0;
            break;
        case "underwater":
            delayTime = 0.15; feedbackGain = 0.3; tremoloRate = 5; tremoloDepth = 0.6;
            break;
        case "robot":
            delayTime = 0; feedbackGain = 0; tremoloRate = 30; tremoloDepth = 1;
            break;
        case "ghost":
            delayTime = 0.5; feedbackGain = 0.8; tremoloRate = 3; tremoloDepth = 0.7;
            break;
        case "whisper":
            delayTime = 0.03; feedbackGain = 0.2; tremoloRate = 4; tremoloDepth = 0.4;
            break;
        case "radio":
            delayTime = 0; feedbackGain = 0; tremoloRate = 6.5; tremoloDepth = 0.7;
            break;
        case "protoss":
            delayTime = 0.09; feedbackGain = 0.42; tremoloRate = 10; tremoloDepth = 0;
            break;
        case "demon":
            delayTime = 0.07; feedbackGain = 0.6; tremoloRate = 120; tremoloDepth = 0.9;
            break;
        case "angel":
            delayTime = 0.35; feedbackGain = 0.65; tremoloRate = 1.5; tremoloDepth = 0.4;
            break;
        case "vader":
            delayTime = 0.04; feedbackGain = 0.4; tremoloRate = 80; tremoloDepth = 0.6;
            break;
        case "possessed":
            delayTime = 0.07; feedbackGain = 0.7; tremoloRate = 100; tremoloDepth = 0.9;
            break;
        case "horror":
            delayTime = 0.38; feedbackGain = 0.78; tremoloRate = 2.8; tremoloDepth = 0.85;
            break;
        case "helium":
            delayTime = 0.015; feedbackGain = 0.18; tremoloRate = 12; tremoloDepth = 0.5;
            break;
        case "timewarp":
            delayTime = 0.42; feedbackGain = 0.89; tremoloRate = 0.25; tremoloDepth = 0.8;
            break;
        case "glitch":
            delayTime = 0.008; feedbackGain = 0.35; tremoloRate = 280; tremoloDepth = 0.98;
            break;
        case "choir":
            delayTime = 0.28; feedbackGain = 0.72; tremoloRate = 1.1; tremoloDepth = 0.5;
            break;
        case "hyperpop":
            delayTime = 0.018; feedbackGain = 0.42; tremoloRate = 220; tremoloDepth = 0.9;
            break;
        case "vaporwave":
            delayTime = 0.38; feedbackGain = 0.78; tremoloRate = 0.35; tremoloDepth = 0.8;
            break;
        case "bitcrush-voice":
            delayTime = 0.004; feedbackGain = 0.25; tremoloRate = 420; tremoloDepth = 0.98;
            break;
        case "portal":
            delayTime = 0.65; feedbackGain = 0.94; tremoloRate = 0.7; tremoloDepth = 0.9;
            break;
        // 필요시 더 추가
        default:
            delayTime = 0; feedbackGain = 0; tremoloDepth = 0;
    }

    delayNode.delayTime.value = delayTime;
    feedback.gain.value = feedbackGain;
    tremoloOsc.frequency.value = tremoloRate;

    // Tremolo: 더 강하고 실시간과 비슷하게
    tremoloOsc.connect(tremoloGain.gain);
    tremoloOsc.start();
    // depth가 깊을수록 gain을 0.2 ~ 1.0 사이로 진동
    tremoloGain.gain.setValueAtTime(1, offlineCtx.currentTime);
    tremoloGain.gain.value = 1 - tremoloDepth * 0.8; // 중심값 낮춰서 떨림 강하게

    // 5) 실시간 applyRouting()과 최대한 동일한 연결
    source.connect(filter);

    // 기본: filter → masterGain
    filter.connect(masterGain);

    // Delay 적용 (실시간과 동일하게 dry + wet)
    if (delayTime > 0 || feedbackGain > 0) {
        filter.connect(delayNode);
        delayNode.connect(feedback);
        feedback.connect(delayNode);
        delayNode.connect(masterGain);
        // dry는 이미 연결됨
    }

    // Tremolo 적용 (실시간 robot/cave 등과 동일하게)
    if (tremoloDepth > 0) {
        // filter에서 tremolo로 분기
        filter.connect(tremoloGain);
        tremoloGain.connect(masterGain);

        // dry 약간 섞기 (너무 강하지 않게)
        if (tremoloDepth < 0.95) {
            filter.connect(masterGain);
        }

        // delay가 있으면 wet에도 tremolo 적용
        if (delayTime > 0) {
            delayNode.connect(tremoloGain);
        }
    }

    masterGain.connect(offlineCtx.destination);

    // 6) 렌더링
    source.start();
    const processedBuffer = await offlineCtx.startRendering();

    // 7) WAV 저장
    const wavBlob = bufferToWav(processedBuffer);
    const newFile = new File([wavBlob], `page_${currentPageIndex + 1}_filtered.wav`, { type: "audio/wav" });

    page.audioFile = newFile;
    page.audioUrl = URL.createObjectURL(newFile);

    alert("🎉 실시간 미리듣기와 거의 동일한 효과로 저장되었습니다!");

    const audioPlayer = document.getElementById("pageAudioPlayer");
    if (audioPlayer) {
        audioPlayer.src = page.audioUrl;
        audioPlayer.load();
    }

    loadPage(currentPageIndex);
}
// wav 변환 함수
function bufferToWav(buffer) {
    const numOfChan = buffer.numberOfChannels,
        length = buffer.length * numOfChan * 2 + 44,
        buffer2 = new ArrayBuffer(length),
        view = new DataView(buffer2),
        channels = [],
        sampleRate = buffer.sampleRate;

    let offset = 0;

    writeString(view, offset, "RIFF"); offset += 4;
    view.setUint32(offset, 36 + buffer.length * numOfChan * 2, true); offset += 4;
    writeString(view, offset, "WAVE"); offset += 4;
    writeString(view, offset, "fmt "); offset += 4;
    view.setUint32(offset, 16, true); offset += 4;
    view.setUint16(offset, 1, true); offset += 2;
    view.setUint16(offset, numOfChan, true); offset += 2;
    view.setUint32(offset, sampleRate, true); offset += 4;
    view.setUint32(offset, sampleRate * numOfChan * 2, true); offset += 4;
    view.setUint16(offset, numOfChan * 2, true); offset += 2;
    view.setUint16(offset, 16, true); offset += 2;
    writeString(view, offset, "data"); offset += 4;
    view.setUint32(offset, buffer.length * numOfChan * 2, true); offset += 4;

    for (let i = 0; i < numOfChan; i++)
        channels.push(buffer.getChannelData(i));

    let pos = 0;
    while (pos < buffer.length) {
        for (let i = 0; i < numOfChan; i++) {
            let sample = Math.max(-1, Math.min(1, channels[i][pos]));
            view.setInt16(offset, sample * 0x7fff, true);
            offset += 2;
        }
        pos++;
    }

    return new Blob([buffer2], { type: "audio/wav" });
}

function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}
