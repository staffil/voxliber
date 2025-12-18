const csrftoken = getCookie('csrftoken');

fetch('/tts/generate/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': csrftoken,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({ text: pageContent })
});
