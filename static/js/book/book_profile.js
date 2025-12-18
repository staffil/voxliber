// 쿠키 가져오기
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

document.addEventListener("DOMContentLoaded", function() {
    const bookCoverInput = document.getElementById("book-cover-image");
    const bookPreview = document.getElementById("cover-preview");
    const previewBookImg = document.getElementById("preview-cover");

    // 북 표지 업로드
    if (bookPreview && bookCoverInput) {
        bookPreview.addEventListener('click', function() {
            bookCoverInput.click();
        });
    }

    // 파일 선택시 미리 보기
    if (bookCoverInput) {
        bookCoverInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file){
                const reader = new FileReader();
                reader.onload = function(event) {
                    previewBookImg.src = event.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // 태그 관련 요소
    const searchInput = document.getElementById("tag-search");
    const selectedTagsContainer = document.getElementById("selected-tags");
    const tagGrid = document.getElementById("tag-grid");
    const addTagBtn = document.getElementById("add-tag-btn");

    // 선택된 태그 업데이트 함수
    function updateSelectedTags() {
        const checkboxes = document.querySelectorAll(".tag-checkbox:checked");
        selectedTagsContainer.innerHTML = "";

        checkboxes.forEach(checkbox => {
            const tagName = checkbox.parentElement.querySelector("span").textContent;
            const tagId = checkbox.value;

            // hidden input 추가
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "tags";
            input.value = tagId;
            selectedTagsContainer.appendChild(input);

            // 선택된 태그 표시
            const span = document.createElement("span");
            span.className = "selected-tag";
            span.textContent = tagName;
            selectedTagsContainer.appendChild(span);
        });
    }

    // 태그 체크박스 클릭 이벤트
    if (tagGrid) {
        tagGrid.addEventListener("change", function(e) {
            if (e.target.classList.contains("tag-checkbox")) {
                updateSelectedTags();
            }
        });
    }

    // 태그 추가 버튼
    if (addTagBtn) {
        addTagBtn.addEventListener("click", async() => {
            const name = searchInput.value.trim();
            if (!name) {
                alert("태그 이름을 입력해주세요.");
                return;
            }

            try {
                const res = await fetch("/book/tags/add/", {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    body: `name=${encodeURIComponent(name)}`
                });

                if (!res.ok) {
                    throw new Error("태그 추가 실패");
                }

                const tag = await res.json();

                // 새 태그를 태그 그리드에 추가
                const label = document.createElement("label");
                label.className = "tag-option";

                const checkbox = document.createElement("input");
                checkbox.type = "checkbox";
                checkbox.className = "tag-checkbox";
                checkbox.value = tag.id;
                checkbox.checked = true;

                const span = document.createElement("span");
                span.textContent = tag.name;

                label.appendChild(checkbox);
                label.appendChild(span);
                tagGrid.appendChild(label);

                // 선택된 태그 업데이트
                updateSelectedTags();

                searchInput.value = "";

                if (tag.created) {
                    alert(`새 태그 "${tag.name}"가 추가되었습니다.`);
                } else {
                    alert(`태그 "${tag.name}"가 선택되었습니다.`);
                }
            } catch (error) {
                console.error("Error:", error);
                alert("태그 추가 중 오류가 발생했습니다.");
            }
        });
    }

    // Enter 키로 태그 추가
    if (searchInput) {
        searchInput.addEventListener("keypress", function(e) {
            if (e.key === "Enter") {
                e.preventDefault();
                addTagBtn.click();
            }
        });
    }

    // 폼 제출 시 유효성 검사
    const bookProfileForm = document.getElementById("book_profile_form");
    if (bookProfileForm) {
        bookProfileForm.addEventListener("submit", function(e) {
            // 제목 검사
            const title = document.querySelector('input[name="novel_title"]').value.trim();
            if (!title) {
                e.preventDefault();
                showAlert("소설 제목을 입력해주세요.");
                return false;
            }

            // 표지 이미지 검사
            const coverInput = document.getElementById("book-cover-image");
            const previewImg = document.getElementById("preview-cover");
            const hasDefaultCover = previewImg.src.indexOf("default-novel-cover") !== -1;
            const hasUploadedFile = coverInput.files && coverInput.files.length > 0;

            // 기본 이미지이고 새로 업로드한 파일도 없으면 에러
            if (hasDefaultCover && !hasUploadedFile) {
                e.preventDefault();
                showAlert("표지 이미지를 선택해주세요.");
                return false;
            }

            // 장르 검사
            const genreCheckboxes = document.querySelectorAll('input[name="genres"]:checked');
            if (genreCheckboxes.length === 0) {
                e.preventDefault();
                showAlert("최소 1개 이상의 장르를 선택해주세요.");
                return false;
            }

            // 태그 검사
            const tagCheckboxes = document.querySelectorAll('.tag-checkbox:checked');
            if (tagCheckboxes.length === 0) {
                e.preventDefault();
                showAlert("최소 1개 이상의 태그를 선택해주세요.");
                return false;
            }

            return true;
        });
    }

    // 알림 표시 함수
    function showAlert(message) {
        const alertDiv = document.createElement('div');
        alertDiv.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 30px 40px;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
            z-index: 10000;
            text-align: center;
            min-width: 300px;
        `;

        const messageP = document.createElement('p');
        messageP.style.cssText = `
            margin: 0 0 20px 0;
            font-size: 16px;
            color: #333;
            font-weight: 500;
        `;
        messageP.textContent = message;

        const okButton = document.createElement('button');
        okButton.textContent = '확인';
        okButton.style.cssText = `
            background: #6366f1;
            color: white;
            border: none;
            padding: 10px 30px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        `;
        okButton.onmouseover = function() {
            this.style.background = '#4f46e5';
        };
        okButton.onmouseout = function() {
            this.style.background = '#6366f1';
        };
        okButton.onclick = function() {
            document.body.removeChild(overlay);
        };

        alertDiv.appendChild(messageP);
        alertDiv.appendChild(okButton);

        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 9999;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        overlay.appendChild(alertDiv);
        document.body.appendChild(overlay);

        // 오버레이 클릭 시 닫기
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) {
                document.body.removeChild(overlay);
            }
        });
    }
});
