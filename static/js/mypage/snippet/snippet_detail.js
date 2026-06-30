document.getElementById("generateTTSSnippetBtn").addEventListener("click", async function () {

    const sentence = document.getElementById("sentence").value.trim();
const voiceId = document.getElementById("voice").value;

    if (!sentence) {
        alert("스니펫 문장을 먼저 입력해주세요.");
        return;
    }

    this.disabled = true;
    this.innerText = "🔄 생성 중...";

    try {
        const response = await fetch("/book/tts/generate/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
            },
            body: JSON.stringify({
                text: sentence,
                language_code: "ko",
                speed_value: "1.0",
                voice_id: voiceId, 
            })
        });

        if (!response.ok) {
            throw new Error("TTS 생성 실패");
        }

        const blob = await response.blob();
        const audioUrl = URL.createObjectURL(blob);

        // 오디오 미리듣기 활성화
        const audioBox = document.getElementById("audioSnippetPreviewBox");
        document.getElementById("snippetTTS").src = audioUrl;
        audioBox.style.display = "block";

    } catch (err) {
        console.error(err);
        alert("TTS 생성 중 문제가 발생했습니다.");
    } finally {
        this.disabled = false;
        this.innerText = "🎧 TTS 생성하기";
    }
});