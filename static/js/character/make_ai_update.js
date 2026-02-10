document.addEventListener('DOMContentLoaded', function () {
  const fileInput = document.getElementById('user_image');     
  const previewImage = document.getElementById('preview-image');
  const fileText = document.getElementById('file-text');

  if (!fileInput) {
    console.error('파일 입력 요소를 찾을 수 없습니다. ID 확인하세요.');
    return;
  }

  fileInput.addEventListener('change', function () {
    const file = this.files[0];
    if (!file) return;

    // 텍스트 변경
    fileText.textContent = file.name;

    // 이미지 미리보기
    const imageUrl = URL.createObjectURL(file);
    previewImage.src = imageUrl;
    previewImage.style.display = 'block';
  });

const container = document.getElementById('sub-images-container');
  const addBtn = document.getElementById('add-sub-image-btn');

  // 추가 버튼 클릭 시 새 입력 칸 생성
  addBtn.addEventListener('click', function() {
    const entry = document.createElement('div');
    entry.className = 'sub-image-entry';
    entry.style.marginBottom = '1.5rem';
    entry.style.padding = '1rem';
    entry.style.border = '1px dashed #ccc';
    entry.style.borderRadius = '8px';

    entry.innerHTML = `
      <div class="form-row" style="display: flex; gap: 1rem; flex-wrap: wrap;">
        <div style="flex: 1;">
          <label>이미지 파일</label>
          <input type="file" name="sub_images" accept="image/*" class="sub-image-file">
        </div>
        <div style="flex: 1; min-width: 200px;">
          <label>HP 범위 (이 범위일 때 이 이미지 사용)</label>
          <div style="display: flex; gap: 0.5rem;">
            <input type="number" name="min_hp[]" placeholder="최소 HP (예: 0)" min="0" style="width: 100px;">
            <span>~</span>
            <input type="number" name="max_hp[]" placeholder="최대 HP (예: 30)" min="0" style="width: 100px;">
          </div>
          <small style="color: #666;">빈 칸이면 HP 조건 없이 사용됩니다.</small>
        </div>
      </div>

      <div style="margin-top: 0.8rem;">
        <label>이미지 제목/메모 (선택)</label>
                                            <textarea type="text" name="sub_image_title[]" placeholder="현재 상황에 맞는 스토리를 적어주세요.(400자)" maxlength="400" class="form-input" value="{{ item.sub_image.title|default:'' }}"  style="max-width: 500px; max-height: 300px;" data-login-required></textarea>
      </div>

      <button type="button" class="remove-sub-image" style="margin-top: 0.5rem; color: #e74c3c; background: none; border: none; cursor: pointer;">
        이 이미지 제거
      </button>
    `;

    container.appendChild(entry);

    // 새로 추가된 삭제 버튼에도 이벤트 붙이기
    entry.querySelector('.remove-sub-image').addEventListener('click', function() {
      entry.remove();
    });
  });

  // 처음부터 있는 삭제 버튼에도 이벤트
  document.querySelectorAll('.remove-sub-image').forEach(btn => {
    btn.addEventListener('click', function() {
      this.closest('.sub-image-entry').remove();
    });
  });

});


const voiceSpans = document.querySelectorAll('.voice-list span');  // <span>{{ voice.voice_id }}</span> 클릭 대상

voiceSpans.forEach(span => {
    span.style.cursor = 'pointer';
    span.addEventListener('click', function() {
        const voiceId = this.textContent.trim();
        document.getElementById('voice_id').value = voiceId;
        
        // 시각적 피드백
        voiceSpans.forEach(s => s.style.backgroundColor = '');
        this.style.backgroundColor = '#e0f7fa';
    });
});



document.addEventListener('DOMContentLoaded', function() {
  const container = document.getElementById('lore-entries-container');
  const addBtn = document.getElementById('add-lore-entry');

  // 추가 버튼 클릭 시 새 항목 생성
  addBtn.addEventListener('click', function() {
    const entry = document.createElement('div');
    entry.className = 'lore-entry';
    entry.style.marginBottom = '2rem';
    entry.style.padding = '1.5rem';
    entry.style.border = '1px dashed #000000';
    entry.style.borderRadius = '12px';
    entry.style.background = '#fafafa';

    entry.innerHTML = `
      <div class="sub-form-group">
        <label>활성화 키워드</label>
        <textarea 
          name="lore_keys[]" 
          rows="3" 
          placeholder="쉼표(,) 또는 줄바꿈으로 구분 (예: 마을, 왕궁, 저주받은 검)"
          required
        ></textarea>
        <small>대화에 이 키워드가 나오면 내용이 주입됩니다.</small>
      </div>

      <div class="sub-form-group">
        <label>주입될 내용</label>
        <textarea 
          name="lore_content[]" 
          rows="5" 
          placeholder="AI에게 주입할 설명, 사실, 설정 등을 자세히"
          required
        ></textarea>
      </div>

      <div class="sub-form-group">
        <label>우선순위</label>
        <input 
          type="number" 
          name="lore_priority[]" 
          value="0" 
          min="0" 
          step="1"
          style="width: 100px;"
        >
        <small>높을수록 먼저 주입</small>
      </div>

      <div class="sub-form-group checkbox-group">
        <label>
          <input type="checkbox" name="lore_always_active[]" value="true">
          항상 포함시키기
        </label>
        <small>주의: 토큰 소모 증가</small>
      </div>

      <div class="sub-form-group">
        <label>카테고리</label>
        <select name="lore_category[]">
          <option value="">선택 안 함</option>
          <option value="personality">성격</option>
          <option value="world">세계관</option>
          <option value="relationship">관계</option>
        </select>
      </div>

      <button type="button" class="remove-lore-entry" style="margin-top: 1rem; color: #e74c3c; background: none; border: none; cursor: pointer;">
        이 항목 제거
      </button>
    `;

    container.appendChild(entry);

    // 새로 추가된 삭제 버튼에 이벤트 붙이기
    entry.querySelector('.remove-lore-entry').addEventListener('click', function() {
      entry.remove();
    });
    
  });


  // 처음부터 있는 삭제 버튼에도 이벤트
  document.querySelectorAll('.remove-lore-entry').forEach(btn => {
    btn.addEventListener('click', function() {
      this.closest('.lore-entry').remove();
    });
  });
});



