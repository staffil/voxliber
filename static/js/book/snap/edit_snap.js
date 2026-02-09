const previewBox = document.getElementById("snap-preview");

/* 이미지 프리뷰 */
document.getElementById("image-input").addEventListener("change", function(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = e => {
        previewBox.innerHTML = `<img src="${e.target.result}" />`;
    };
    reader.readAsDataURL(file);
});

/* 비디오 프리뷰 */
document.getElementById("video-input").addEventListener("change", function(e) {
    const file = e.target.files[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    previewBox.innerHTML = `<video src="${url}" controls></video>`;
});