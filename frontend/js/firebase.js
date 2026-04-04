const firebaseConfig = {
  apiKey: "AIzaSyAZEvPB1MaBbnT09e5EibwUsXvb-M725YM",
  authDomain: "notestackiitm.firebaseapp.com",
  projectId: "notestackiitm",
  storageBucket: "notestackiitm.firebasestorage.app",
  messagingSenderId: "493958401204",
  appId: "1:493958401204:web:3e01028a538146e06b1be1"
};

// Initialize Firebase (only if firebase JS script is included in the HTML)
if (typeof firebase !== 'undefined') {
  firebase.initializeApp(firebaseConfig);
  console.log('[Firebase] Client initialized successfully');

  // ── Google Auth Logic ────────────────────────────────────────
  const auth = firebase.auth();
  const provider = new firebase.auth.GoogleAuthProvider();

  async function handleGoogleAuth() {
    try {
      const result = await auth.signInWithPopup(provider);
      const idToken = await result.user.getIdToken();

      // Send token to backend to create session
      const response = await fetch('/api/auth/google', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id_token: idToken }),
      });

      const data = await response.json();

      if (data.success) {
        window.location.href = data.redirect_url || '/dashboard';
      } else {
        alert('Authentication failed: ' + (data.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('[Firebase] Sign-in error:', error);
      if (error.code !== 'auth/popup-closed-by-user') {
        alert('Error during Google sign-in: ' + error.message);
      }
    }
  }

  // Attach listeners when DOM is ready
  document.addEventListener('DOMContentLoaded', () => {
    const loginBtn = document.getElementById('google-login-btn');
    const registerBtn = document.getElementById('google-signin-btn');

    if (loginBtn) {
      loginBtn.addEventListener('click', handleGoogleAuth);
    }
    if (registerBtn) {
      registerBtn.addEventListener('click', handleGoogleAuth);
    }
  });

} else {
  console.warn('[Firebase] SDK script not found. Firebase features may not work.');
}