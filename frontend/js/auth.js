function validateRegisterForm(form) {
  const password = form.querySelector('[name="password"]');
  const confirm  = form.querySelector('[name="confirm_password"]');

  if (password && confirm && password.value !== confirm.value) {
    showToast('Passwords do not match.');
    return false;
  }
  return true;
}

/**
 * Shows a toast notification (reuses global toast system from utils.js).
 */
function showToast(message) {
  const toast = document.createElement('div');
  toast.className = 'brutalist-toast';
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.transition = 'all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)';
    toast.style.transform  = 'translate(100px, -100px)';
    toast.style.opacity    = '0';
    setTimeout(() => toast.remove(), 500);
  }, 3500);
}

// Attach to register form if present
document.addEventListener('DOMContentLoaded', () => {
  const registerForm = document.getElementById('register-form');
  if (registerForm) {
    registerForm.addEventListener('submit', (e) => {
      if (!validateRegisterForm(registerForm)) {
        e.preventDefault();
      }
    });
  }
});