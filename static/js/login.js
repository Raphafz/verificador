document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('loginForm');
  if (!form) return;

  const loginInput = document.getElementById('id_username');
  const pwdInput = document.getElementById('id_password');
  const remember = document.getElementById('rememberEmail');
  const passwordToggle = document.getElementById('passwordToggle');

  const scope = document.body.dataset.loginScope || 'default';
  const storageKey = 'rm_saved_login_' + scope;
  const legacyEmailKey = 'rememberedEmail';

  function loadSavedCredentials() {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const data = JSON.parse(raw);
        if (loginInput && data.login) loginInput.value = data.login;
        if (pwdInput && data.password) pwdInput.value = data.password;
        if (remember) remember.checked = true;
        return;
      }

      const legacyLogin = localStorage.getItem(legacyEmailKey);
      if (legacyLogin && loginInput) {
        loginInput.value = legacyLogin;
        if (remember) remember.checked = true;
        localStorage.removeItem(legacyEmailKey);
      }
    } catch (_) { /* ignore */ }
  }

  function saveOrClearCredentials() {
    try {
      if (remember && remember.checked && loginInput) {
        const login = loginInput.value.trim();
        if (!login) return;
        localStorage.setItem(
          storageKey,
          JSON.stringify({
            login: login,
            password: pwdInput ? pwdInput.value : '',
          })
        );
        localStorage.removeItem(legacyEmailKey);
      } else {
        localStorage.removeItem(storageKey);
        localStorage.removeItem(legacyEmailKey);
      }
    } catch (_) { /* ignore */ }
  }

  loadSavedCredentials();

  if (pwdInput) {
    pwdInput.required = true;
  }

  form.addEventListener('submit', saveOrClearCredentials);

  if (passwordToggle && pwdInput) {
    passwordToggle.addEventListener('click', function () {
      const icon = passwordToggle.querySelector('i');
      if (pwdInput.type === 'password') {
        pwdInput.type = 'text';
        icon.className = 'fas fa-eye-slash';
        passwordToggle.setAttribute('aria-label', 'Ocultar senha');
      } else {
        pwdInput.type = 'password';
        icon.className = 'fas fa-eye';
        passwordToggle.setAttribute('aria-label', 'Mostrar senha');
      }
    });
  }
});
