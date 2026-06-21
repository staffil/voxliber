/**
 * Flutter WebView 감지 후 OAuth provider로 리다이렉트
 * Flutter 앱에서 열릴 때: User-Agent에 'VoxLiberApp' 포함 또는
 * window.oauthRedirectUri가 설정된 경우
 */
function oauthLogin(provider) {
    const ua = navigator.userAgent;
    const isFlutter = ua.includes('VoxLiberApp') ||
                      typeof window.flutter_inappwebview !== 'undefined' ||
                      typeof window.oauthRedirectUri !== 'undefined';

    let url = `/login/oauth/${provider}/`;

    if (isFlutter) {
        const redirectUri = window.oauthRedirectUri || 'voxliber://oauth/callback';
        url += `?redirect_uri=${encodeURIComponent(redirectUri)}`;
    }

    location.href = url;
}
