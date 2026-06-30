function previewFile(input, previewId, areaId) {
  var file = input.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(e) {
    var preview = document.getElementById(previewId);
    preview.src = e.target.result;
    preview.style.display = 'block';
  };
  reader.readAsDataURL(file);
}
function setVideoName(input, areaId) {
  var file = input.files[0];
  if (!file) return;
  var area = document.getElementById(areaId);
  var text = area.querySelector('.file-upload-text');
  if (text) text.innerHTML = '<strong>' + file.name + '</strong>선택 완료';
}